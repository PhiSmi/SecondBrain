"""SecondBrain — Streamlit UI."""

import datetime

import streamlit as st

import db
import ingest
import query

st.set_page_config(page_title="SecondBrain", page_icon="🧠", layout="wide")


# ---------------------------------------------------------------------------
# Password gate
# ---------------------------------------------------------------------------

def _check_password() -> bool:
    correct = st.secrets.get("APP_PASSWORD")
    if not correct:
        return True
    if st.session_state.get("authenticated"):
        return True
    st.title("🧠 SecondBrain")
    pwd = st.text_input("Password", type="password")
    if st.button("Enter", type="primary"):
        if pwd == correct:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    return False


if not _check_password():
    st.stop()

st.title("🧠 SecondBrain")
st.caption("Your personal RAG-powered knowledge base")

tab_ingest, tab_ask, tab_sources = st.tabs(["Ingest", "Ask", "Sources"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tag_input(key: str, label: str = "Tags (comma-separated, optional)") -> list[str]:
    raw = st.text_input(label, key=key, placeholder="e.g. aws, architecture, reliability")
    return [t.strip() for t in raw.split(",") if t.strip()] if raw.strip() else []


def _build_export_md(question: str, result: dict) -> str:
    lines = [
        f"# {question}",
        f"*Exported from SecondBrain — {datetime.date.today()}*",
        "",
        "## Answer",
        result["answer"],
        "",
        "## Sources",
    ]
    for i, src in enumerate(result.get("sources", []), 1):
        lines.append(f"### {i}. {src['title']}")
        if src.get("url"):
            lines.append(f"**URL:** {src['url']}")
        lines.append(f"**Score:** {src.get('score', 'n/a')}")
        lines.append("")
        lines.append(src["text"][:500] + ("..." if len(src["text"]) > 500 else ""))
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# INGEST TAB
# ---------------------------------------------------------------------------

with tab_ingest:
    st.header("Add Knowledge")

    input_type = st.radio(
        "Input type",
        ["Paste text", "URL", "PDF", "YouTube", "Bulk URLs"],
        horizontal=True,
    )

    # ---- Paste text ----
    if input_type == "Paste text":
        title = st.text_input("Title", placeholder="e.g. AWS Well-Architected — Reliability Pillar")
        text = st.text_area("Paste content here", height=300)
        tags = _tag_input("tags_text")
        if st.button("Ingest", type="primary"):
            if not text.strip():
                st.error("Please paste some text.")
            elif not title.strip():
                st.error("Please provide a title.")
            else:
                with st.spinner("Chunking and embedding..."):
                    n = ingest.ingest_text(text, title=title.strip(), tags=tags)
                st.success(f"Ingested **{n}** chunks from \"{title.strip()}\"")

    # ---- Single URL ----
    elif input_type == "URL":
        url = st.text_input("URL", placeholder="https://example.com/article")
        title = st.text_input("Title (optional)", placeholder="Defaults to URL")
        tags = _tag_input("tags_url")
        if st.button("Ingest URL", type="primary"):
            if not url.strip():
                st.error("Please enter a URL.")
            else:
                with st.spinner("Fetching and processing..."):
                    try:
                        n, js_warn = ingest.ingest_url(url.strip(), title=title.strip() or None, tags=tags)
                        if js_warn:
                            st.warning(
                                f"Only extracted a small amount of text ({n} chunk(s)). "
                                "This page likely requires JavaScript — try **Paste text** instead."
                            )
                        else:
                            st.success(f"Ingested **{n}** chunks.")
                    except Exception as e:
                        st.error(f"Failed: {e}")

    # ---- PDF ----
    elif input_type == "PDF":
        uploaded = st.file_uploader("Upload a PDF", type="pdf")
        title = st.text_input("Title", placeholder="e.g. AWS Security Whitepaper")
        tags = _tag_input("tags_pdf")
        if st.button("Ingest PDF", type="primary"):
            if uploaded is None:
                st.error("Please upload a PDF file.")
            elif not title.strip():
                st.error("Please provide a title.")
            else:
                with st.spinner("Extracting and embedding..."):
                    n = ingest.ingest_pdf(uploaded.read(), title=title.strip(), tags=tags)
                st.success(f"Ingested **{n}** chunks from \"{title.strip()}\"")

    # ---- YouTube ----
    elif input_type == "YouTube":
        url = st.text_input("YouTube URL", placeholder="https://www.youtube.com/watch?v=...")
        title = st.text_input("Title (optional)", placeholder="Defaults to URL")
        tags = _tag_input("tags_yt")
        st.caption("Uses the video's auto-generated or community transcript. No audio processing needed.")
        if st.button("Ingest transcript", type="primary"):
            if not url.strip():
                st.error("Please enter a YouTube URL.")
            else:
                with st.spinner("Fetching transcript..."):
                    try:
                        n = ingest.ingest_youtube(url.strip(), title=title.strip() or None, tags=tags)
                        st.success(f"Ingested **{n}** chunks from transcript.")
                    except Exception as e:
                        st.error(f"Failed: {e}")

    # ---- Bulk URLs ----
    else:
        urls_raw = st.text_area("URLs (one per line)", height=200, placeholder="https://example.com/a\nhttps://example.com/b")
        tags = _tag_input("tags_bulk")
        if st.button("Ingest all", type="primary"):
            urls = [u.strip() for u in urls_raw.splitlines() if u.strip()]
            if not urls:
                st.error("Please enter at least one URL.")
            else:
                with st.spinner(f"Ingesting {len(urls)} URLs..."):
                    results = ingest.ingest_bulk_urls(urls, tags=tags)
                for r in results:
                    if r["error"]:
                        st.error(f"❌ {r['url']} — {r['error']}")
                    elif r["warning"]:
                        st.warning(f"⚠️ {r['url']} — {r['chunks']} chunks (JS-rendered, content may be partial)")
                    else:
                        st.success(f"✓ {r['url']} — {r['chunks']} chunks")


# ---------------------------------------------------------------------------
# ASK TAB
# ---------------------------------------------------------------------------

with tab_ask:
    st.header("Ask Your Knowledge Base")

    # Sidebar-style options inside the tab
    with st.expander("Search options", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            use_hybrid = st.toggle("Hybrid search (BM25 + semantic)", value=True,
                                   help="Combines keyword and semantic search for better recall")
            use_rerank = st.toggle("Reranking", value=False,
                                   help="Cross-encoder reranks retrieved chunks for higher precision. Uses extra ~85MB RAM.")
        with col2:
            all_tags = db.get_all_tags()
            selected_tags = st.multiselect("Filter by tags", options=all_tags,
                                           help="Leave empty to search all sources")

    question = st.text_input("Your question", placeholder="What are the key reliability design principles?")

    col_ask, col_clear = st.columns([1, 5])
    with col_ask:
        ask_clicked = st.button("Ask", type="primary")
    with col_clear:
        if st.button("Clear conversation"):
            st.session_state.pop("chat_history", None)
            st.rerun()

    # Conversation history lives in session state
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    if ask_clicked:
        if not question.strip():
            st.error("Please enter a question.")
        else:
            with st.spinner("Searching and generating answer..."):
                result = query.ask(
                    question.strip(),
                    history=st.session_state["chat_history"],
                    tags=selected_tags or None,
                    use_rerank=use_rerank,
                    hybrid=use_hybrid,
                )
            st.session_state["chat_history"] = result["history"]

            # Store last result for export
            st.session_state["last_result"] = result
            st.session_state["last_question"] = question.strip()

    # Display full conversation
    if st.session_state["chat_history"]:
        st.markdown("---")
        turns = st.session_state["chat_history"]
        for i in range(0, len(turns) - 1, 2):
            user_msg = turns[i]["content"]
            asst_msg = turns[i + 1]["content"] if i + 1 < len(turns) else ""
            st.markdown(f"**You:** {user_msg}")
            st.markdown(asst_msg)
            st.markdown("")

        # Show sources for the last answer
        last = st.session_state.get("last_result")
        if last and last.get("sources"):
            st.markdown("---")
            st.markdown("**Sources used for last answer**")
            for i, src in enumerate(last["sources"], 1):
                score = src.get("score", 0)
                with st.expander(f"Source {i}: {src['title']} (score: {score})"):
                    if src["url"]:
                        st.markdown(f"**URL:** {src['url']}")
                    st.text(src["text"][:500] + ("..." if len(src["text"]) > 500 else ""))

        # Export last answer
        last_result = st.session_state.get("last_result")
        last_q = st.session_state.get("last_question", "")
        if last_result:
            md = _build_export_md(last_q, last_result)
            st.download_button(
                label="Export last answer as Markdown",
                data=md,
                file_name=f"secondbrain_{datetime.date.today()}.md",
                mime="text/markdown",
            )


# ---------------------------------------------------------------------------
# SOURCES TAB
# ---------------------------------------------------------------------------

with tab_sources:
    st.header("Ingested Sources")

    all_tags_filter = db.get_all_tags()
    filter_tags = st.multiselect("Filter by tag", options=all_tags_filter, key="src_filter_tags")
    sources = db.get_all_sources()

    if filter_tags:
        sources = [s for s in sources if any(t in s["tags"] for t in filter_tags)]

    if not sources:
        st.info("No sources ingested yet.")
    else:
        for src in sources:
            with st.expander(f"{src['title']}  —  {src['chunk_count']} chunks  |  {src['source_type']}  |  {src['ingested_at'][:10]}"):
                col1, col2 = st.columns([3, 1])
                with col1:
                    if src.get("url"):
                        st.caption(src["url"])
                    # Tags editor
                    current_tags = ", ".join(src.get("tags") or [])
                    new_tags_raw = st.text_input("Tags", value=current_tags, key=f"tags_{src['id']}")
                    if st.button("Save tags", key=f"save_tags_{src['id']}"):
                        new_tags = [t.strip() for t in new_tags_raw.split(",") if t.strip()]
                        db.update_source_tags(src["id"], new_tags)
                        st.success("Tags updated.")
                        st.rerun()

                with col2:
                    st.metric("Chunks", src["chunk_count"])

                    if st.button("Summarise", key=f"sum_{src['id']}"):
                        with st.spinner("Summarising..."):
                            summary = query.summarise_source(src["id"])
                        st.markdown(summary)

                    if st.button("Re-ingest", key=f"reingest_{src['id']}",
                                 help="Re-embed all chunks (e.g. after switching embedding model)"):
                        with st.spinner("Re-embedding..."):
                            n = ingest.reingest_source(src["id"])
                        st.success(f"Re-ingested {n} chunks.")
                        st.rerun()

                    if st.button("Delete", key=f"del_{src['id']}",
                                 type="secondary"):
                        ingest.delete_source(src["id"])
                        st.rerun()

                # View chunks
                if st.checkbox("View chunks", key=f"chunks_{src['id']}"):
                    chunks = db.get_chunks_for_source(src["id"])
                    for c in chunks:
                        st.text_area(
                            f"Chunk {c['chunk_index']}",
                            value=c["text"],
                            height=120,
                            disabled=True,
                            key=f"chunk_text_{c['id']}",
                        )
