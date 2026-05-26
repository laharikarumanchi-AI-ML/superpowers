import os
from pathlib import Path
import streamlit as st
from agent.orchestrator import run
from agent.llm_client import GroqClient

DATASETS_DIR = Path(__file__).parent / "datasets"

st.set_page_config(page_title="Data Analysis Agent", layout="wide")
st.title("Data Analysis Agent")
st.caption("Ask a question about one of the example datasets. The agent will write and run Python to answer.")

csvs = sorted(DATASETS_DIR.glob("*.csv"))
choice = st.selectbox("Dataset", [c.name for c in csvs])
question = st.text_input("Your question", "What is the average of the first numeric column?")
go = st.button("Ask")

if go and question:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        st.error("GROQ_API_KEY not set in this environment.")
    else:
        with st.spinner("Thinking..."):
            llm = GroqClient(api_key=api_key)
            result = run(question, str(DATASETS_DIR / choice), llm)
        if result.success:
            st.success(result.answer)
        else:
            st.error(f"Agent failed: {result.failure_reason}")
        with st.expander("Trace"):
            for step in result.trace.steps:
                st.code(step.code or "(no code — final answer step)", language="python")
                if step.stdout:
                    st.text(step.stdout)
                if step.exception:
                    st.error(step.exception)
