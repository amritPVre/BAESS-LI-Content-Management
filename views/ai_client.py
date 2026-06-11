"""Shared DeepSeek API client for all generator pages."""

import streamlit as st
from openai import OpenAI


def get_api_key() -> str:
    if st.session_state.get("api_key"):
        key = st.session_state.api_key
        if key and key != "PASTE_YOUR_DEEPSEEK_API_KEY_HERE":
            return key
    try:
        key = st.secrets["DEEPSEEK_API_KEY"]
        if key and key != "PASTE_YOUR_DEEPSEEK_API_KEY_HERE":
            st.session_state.api_key = key
            return key
    except (KeyError, AttributeError, FileNotFoundError):
        pass
    return ""


def call_ai(system_prompt: str, user_prompt: str, max_tokens: int = 600) -> str:
    api_key = get_api_key()
    if not api_key:
        st.error("DeepSeek API key not found. Add DEEPSEEK_API_KEY to .streamlit/secrets.toml")
        return ""
    try:
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        resp = client.chat.completions.create(
            model="deepseek-chat",
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        st.error(f"AI error: {e}")
        return ""
