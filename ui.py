import streamlit as st
import time
from typing import List, Dict, Any
from datetime import datetime
from src.the_preview.crew import ThePreview
from dotenv import load_dotenv

# Load Agent model config
load_dotenv(".env")

# Page configuration
st.set_page_config(
    page_title="The Previews",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# background-color: #e3f2fd;
# .chat-message.assistant {
#     background-color: #f5f5f5;
# }

# Custom CSS for better chat appearance
st.markdown(
    """
<style>
    .chat-message {
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 1rem;
        display: flex;
        align-items: flex-start;
    }
    
    .chat-message.user {
        flex-direction: row-reverse;
    }
    
    .chat-message .avatar {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        margin: 0 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        color: white;
    }
    
    .chat-message.user .avatar {
        background-color: #1976d2;
    }
    
    .chat-message.assistant .avatar {
        background-color: #424242;
    }
    
    .chat-message .message {
        flex: 1;
        padding: 0 10px;
    }
    
    .stTextInput > div > div > input {
        border-radius: 20px;
    }
</style>
""",
    unsafe_allow_html=True,
)


# Initialize session state for messages
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.crew = ThePreview().crew()

st.title("The Previews")

# Display past messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Chat input box
if user_input := st.chat_input("Movie title..."):
    # Add user's message to history
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Generate CrewAI response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                response = st.session_state.crew.kickoff({"movie_title": user_input})
            except Exception as e:
                response = f"⚠️ Error: {e}"

            st.markdown(response)

    # Add assistant's response to history
    st.session_state.messages.append({"role": "assistant", "content": response})
