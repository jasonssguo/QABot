# agent.py
from utils import *
from config import *
from prompt import *
import urllib.parse

import os
from langchain.chains import LLMChain, LLMRequestsChain
from langchain.prompts import PromptTemplate
from langchain.vectorstores.chroma import Chroma
from langchain.vectorstores.faiss import FAISS
from langchain.schema import Document
from langchain.agents import ZeroShotAgent, AgentExecutor, Tool
from langchain.memory import ConversationBufferMemory
from langchain.output_parsers import ResponseSchema, StructuredOutputParser


class Agent():
    def __init__(self):
        # 定义向量库持久化目录
        self.db_path = os.path.join(os.path.dirname(__file__), './data/db/')
        # 初始化嵌入模型
        self.embeddings = get_embeddings_model()
        # 初始化Chroma向量库
        self.vdb = self.init_chroma_db()

    def init_chroma_db(self):
        """
        初始化Chroma向量库：如果库中无数据，则添加示例数据；否则直接加载
        """
        # 检查Chroma持久化目录是否存在（判断是否已有数据）
        if os.path.exists(self.db_path) and len(os.listdir(self.db_path)) > 0:
            # 加载已存在的向量库
            vdb = Chroma(
                persist_directory=self.db_path,
                embedding_function=self.embeddings
            )
            print(f"成功加载已有向量库，当前库中文档数量：{vdb._collection.count()}")
        else:
            # 无数据时，创建示例文档并写入向量库
            # 这里替换成你自己的业务文档
            sample_documents = [
                Document(
                    page_content="寻医问药网是一个专业的医疗健康信息服务平台，提供疾病咨询、药品查询、医生在线问诊等服务。",
                    metadata={"source": "寻医问药网官网"}
                ),
                Document(
                    page_content="寻医问药网的客服电话是400-123-4567，工作时间为每天9:00-18:00。",
                    metadata={"source": "寻医问药网帮助中心"}
                )
            ]
            # 将文档写入Chroma向量库
            vdb = Chroma.from_documents(
                documents=sample_documents,
                embedding=self.embeddings,
                persist_directory=self.db_path
            )
            # 持久化数据（关键步骤，确保数据写入磁盘）
            vdb.persist()
            print(f"已创建新向量库并写入{len(sample_documents)}条示例文档")
        return vdb

    def generic_func(self, x, query):
        # print(f'query{query}')
        prompt = PromptTemplate.from_template(GENERIC_PROMPT_TPL)
        llm_chain = LLMChain(
            llm=get_llm_model(),
            prompt=prompt,
            verbose=os.getenv("VERBOSE")
        )
        return llm_chain.run(query)

    def retrival_func(self, x, query):
        # 召回并过滤文档（k=5表示返回最相似的5条）
        documents = self.vdb.similarity_search_with_relevance_scores(query, k=5)
        # 打印查询结果，方便调试（替换原来的print+exit）
        # print(f"\n原始查询结果（文档+相似度得分）：{documents}")

        # 过滤相似度得分>0.7的文档
        query_result = [doc[0].page_content for doc in documents if doc[1] > 0.5]
        # print(f"\n过滤后的有效文档：{query_result}")

        # 填充答案
        prompt = PromptTemplate.from_template(RETRIVAL_PROMPT_TPL)
        retrival_chain = LLMChain(
            llm=get_llm_model(),
            prompt=prompt,
            verbose=os.getenv('VERBOSE')
        )
        inputs = {
            'query': query,
            'query_result': '\n\n'.join(query_result) if len(query_result) else '没有查到'
        }
        return retrival_chain.run(inputs)

    def graph_func(self, x, query):
        # 命名实体识别
        response_schemas = [
            ResponseSchema(type='list', name='disease', description='疾病名称实体'),
            ResponseSchema(type='list', name='symptom', description='疾病症状实体'),
            ResponseSchema(type='list', name='drug', description='药品名称实体'),
        ]
        output_parser = StructuredOutputParser(response_schemas=response_schemas)
        format_instructions = structured_output_parser(response_schemas)

        ner_prompt = PromptTemplate(
            template=NER_PROMPT_TPL,
            partial_variables={'format_instructions': format_instructions},
            input_variables=['query']
        )

        ner_chain = LLMChain(
            llm=get_llm_model(),
            prompt=ner_prompt,
            verbose=os.getenv('VERBOSE')
        )

        result = ner_chain.run({
            'query': query
        })

        ner_result = output_parser.parse(result)
        # print(ner_result)
        # exit()


        # 命名实体识别结果，填充模板
        graph_templates = []
        for key, template in GRAPH_TEMPLATE.items():
            slot = template['slots'][0]
            slot_values = ner_result[slot]
            # print(slot_values)
            # exit()
            for value in slot_values:
                graph_templates.append({
                    'question': replace_token_in_string(template['question'], {slot: value}),
                    'cypher': replace_token_in_string(template['cypher'], {slot: value}),
                    'answer': replace_token_in_string(template['answer'], {slot: value}),
                })
            # print(graph_templates)
            # exit()
        if not graph_templates:
            return

        # 计算问题相似度，筛选最相关问题
        graph_documents = [
            Document(page_content=template['question'], metadata=template)
            for template in graph_templates
        ]
        # print(graph_documents)
        # exit()
        db = FAISS.from_documents(graph_documents, get_embeddings_model())
        graph_documents_filter = db.similarity_search_with_relevance_scores(query, k=5)
        # print(graph_documents_filter)

        # 执行CQL，拿到结果
        query_result = []
        neo4j_conn = get_neo4j_conn()
        # result = neo4j_conn.run("CALL dbms.components() YIELD versions, name RETURN name, versions[0] as version").data()
        # if result:
        #     print(f"✅ Neo4j连接成功（py2neo）！")
        #     print(f"📌 数据库信息：{result[0]['name']} {result[0]['version']}")
        # print(neo4j_conn)
        for document in graph_documents_filter:
            question = document[0].page_content
            cypher = document[0].metadata['cypher']
            answer = document[0].metadata['answer']
            # print(cypher)
            try:
                result = neo4j_conn.run(cypher).data()
                if result and any(value for value in result[0].values()):
                    answer_str = replace_token_in_string(answer, list(result[0].items()))
                    # print(answer_str)
                    # exit()
                    query_result.append(f'问题: {question}\n答案: {answer_str}')
            except:
                pass
        print(query_result)
        # exit()

        # 总结答案
        prompt = PromptTemplate.from_template(GRAPH_PROMPT_TPL)
        graph_chain = LLMChain(
            llm=get_llm_model(),
            prompt=prompt,
            verbose=os.getenv('VERBOSE')
        )
        inputs = {
            'query': query,
            'query_result': "\n\n".join(query_result) if len(query_result) else "没有查到"
        }
        return graph_chain.run(inputs)

    def search_func(self, query):
        # // 网络搜索的模块
        prompt = PromptTemplate.from_template(SEARCH_PROMPT_TPL)
        llm_chain = LLMChain(
            llm=get_llm_model(),
            prompt=prompt,
            verbose=os.getenv('VERBOSE')
        )
        llm_request_chain = LLMRequestsChain(
            llm_chain=llm_chain,
            requests_key='query_result'
        )
        encoded_query = urllib.parse.quote(query)
        baidu_url = f'https://www.baidu.com/s?wd={encoded_query}&rn=10'
        c360_url = f'https://www.so.com/s?q='+query.replace(' ','+')
        inputs = {
            'query': query,
            # 'url': 'https://www.google.com/search?q=' + query.replace(' ', '+')
            'url': c360_url
        }
        return llm_request_chain.run(inputs)


    def parse_tools(self, tools, query):
        prompt = PromptTemplate.from_template(PARSE_TOOLS_PROMPT_TPL)
        llm_chain = LLMChain(
            llm=get_llm_model(),
            prompt=prompt,
            verbose=os.getenv('VERBOSE')
        )
        # 拼接工具描述参数
        tools_description = ''
        for tool in tools:
            tools_description += tool.name + ':' + tool.description + '\n'
        # print(tools_description)
        # exit()
        result = llm_chain.invoke({'tools_description': tools_description, 'query': query})
        # print(result)
        # exit()
        # 解析工具函数
        for tool in tools:
            if tool.name == result['text']:
                return tool
        return tools[0]

    def query(self, query):
        tools = [
            Tool.from_function(
                name="generic_func",
                func=lambda x: self.generic_func(x, query),
                description="可以解答通用领域的知识，例如打招呼、问你是谁等问题"
            ),
            Tool.from_function(
                name="retrival_func",
                func=lambda x: self.retrival_func(x, query),
                description="用于回答寻医问药网相关问题"
            ),
            Tool(
                name="graph_func",
                func=lambda x: self.graph_func(x, query),
                description="用于回答疾病、症状、药物等医疗相关问题"
            ),
            Tool(
                name="search_func",
                func=self.search_func,
                description="其他工具没有正确答案时，通过搜索引擎回答通用类问题"
            )
        ]
        # tool = self.parse_tools(tools,query=query)
        # return tool.func(query)

        prefix = '''请用中文，尽你所能回答以下的问题。

重要规则：
1. 当你有足够的信息来回答问题时，必须使用 "Final Answer: [你的答案]" 格式直接回答，不要再调用工具。
2. 只有当你需要使用工具获取更多信息时，才使用 "Action: [工具名称]" 格式。
3. 不要重复调用同一个工具。
4. 对于简单的问候，使用 generic_func 工具获取答案后，直接给出 Final Answer。

回答格式：
- 如果需要使用工具：Thought: [思考] Action: [工具名] Action Input: [输入]
- 如果可以直接回答：Thought: [思考] Final Answer: [答案]

您可以使用以下的工具：'''
        suffix = """Begin!

Question: {input}
Thought: {agent_scratchpad}"""

        agent_prompt = ZeroShotAgent.create_prompt(
            tools=tools,
            prefix=prefix,
            suffix=suffix,
            input_variables=['input', 'agent_scratchpad', 'chat_history']
        )

        llm_chain = LLMChain(llm=get_llm_model(), prompt=agent_prompt)
        agent = ZeroShotAgent(llm_chain=llm_chain)
        memory = ConversationBufferMemory(memory_key='chat_history')

        agent_chain = AgentExecutor.from_agent_and_tools(
            agent=agent,
            tools=tools,
            memory=memory,
            handle_parsing_errors=True,
            max_iterations=3,  # 限制最大迭代次数，防止无限循环
            verbose=os.getenv('VERBOSE')
        )
        return agent_chain.run({'input':query})

if __name__ == '__main__':
    agent = Agent()
    print("\n===== 查询结果 =====")
    # print(agent.retrival_func('介绍一下寻医问药网是什么'))

    print(agent.query('寻医问药网的客服电话是多少？'))
    # print(agent.generic_func('你叫什么名字？'))

    # print(agent.graph_func('化脓性鼻窦炎是鼻炎的并发症吗？'))
    # print(agent.graph_func('感冒一般是由什么引起的？'))
    # agent.graph_func('感冒吃什么药好得快？可以吃阿莫西林吗？')
    # 调用测试
    # print(agent.search_func('陈华编程都有什么课程'))
    # print(agent.query('你好'))
    # exit()
    # print(agent.query('寻医问药网获得过哪些投资'))
    # print(agent.query('鼻炎和感冒是并发症吗？'))
    # print(agent.query('鼻炎怎么治疗？'))
    # print(agent.query('烧橙子可以治感冒吗？'))