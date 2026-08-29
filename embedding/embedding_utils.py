"""
embedding/embedding_utils.py

Wraps the sentence-transformers model for generating job posting embeddings.
"""

import streamlit as st
from sentence_transformers import SentenceTransformer

@st.cache_resource
def get_model():
    return SentenceTransformer("all-MiniLM-L6-v2")

def embed_text(text: str):
    model = get_model()
    return model.encode(text).tolist()