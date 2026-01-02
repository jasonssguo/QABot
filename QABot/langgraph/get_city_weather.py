import sys
import os
# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import *
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

@tool
def get_weather(city: str) -> str:
    """获取指定城市的天气信息。

    Args:
        city: 城市名称

    Returns:
        返回该城市的天气描述
    """
    return f"今天{city}是晴天"

def main():
    # 创建模型
    model = get_llm_model()

    # 使用LangGraph提供的API创建Agent
    agent = create_react_agent(
        model=model,          # 添加模型
        tools=[get_weather],  # 添加工具
        prompt="你是一个天气助手，可以帮助用户查询天气信息。"
    )

    # 创建用户消息
    human_message = HumanMessage(content="今天深圳天气怎么样？")

    # 调用agent
    response = agent.invoke(
        {"messages": [human_message]}
    )

    print("最终回答:", response["messages"][-1].content)

if __name__ == "__main__":
    main()
