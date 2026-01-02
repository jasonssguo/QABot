from prompt import *
from utils import *
from agent import *
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate

class Service:
    def __init__(self):
        self.agent = Agent()

    def get_summary_message(self, message, history):
        llm = get_llm_model()
        prompt = PromptTemplate.from_template(SUMMARY_PROMPT_TPL)
        llm_chain = LLMChain(
            llm=llm,
            prompt=prompt,
            verbose=os.getenv('VERBOSE')
        )
        chat_history = ''
        for q, a in history[-2:]:
            chat_history += f'问题：{q}, 答案：{a}\n'
        return llm_chain.run(query=message, chat_history=chat_history)

    def answer(self, message, history):
        if history:
            message = self.get_summary_message(message=message, history=history)
            print(f'---message---{message}')
        return self.agent.query(message)


if __name__ == '__main__':
    service = Service()
    # print(service.answer('你好',[]))
    # print(service.answer('得了鼻炎怎么办？',[['你好','你好！我是一个由阿磊编程打造的医疗问诊机器人。有什么可以帮助您的吗？']]))
    print(service.answer('大概多长时间能治好？',[
        ['你好','你好！我是一个由阿磊编程打造的医疗问诊机器人。有什么可以帮助您的吗？'],
        ['得了鼻炎怎么办','得了鼻炎，关键在于**及时到耳鼻喉科就诊**，在医生指导下进行检查和治疗，并配合长期的日常保 健与预防措施来控制病情']
    ]))