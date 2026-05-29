"""
检索模块：封装向量库检索接口。
"""

from src.rag.vector_store import SimpleVectorStore


class Retriever:
    """案例检索器。"""

    def __init__(self, store: SimpleVectorStore):
        self.store = store

    def retrieve(self, query_vector, top_k: int = 3):
        return self.store.search(query_vector, top_k=top_k)
