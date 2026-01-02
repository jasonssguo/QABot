import gradio as gr
from service import Service

def doctor_bot(message, history):
    service = Service()
    return service.answer(message, history)

CSS = """
.gradio-container {
    max-width: 850px !important;
    margin: 20px auto !important;
}
.message {
    padding: 10px !important;
    font-size: 14px !important;
}

/* 聊天框动态大小设置 */
.gradio-chatbot {
    height: calc(100vh - 300px) !important; /* 根据视窗高度动态调整 */
    min-height: 400px !important; /* 最小高度 */
    max-height: 80vh !important; /* 最大高度 */
    overflow-y: auto !important; /* 超出时显示滚动条 */
}

/* 响应式设计 - 小屏幕设备 */
@media (max-width: 768px) {
    .gradio-chatbot {
        height: calc(100vh - 350px) !important;
        min-height: 300px !important;
    }
    .gradio-container {
        max-width: 95% !important;
        margin: 10px auto !important;
    }
}

/* 大屏幕设备 */
@media (min-width: 1200px) {
    .gradio-chatbot {
        height: calc(100vh - 250px) !important;
        max-height: 120vh !important;
    }
}
"""

demo = gr.ChatInterface(
    css=CSS,
    fn=doctor_bot,
    title="医疗问诊机器人",
    chatbot=gr.Chatbot(height=800,bubble_full_width=True),
    theme=gr.themes.Default(spacing_size='sm', radius_size='sm'),
    textbox=gr.Textbox(
        placeholder="在此输入您的问题",
        container=False,
        scale=7
    ),
    examples=[
        "你好，你叫什么名字？",
        "介绍一下寻医问药网",
        "感冒是一种什么病？",
        "吃什么药好得快？"
    ],
    submit_btn=gr.Button('提交', variant='primary'),
    clear_btn=gr.Button('清空记录'),
    retry_btn=None,
    undo_btn=None
)

if __name__ =="__main__":
    demo.launch()