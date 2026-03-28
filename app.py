"""Streamlit UI for SecondBrain — ingest content and ask questions."""

import streamlit as st

import db
import ingest
import query

st.set_page_config(page_title="SecondBrain", page_icon="🧠", layout="wide")
st.title("🧠 SecondBrain")
st.caption("Your personal RAG-powered knowledge base")

tab_ingest, tab_query, tab_sources = st.tabs(["Ingest", "Ask", "Sources"])

# ---------------------------------------------------------------------------
# Ingest tab
# ---------------------------------------------------------------------------
with tab_ingest:
    st.header("Add Knowledge")

    input_type = st.radio("Input type", ["Paste text", "URL"], horizontal=True)

    if input_type == "Paste text":
        title = st.text_input("Title / label for this content", placeholder="e.g. AWS Well-Architected Framework - Reliability Pillar")
        text = st.text_area("Paste your text here", height=300)

        if st.button("Ingest text", type="primary"):
            if not text.strip():
                st.error("Please paste some text first.")
            elif not title.strip():
                st.error("Please provide a title.")
            else:
                with st.spinner("Chunking and embedding..."):
                    chunk_count = ingest.ingest_text(text, title=title.strip())
                st.success(f"Ingested **{chunk_count}** chunks from \"{title.strip()}\"")

    else:
        url = st.text_input("URL to ingest", placeholder="https://example.com/article")
        title = st.text_input("Title (optional — defaults to URL)", placeholder="e.g. Martin Fowler on Event-Driven Architecture")

        if st.button("Ingest URL", type="primary"):
            if not url.strip():
                st.error("Please enter a URL.")
            else:
                with st.spinner("Fetching and processing..."):
                    try:
                        chunk_count = ingest.ingest_url(url.strip(), title=title.strip() or None)
                        st.success(f"Ingested **{chunk_count}** chunks from {url.strip()}")
                    except Exception as e:
                        st.error(f"Failed to ingest URL: {e}")

# ---------------------------------------------------------------------------
# Query tab
# ---------------------------------------------------------------------------
with tab_query:
    st.header("Ask Your Knowledge Base")

    question = st.text_input("Your question", placeholder="What are the key principles of the reliability pillar?")

    if st.button("Ask", type="primary"):
        if not question.strip():
            st.error("Please enter a question.")
        else:
            with st.spinner("Searching and generating answer..."):
                result = query.ask(question.strip())

            st.markdown("### Answer")
            st.markdown(result["answer"])

            if result["sources"]:
                st.markdown("---")
                st.markdown("### Sources")
                for i, src in enumerate(result["sources"], 1):
                    with st.expander(f"Source {i}: {src['title']} (similarity: {src['similarity']})"):
                        if src["url"]:
                            st.markdown(f"**URL:** {src['url']}")
                        st.text(src["text"][:500] + ("..." if len(src["text"]) > 500 else ""))

# ---------------------------------------------------------------------------
# Sources tab
# ---------------------------------------------------------------------------
with tab_sources:
    st.header("Ingested Sources")

    sources = db.get_all_sources()

    if not sources:
        st.info("No sources ingested yet. Go to the Ingest tab to add content.")
    else:
        for src in sources:
            col1, col2, col3 = st.columns([4, 2, 1])
            with col1:
                st.markdown(f"**{src['title']}**")
                if src["url"]:
                    st.caption(src["url"])
            with col2:
                st.caption(f"{src['chunk_count']} chunks | {src['source_type']} | {src['ingested_at'][:10]}")
            with col3:
                if st.button("Delete", key=f"del_{src['id']}"):
                    db.delete_source(src["id"])
                    st.rerun()
