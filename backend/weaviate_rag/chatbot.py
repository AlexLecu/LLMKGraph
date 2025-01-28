import streamlit as st
import requests
import json
import logging
from rag_system import KGRAGSystem
from typing import Dict

logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("weaviate").setLevel(logging.WARNING)

OLLAMA_HOST = "http://localhost:11434"
MODEL_NAME = "deepseek-r1"
MAX_HISTORY = 3


class ChatManager:
    def __init__(self):
        self.rag = None
        self.init_session_state()

    def init_session_state(self):
        if "messages" not in st.session_state:
            st.session_state.messages = []
        if "rag" not in st.session_state:
            try:
                st.session_state.rag = KGRAGSystem()
            except Exception as e:
                st.error(f"Failed to initialize RAG system: {str(e)}")
                st.stop()

    def get_conversation_history(self) -> str:
        return "\n".join(
            f"{msg['role'].capitalize()}: {msg['content']}"
            for msg in st.session_state.messages[-MAX_HISTORY * 2:]
        )

    def generate_response(self, prompt: str) -> str:
        try:
            kg_result = st.session_state.rag.query(prompt)

            if kg_result.get("error"):
                return f"Knowledge retrieval error: {kg_result['error']}"

            llm_prompt = f"""
            You are a helpful, expert-level medical research assistant. 
            You have access to additional relevant data:
            
            {kg_result.get('context', 'No further information is available.')}
            
            Here is the current conversation:
            
            {self.get_conversation_history()}
            
            The user asks:
            
            {prompt}
            
            Please provide a detailed yet concise answer, observing these guidelines:
            1. Draw upon any relevant data you have to support your answer.
            2. Cite sources only if they are specifically referenced in your data. 
               - Use a simple reference style (e.g., "[Source]") and place it naturally within your text.
            3. If you lack enough information to answer confidently, say so and explain what is missing.
            4. Do not fabricate references or information.
            
            Deliver your response in a clear, professional tone, focusing on accuracy and helpfulness.
            """

            response = requests.post(
                f"{OLLAMA_HOST}/api/chat",
                json={
                    "model": MODEL_NAME,
                    "messages": [{"role": "user", "content": llm_prompt}],
                    "stream": True
                },
                stream=True
            )

            return self.handle_streaming_response(response, kg_result)

        except requests.exceptions.ConnectionError:
            st.error("Ollama service unavailable. Start it with `ollama serve`")
            st.stop()
        except Exception as e:
            logging.error(f"Response generation failed: {str(e)}", exc_info=True)
            return f"Error processing request: {str(e)}"

    def handle_streaming_response(self, response, kg_result: Dict) -> str:
        full_response = ""
        message_placeholder = st.empty()

        try:
            for line in response.iter_lines():
                if line:
                    chunk = json.loads(line.decode())
                    if "message" in chunk:
                        content = chunk["message"].get("content", "")
                        full_response += content
                        message_placeholder.markdown(full_response + "▌")

            sources = kg_result.get("sources", [])
            if sources:
                sources_section = "\n\n**Sources:**\n" + "\n".join(f"- {src}" for src in sources)
                full_response += sources_section

                message_placeholder.markdown(full_response)

            return full_response

        except Exception as e:
            logging.error(f"Stream processing error: {str(e)}", exc_info=True)
            return "Error processing streaming response"


def main():
    st.set_page_config(
        page_title="Medical Research Chat",
        page_icon="⚕️",
        layout="wide"
    )

    chat_manager = ChatManager()

    st.title("Medical Research Assistant")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if "sources" in msg and msg["sources"]:
                with st.expander("References"):
                    st.write("\n".join(f"- {src}" for src in msg["sources"]))

    if prompt := st.chat_input("Ask about medical research..."):
        with st.chat_message("user"):
            st.markdown(prompt)

        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.chat_message("assistant"):
            response = chat_manager.generate_response(prompt)

        st.session_state.messages.append({
            "role": "assistant",
            "content": response
        })


if __name__ == "__main__":
    main()
