from SPARQLWrapper import SPARQLWrapper, JSON
from langchain_huggingface.embeddings import HuggingFaceEmbeddings

import faiss
import numpy as np

import streamlit as st
from langchain_core.messages import AIMessage, HumanMessage

from transformers import AutoModelForCausalLM, AutoTokenizer

embeddings = HuggingFaceEmbeddings()

falcon_tokenizer = AutoTokenizer.from_pretrained("tiiuae/falcon-7b-instruct")
falcon_model = AutoModelForCausalLM.from_pretrained("tiiuae/falcon-7b-instruct",
                                                    device_map="auto",
                                                    offload_folder="offload_folder",
                                                    )

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


#Generate Embeddings
kg_embeddings = []
for kg_triple in kg_triples:
    emb = embeddings.embed_query(kg_triple)
    kg_embeddings.append(emb)

kg_embeddings = np.array(kg_embeddings, dtype=np.float32)



# Index Embeddings with a Vector Database
d = kg_embeddings.shape[1]
index = faiss.IndexFlatL2(d)
index.add(kg_embeddings)

# Save the index and mappings
faiss.write_index(index, 'kg_index.faiss')
np.save('kg_triples.npy', kg_triples)

index = faiss.read_index('kg_index.faiss')
kg_triples = np.load('kg_triples.npy', allow_pickle=True)


def search_kg(query, top_k=5):
    query_embedding = embeddings.embed_query(query)
    query_embedding = np.array(query_embedding, dtype=np.float32)
    if len(query_embedding.shape) == 1:
        query_embedding = np.expand_dims(query_embedding, axis=0)

    distances, indices = index.search(query_embedding, top_k)
    return [kg_triples[i] for i in indices[0]]


def generate_response(user_query, max_length=1000):
    relevant_kg_elements = search_kg(user_query)

    prompt = f"Query: {user_query}\nRelevant Information: {', '.join(relevant_kg_elements)}\nAnswer:"

    inputs = falcon_tokenizer(prompt, return_tensors="pt")
    inputs.input_ids = inputs.input_ids.to("cuda")
    outputs = falcon_model.generate(inputs.input_ids, max_length=max_length, num_return_sequences=1)
    return falcon_tokenizer.decode(outputs[0], skip_special_tokens=True)


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