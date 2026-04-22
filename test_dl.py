import streamlit as st
def get_data():
    return b"test"
st.download_button("dl", data=get_data, file_name="t.txt")
