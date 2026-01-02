# utils.py
from langchain.embeddings import DashScopeEmbeddings
from langchain.chat_models import ChatOpenAI
from requests import auth
from neo4j import GraphDatabase, exceptions
from py2neo import Graph
from config import *
import os
import erniebot
from dotenv import load_dotenv
import requests

load_dotenv()


class BaiduEmbeddings:
    def __init__(self):
        erniebot.api_type = os.getenv('ERNIEBOT_API_TYPE')
        erniebot.access_token = os.getenv('ERNIEBOT_API_KEY')
    @staticmethod
    def embed_documents(texts):
        resp = erniebot.Embedding.create(
            model=os.getenv('BAIDU_EMBEDDINGS_MODEL'),
            input=texts
        )
        return [item['embedding'] for item in resp['data']]

    def embed_query(self, text):
        return self.embed_documents([text])[0]

    def __call__(self, text):
        return self.embed_query(text)


# def get_embeddings_model():
#     embedding = BaiduEmbeddings()
#     return embedding

def get_embeddings_model():
    return DashScopeEmbeddings(
        model = os.getenv('BAILIAN_EMBEDDINGS_MODEL')
    )

def get_llm_model():
    model_map = {
        "deepseek": ChatOpenAI(
            model=os.getenv('DP_LLM_MODEL'),
            temperature=os.getenv('TEMPERATURE'),
            max_tokens=os.getenv('MAX_TOKENS'),
            api_key=os.getenv('DeepSeek_API_KEY'),
            base_url=os.getenv('DeepSeek_BASE_URL')
        )
    }
    return model_map.get(os.getenv('LLM_MODEL'))

def structured_output_parser(response_schemas):
    text = '''
请从以下文本中，抽取出实体信息，并按json格式输出，json包含首尾的"```json"和"```"。

以下是字段含义和类型，要求输出json中，必须包含下列所有字段：
'''
    for schema in response_schemas:
        text += schema.name + ' 字段，表示: ' + schema.description + ', 类型为: ' + schema.type + '\n'
    return text

# 该函数用于将字符串中的占位符替换为实际的值
def replace_token_in_string(string, slots):
    # 如果 slots 是列表，转换为字典
    if isinstance(slots, list):
        slots = dict(slots)
    
    for key, value in slots.items():
        string = string.replace('%' + key + '%', value)
    return string


def get_neo4j_conn():
    return Graph(
        os.getenv('NEO4J_URI'),
        auth = (os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD"))
    )

def check_neo4j_connection():
    """
    验证Neo4j连接是否成功（基于py2neo）
    返回：布尔值（True=连接成功，False=连接失败）
    """
    try:
        # 获取Graph连接对象
        graph = get_neo4j_conn()
        
        # 方式1：执行轻量查询验证连接（推荐，能覆盖密码过期、权限等问题）
        # 查询Neo4j数据库版本（py2neo的Graph.run返回Cursor对象，需用data()获取结果）
        result = graph.run("CALL dbms.components() YIELD versions, name RETURN name, versions[0] as version").data()
        if result:
            print(f"✅ Neo4j连接成功（py2neo）！")
            print(f"📌 数据库信息：{result[0]['name']} {result[0]['version']}")
        
        # 方式2：可选的轻量验证（仅检查连接是否可达，不验证权限）
        # graph.verify_connectivity()  # py2neo 2021.0+版本支持该方法
        
        return True
    except ValueError as e:
        # 捕获环境变量缺失的错误
        print(f"❌ 连接失败：{e}")
        return False
    except exceptions.AuthError as e:
        # 捕获认证错误（用户名/密码错误、密码过期）
        print(f"❌ Neo4j认证失败：{str(e)}")
        return False
    except exceptions.ConnectionError as e:
        # 捕获连接错误（端口错误、服务未启动、URI错误）
        print(f"❌ Neo4j连接失败：{str(e)}")
        return False
    except Exception as e:
        # 捕获其他通用错误
        print(f"❌ 连接失败：{str(e)}")
        return False

if __name__ == '__main__':
    # llm_model = get_llm_model()
    # print(llm_model.predict("你是谁"))
    check_neo4j_connection()