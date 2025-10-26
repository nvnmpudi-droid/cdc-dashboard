# vector_database.py
# Handle CDC data embeddings and store/query vectors.

from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings

def init_vector_db(persist_dir="chroma_db"):
    return Chroma(persist_directory=persist_dir, embedding_function=OpenAIEmbeddings())

def add_texts_to_db(vector_db, texts, ids=None):
    vector_db.add_texts(texts=texts, ids=ids)

def query_vector_db(vector_db, query_text, top_n=3):
    results = vector_db.similarity_search(query_text, k=top_n)
    return [r.page_content for r in results]
