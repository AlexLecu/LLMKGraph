from langchain_huggingface.embeddings import HuggingFaceEmbeddings
from langchain.prompts import PromptTemplate
from langchain_core.messages import AIMessage, HumanMessage
from langchain import HuggingFaceHub, PromptTemplate, LLMChain

from SPARQLWrapper import SPARQLWrapper, JSON

import os
import faiss
import numpy as np
import streamlit as st
import re


huggingfacehub_api_token = os.environ['HUGGINGFACEHUB_API_TOKEN']

embeddings = HuggingFaceEmbeddings()
repo_id = "tiiuae/falcon-7b-instruct"
llm = HuggingFaceHub(huggingfacehub_api_token=huggingfacehub_api_token,
                     repo_id=repo_id,
                     model_kwargs={"temperature":0.6, "max_new_tokens":2000})


def extract_data():
    #Extract Data from GraphDB
    sparql = SPARQLWrapper("http://localhost:7200/repositories/amd_repo")

    sparql.setQuery("""
        SELECT ?subject ?predicate ?object
        WHERE {
            ?subject ?predicate ?object
        }
        LIMIT 1000
    """)

    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()

    kg_triples = []
    for result in results["results"]["bindings"]:
        subject = result["subject"]["value"]
        predicate = result["predicate"]["value"]
        object = result["object"]["value"]
        kg_triples.append(f"{subject} {predicate} {object}")

    return kg_triples


def generate_embeddings(kg_triples):
    #Generate Embeddings
    kg_embeddings = []
    for kg_triple in kg_triples:
        emb = embeddings.embed_query(kg_triple)
        kg_embeddings.append(emb)

    kg_embeddings = np.array(kg_embeddings, dtype=np.float32)

    return kg_embeddings


def index_embeddings(kg_embeddings, kg_triples):
    # Index Embeddings with a Vector Database
    d = kg_embeddings.shape[1]
    index = faiss.IndexFlatL2(d)
    index.add(kg_embeddings)

    # Save the index and mappings
    faiss.write_index(index, 'embeddings/kg_index.faiss')
    np.save('embeddings/kg_triples.npy', kg_triples)


def search_kg(query, top_k=5):
    index = faiss.read_index('embeddings/kg_index.faiss')
    kg_triples = np.load('embeddings/kg_triples.npy', allow_pickle=True)

    query_embedding = embeddings.embed_query(query)
    query_embedding = np.array(query_embedding, dtype=np.float32)
    if len(query_embedding.shape) == 1:
        query_embedding = np.expand_dims(query_embedding, axis=0)

    distances, indices = index.search(query_embedding, top_k)
    return [kg_triples[i] for i in indices[0]]


def factory():
    prompt_template = """
            Answer the question as detailed as possible from the provided context, make sure to provide all the details, if the answer is not in
            provided context just say, "answer is not available in the context", don't provide the wrong answer\n\n
            Context:\n {context}?\n
            Question: \n{question}\n

            Answer:
            """

    prompt = PromptTemplate(template=prompt_template, input_variables=["context", "question"])
    llm_chain = LLMChain(prompt=prompt, llm=llm, verbose=True)

    return llm_chain, prompt


def generate_response(user_query):
    relevant_kg_elements = search_kg(user_query)
    llm_chain, prompt = factory()

    inputs = {
        "context": relevant_kg_elements,
        "question": user_query
    }

    output = llm_chain.run(inputs)
    answer = output.split("Answer:")[1].strip()
    cleaned_answer = re.sub(r'^<[^>]+>|<[^>]+>$', '', answer)

    return cleaned_answer


def streamlit_ui():
    # App config
    st.set_page_config(page_title="Chat with AMD_KG", page_icon="🤖")
    st.title("Chat with AMD_KG")
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = [
            AIMessage(content="Hello, I am a bot. How can I help you?"),
        ]

    # User input
    user_query = st.chat_input("Type your message here...")
    if user_query is not None and user_query != "":
        response = generate_response(user_query)
        st.session_state.chat_history.append(HumanMessage(content=user_query))
        st.session_state.chat_history.append(AIMessage(content=response))

    # Conversation
    for message in st.session_state.chat_history:
        if isinstance(message, AIMessage):
            with st.chat_message("AI"):
                st.write(message.content)
        elif isinstance(message, HumanMessage):
            with st.chat_message("Human"):
                st.write(message.content)


if __name__ == "__main__":
    streamlit_ui()
