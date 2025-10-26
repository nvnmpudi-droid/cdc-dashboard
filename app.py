import streamlit as st
import pandas as pd
import os

# Existing imports from your current modules
from data_ingest import fetch_cdc_data
from processing import filter_recent_years
from analysis import summarize_covid_deaths
from dashboard import plot_covid_deaths
from summarization import ai_narrative_summary

# New imports for RAG + LangChain integration
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate

# -----------------------------------------
# SETUP: API Keys & Persistent Storage
# -----------------------------------------
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY", "your_api_key_here")
VECTOR_DB_DIR = "chroma_cdc_data"

# -----------------------------------------
# STREAMLIT UI SETUP
# -----------------------------------------
st.set_page_config(
    page_title="CDC AI Dashboard",
    page_icon="🧠",
    layout="wide"
)
st.title("🧠 CDC COVID-19 AI & RAG Dashboard")

st.sidebar.header("Configuration")
use_existing_db = st.sidebar.checkbox("Use existing Chroma vector DB (if already built)", value=True)

# -----------------------------------------
# SECTION 1: Load and Display CDC Data
# -----------------------------------------
st.header("📊 Step 1: Load Official CDC Mortality Data")

if st.button("Fetch and Preview CDC Data"):
    df = fetch_cdc_data()
    st.success("CDC Data Fetched Successfully!")
    st.write("Columns available:", df.columns.tolist())
    st.dataframe(df.head())

    # Filter and summarize
    df_filtered = filter_recent_years(df)
    summary = summarize_covid_deaths(df_filtered)

    st.subheader("Yearly COVID-19 Mortality Summary")
    st.dataframe(summary)
    st.pyplot(plot_covid_deaths(summary))

    ai_summary = ai_narrative_summary(summary)
    st.subheader("AI-Generated Summary")
    st.info(ai_summary)

# -----------------------------------------
# SECTION 2: Build or Load Vectorstore
# -----------------------------------------
st.header("🧮 Step 2: Build or Load Vector Database for RAG")

def build_chroma_vectorstore():
    df = pd.read_csv("cdc_data.csv")
    text_data = [
        f"{row['Year']}: {row['COVID-19 Deaths']} deaths"
        for _, row in df.iterrows() if 'Year' in df.columns
    ]
    splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=50)
    docs = splitter.create_documents(text_data)

    embeddings = OpenAIEmbeddings()
    vector_db = Chroma.from_documents(
        docs, embeddings, persist_directory=VECTOR_DB_DIR
    )
    vector_db.persist()
    return vector_db

def load_chroma_vectorstore():
    embeddings = OpenAIEmbeddings()
    return Chroma(persist_directory=VECTOR_DB_DIR, embedding_function=embeddings)

if st.button("🚀 Build / Load Chroma Database"):
    if use_existing_db and os.path.exists(VECTOR_DB_DIR):
        st.warning("Using existing vector database.")
        vectorstore = load_chroma_vectorstore()
    else:
        st.info("Building new Chroma vector store...")
        vectorstore = build_chroma_vectorstore()
    st.success("Vector store ready for semantic query!")

# -----------------------------------------
# SECTION 3: Interactive RAG Query Interface
# -----------------------------------------
st.header("💬 Step 3: Ask CDC Data Questions (RAG Engine)")

def create_rag_qa_chain(vectorstore):
    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
    prompt_template = """You are a CDC data analyst. 
Answer questions about COVID-19 mortality based on the following context.

Context:
{context}

Question: {question}

If unsure, say: 'I cannot find this specific data in CDC records.'

Answer:"""
    prompt = PromptTemplate.from_template(prompt_template)
    llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0)
    qa_chain = RetrievalQA.from_chain_type(
        llm=llm, 
        retriever=retriever,
        chain_type="stuff", 
        chain_type_kwargs={"prompt": prompt}
    )
    return qa_chain

query = st.text_input("Ask a data-driven question (e.g., 'Which year had the most COVID-19 deaths?')")
if st.button("🔍 Run RAG Query"):
    if not os.path.exists(VECTOR_DB_DIR):
        st.error("Vector database not found. Please build it first.")
    else:
        vectorstore = load_chroma_vectorstore()
        rag_chain = create_rag_qa_chain(vectorstore)
        response = rag_chain.run(query)
        st.subheader("🧠 CDC AI Response:")
        st.success(response)

# -----------------------------------------
# FOOTER
# -----------------------------------------
st.markdown("---")
st.caption("Built with ❤️ using Streamlit, LangChain, and CDC Open Data.")
