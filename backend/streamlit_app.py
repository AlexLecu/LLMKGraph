import os

from langchain_community.graphs import OntotextGraphDBGraph
from langchain.chains import OntotextGraphDBQAChain
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, HumanMessage

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

openai_api_key = os.environ['OPENAI_API_KEY']

os.environ["GRAPHDB_USERNAME"] = "admin"
os.environ["GRAPHDB_PASSWORD"] = "root"

graph = OntotextGraphDBGraph(
    query_endpoint="http://localhost:7200/repositories/amd_repo",
    query_ontology="CONSTRUCT {?s ?p ?o} FROM <http://amddata.org/amd/> WHERE {?s ?p ?o}",
)

llm = ChatOpenAI(temperature=0.5, model_name="gpt-4-1106-preview")

chain = OntotextGraphDBQAChain.from_llm(
    llm,
    graph=graph,
    verbose=True,
)


def get_response(user_input):
    return chain.invoke({chain.input_key: user_input})[chain.output_key]


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
    response = get_response(user_query)
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
