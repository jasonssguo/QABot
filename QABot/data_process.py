# data_process.py
from utils import *
import os
from glob import glob
from langchain.vectorstores.chroma import Chroma
from langchain.document_loaders import CSVLoader, PyMuPDFLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

def doc2vec():
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=400,
        chunk_overlap=50
    )

    # 获取当前脚本所在目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # 拼接数据目录路径，使用os.path.join自动适配系统斜杠
    dir_path = os.path.join(current_dir, 'data', 'input')
    # 确保路径末尾有目录分隔符（可选，glob不影响）
    dir_path = os.path.join(dir_path, '')  # 结果如：G:\xxx\data\input\
    documents = []
    for file_path in glob(dir_path + '*.*'):
        loader = None
        if '.csv' in file_path:
            loader = CSVLoader(file_path, encoding='utf-8')
        if '.pdf' in file_path:
            loader = PyMuPDFLoader(file_path)
        if '.txt' in file_path:
            loader = TextLoader(file_path, encoding='utf-8')
        if loader:
            documents += loader.load_and_split(text_splitter)
    # print(len(documents))
    # 向量化并存储：
    if documents:
        vdb = Chroma.from_documents(
            documents=documents,
            embedding=get_embeddings_model(),
            persist_directory=os.path.join(os.path.dirname(__file__), './data/db/')
        )
        vdb.persist()

if __name__ == '__main__':
    doc2vec()