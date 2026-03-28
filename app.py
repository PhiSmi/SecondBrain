"""SecondBrain — Streamlit UI."""

import datetime
import json

import streamlit as st

import config
import db
import ingest
import query

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
_brand = config.branding()
st.set_page_config(
    page_title=_brand.get("page_title", "SecondBrain"),
    page_icon=_brand.get("favicon", "🧠"),
    layout="wide",
)

# ---------------------------------------------------------------------------
# Custom CSS — professional dark theme
# ---------------------------------------------------------------------------
_theme = config.theme()
_css = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* ---- Global ---- */
.stApp {{
    font-family: {_theme.get("font_family", "Inter, sans-serif")};
}}

/* ---- Header gradient ---- */
.app-header {{
    background: linear-gradient(135deg, {_theme["gradient_start"]} 0%, {_theme["gradient_end"]} 100%);
    padding: 2rem 2.5rem;
    border-radius: 16px;
    margin-bottom: 1.5rem;
    box-shadow: 0 8px 32px rgba(108, 92, 231, 0.15);
}}
.app-header h1 {{
    color: white;
    font-size: 2.2rem;
    font-weight: 700;
    margin: 0 0 0.3rem 0;
    letter-spacing: -0.5px;
}}
.app-header p {{
    color: rgba(255, 255, 255, 0.85);
    font-size: 1.05rem;
    margin: 0;
    font-weight: 300;
}}

/* ---- Metric cards ---- */
.metric-card {{
    background: linear-gradient(145deg, {_theme["surface_color"]}, {_theme["surface_hover"]});
    border: 1px solid {_theme["border_color"]};
    border-radius: 12px;
    padding: 1.2rem 1.5rem;
    text-align: center;
    transition: transform 0.2s, box-shadow 0.2s;
}}
.metric-card:hover {{
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(108, 92, 231, 0.12);
}}
.metric-card .metric-value {{
    font-size: 2.2rem;
    font-weight: 700;
    background: linear-gradient(135deg, {_theme["primary_color"]}, {_theme["secondary_color"]});
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    line-height: 1.2;
}}
.metric-card .metric-label {{
    font-size: 0.85rem;
    color: {_theme["text_secondary"]};
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-top: 0.3rem;
}}

/* ---- Workspace badge ---- */
.workspace-badge {{
    display: inline-block;
    background: linear-gradient(135deg, {_theme["primary_color"]}22, {_theme["secondary_color"]}22);
    border: 1px solid {_theme["primary_color"]}44;
    border-radius: 20px;
    padding: 0.25rem 0.8rem;
    font-size: 0.82rem;
    font-weight: 500;
    color: {_theme["primary_color"]};
    margin-bottom: 0.5rem;
}}

/* ---- Chat messages ---- */
.chat-user {{
    background: {_theme["primary_color"]}15;
    border-left: 3px solid {_theme["primary_color"]};
    padding: 0.8rem 1.2rem;
    border-radius: 0 10px 10px 0;
    margin-bottom: 0.5rem;
}}
.chat-assistant {{
    padding: 0.8rem 1.2rem;
    margin-bottom: 1rem;
    line-height: 1.7;
}}

/* ---- Source cards ---- */
.source-card {{
    border: 1px solid {_theme["border_color"]};
    border-radius: 10px;
    padding: 0.6rem 1rem;
    margin-bottom: 0.5rem;
    transition: border-color 0.2s;
}}
.source-card:hover {{
    border-color: {_theme["primary_color"]}66;
}}

/* ---- Section divider ---- */
.section-divider {{
    height: 1px;
    background: linear-gradient(90deg, transparent, {_theme["border_color"]}, transparent);
    margin: 1.5rem 0;
    border: none;
}}

/* ---- Tabs styling ---- */
.stTabs [data-baseweb="tab-list"] {{
    gap: 0.5rem;
}}
.stTabs [data-baseweb="tab"] {{
    border-radius: 8px;
    padding: 0.5rem 1.2rem;
    font-weight: 500;
}}

/* ---- Button accents ---- */
.stButton > button[kind="primary"] {{
    background: linear-gradient(135deg, {_theme["primary_color"]}, {_theme["secondary_color"]});
    border: none;
    font-weight: 600;
    letter-spacing: 0.3px;
}}

/* ---- Streamlit overrides — hide default decorations ---- */
#MainMenu {{visibility: hidden;}}
header {{visibility: hidden;}}
footer {{visibility: hidden;}}
</style>
"""
st.markdown(_css, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Password gate
# ---------------------------------------------------------------------------

def _check_password() -> bool:
    correct = st.secrets.get("APP_PASSWORD")
    if not correct:
        return True
    if st.session_state.get("authenticated"):
        return True
    st.markdown(f"""
    <div class="app-header" style="text-align:center; margin-top: 4rem;">
        <h1>{_brand.get("emoji", "🧠")} {_brand.get("app_name", "SecondBrain")}</h1>
        <p>Enter your password to continue</p>
    </div>
    """, unsafe_allow_html=True)
    pwd = st.text_input("Password", type="password", label_visibility="collapsed")
    if st.button("Enter", type="primary", use_container_width=True):
        if pwd == correct:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    return False


if not _check_password():
    st.stop()


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown(f"""
<div class="app-header">
    <h1>{_brand.get("emoji", "🧠")} {_brand.get("app_name", "SecondBrain")}</h1>
    <p>{_brand.get("tagline", "Your personal RAG-powered knowledge base")}</p>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Workspace selector (sidebar)
# ---------------------------------------------------------------------------
ws_cfg = config.workspaces()
if ws_cfg.get("enabled"):
    with st.sidebar:
        st.markdown("### Workspace")
        predefined = ws_cfg.get("predefined", [])
        ws_names = [w["name"] for w in predefined]

        # Add any workspaces that exist in DB but not in config
        for ws in db.get_workspaces():
            if ws not in ws_names:
                ws_names.append(ws)

        ws_display = []
        for name in ws_names:
            match = next((w for w in predefined if w["name"] == name), None)
            icon = match.get("icon", "📁") if match else "📁"
            desc = match.get("description", "") if match else ""
            ws_display.append(f"{icon} {name}" + (f" — {desc}" if desc else ""))

        selected_ws_idx = st.selectbox(
            "Active workspace",
            range(len(ws_names)),
            format_func=lambda i: ws_display[i],
            label_visibility="collapsed",
        )
        active_workspace = ws_names[selected_ws_idx]

        # Create new workspace
        with st.expander("New workspace"):
            new_ws_name = st.text_input("Name", placeholder="e.g. projects", key="new_ws")
            if st.button("Create") and new_ws_name.strip():
                active_workspace = new_ws_name.strip().lower().replace(" ", "-")
                st.rerun()

        st.markdown(f'<div class="workspace-badge">Active: {active_workspace}</div>', unsafe_allow_html=True)
else:
    active_workspace = "default"

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
_ui = config.ui()
tab_names = _ui.get("tabs", ["Ingest", "Ask", "History", "Sources", "Analytics"])
tab_ingest, tab_ask, tab_history, tab_sources, tab_analytics = st.tabs(tab_names)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_ingest_cfg = config.ui("ingest")
_ask_cfg = config.ui("ask")


def _tag_input(key: str) -> list[str]:
    label = _ingest_cfg.get("tag_label", "Tags (comma-separated, optional)")
    placeholder = _ingest_cfg.get("tag_placeholder", "e.g. aws, architecture, reliability")
    raw = st.text_input(label, key=key, placeholder=placeholder)
    return [t.strip() for t in raw.split(",") if t.strip()] if raw.strip() else []


def _build_export_md(question: str, result: dict) -> str:
    lines = [
        f"# {question}",
        f"*Exported from {_brand.get('app_name', 'SecondBrain')} — {datetime.date.today()}*",
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
    st.markdown(f"### {_ingest_cfg.get('heading', 'Add Knowledge')}")

    input_types = _ingest_cfg.get("input_types", ["Paste text", "URL", "File upload", "YouTube", "Bulk URLs"])
    input_type = st.radio("Input type", input_types, horizontal=True)

    # Embedding model picker
    embed_models = config.models("embedding")
    embed_names = [m["name"] for m in embed_models]
    default_idx = next((i for i, m in enumerate(embed_models) if m.get("default")), 0)
    embed_choice = st.selectbox("Embedding model", embed_names, index=default_idx,
                                help="Choose which model converts text into vectors")
    embed_model_id = embed_models[embed_names.index(embed_choice)]["id"]

    if input_type == "Paste text":
        title = st.text_input("Title", placeholder=_ingest_cfg.get("paste_title_placeholder", ""))
        text = st.text_area(_ingest_cfg.get("paste_area_placeholder", "Paste content here"), height=300)
        tags = _tag_input("tags_text")
        if st.button("Ingest", type="primary"):
            if not text.strip():
                st.error("Please paste some text.")
            elif not title.strip():
                st.error("Please provide a title.")
            else:
                with st.spinner("Chunking and embedding..."):
                    n = ingest.ingest_text(text, title=title.strip(), tags=tags,
                                           workspace=active_workspace, embed_model_id=embed_model_id)
                st.success(f"Ingested **{n}** chunks from \"{title.strip()}\"")

    elif input_type == "URL":
        url = st.text_input("URL", placeholder=_ingest_cfg.get("url_placeholder", ""))
        title = st.text_input("Title (optional)", placeholder="Defaults to URL")
        tags = _tag_input("tags_url")
        if st.button("Ingest URL", type="primary"):
            if not url.strip():
                st.error("Please enter a URL.")
            else:
                with st.spinner("Fetching and processing..."):
                    try:
                        n, js_warn = ingest.ingest_url(url.strip(), title=title.strip() or None, tags=tags,
                                                       workspace=active_workspace, embed_model_id=embed_model_id)
                        if js_warn:
                            st.warning(
                                f"Only extracted a small amount of text ({n} chunk(s)). "
                                "This page likely requires JavaScript — try **Paste text** instead."
                            )
                        else:
                            st.success(f"Ingested **{n}** chunks.")
                    except Exception as e:
                        st.error(f"Failed: {e}")

    elif input_type == "File upload":
        uploaded = st.file_uploader(
            "Upload a file",
            type=["pdf", "docx", "txt", "md", "csv", "json", "rst"],
            help=_ingest_cfg.get("file_help", ""),
        )
        title = st.text_input("Title", placeholder="e.g. AWS Security Whitepaper")
        tags = _tag_input("tags_file")
        if st.button("Ingest file", type="primary"):
            if uploaded is None:
                st.error("Please upload a file.")
            elif not title.strip():
                st.error("Please provide a title.")
            else:
                with st.spinner("Extracting and embedding..."):
                    n = ingest.ingest_file(uploaded.read(), uploaded.name, title=title.strip(), tags=tags,
                                           workspace=active_workspace, embed_model_id=embed_model_id)
                st.success(f"Ingested **{n}** chunks from \"{title.strip()}\"")

    elif input_type == "YouTube":
        url = st.text_input("YouTube URL", placeholder=_ingest_cfg.get("youtube_placeholder", ""))
        title = st.text_input("Title (optional)", placeholder="Defaults to URL")
        tags = _tag_input("tags_yt")
        st.caption(_ingest_cfg.get("youtube_caption", ""))
        if st.button("Ingest transcript", type="primary"):
            if not url.strip():
                st.error("Please enter a YouTube URL.")
            else:
                with st.spinner("Fetching transcript..."):
                    try:
                        n = ingest.ingest_youtube(url.strip(), title=title.strip() or None, tags=tags,
                                                  workspace=active_workspace, embed_model_id=embed_model_id)
                        st.success(f"Ingested **{n}** chunks from transcript.")
                    except Exception as e:
                        st.error(f"Failed: {e}")

    else:  # Bulk URLs
        urls_raw = st.text_area("URLs (one per line)", height=200,
                                placeholder=_ingest_cfg.get("bulk_placeholder", ""))
        tags = _tag_input("tags_bulk")
        if st.button("Ingest all", type="primary"):
            urls = [u.strip() for u in urls_raw.splitlines() if u.strip()]
            if not urls:
                st.error("Please enter at least one URL.")
            else:
                progress = st.progress(0)
                results = []
                for idx, url in enumerate(urls):
                    try:
                        count, js_warning = ingest.ingest_url(url.strip(), tags=tags,
                                                              workspace=active_workspace,
                                                              embed_model_id=embed_model_id)
                        results.append({"url": url, "chunks": count, "warning": js_warning, "error": None})
                    except Exception as e:
                        results.append({"url": url, "chunks": 0, "warning": False, "error": str(e)})
                    progress.progress((idx + 1) / len(urls))
                progress.empty()
                for r in results:
                    if r["error"]:
                        st.error(f"{r['url']} — {r['error']}")
                    elif r["warning"]:
                        st.warning(f"{r['url']} — {r['chunks']} chunks (JS-rendered, may be partial)")
                    else:
                        st.success(f"{r['url']} — {r['chunks']} chunks")

    # Import KB
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    st.markdown(f"### {_ingest_cfg.get('import_heading', 'Import Knowledge Base')}")
    import_file = st.file_uploader("Upload a SecondBrain export (.json)", type=["json"], key="import_kb")
    if import_file and st.button("Import", type="secondary"):
        with st.spinner("Importing..."):
            data = json.loads(import_file.read().decode("utf-8"))
            result = ingest.import_knowledge_base(data, workspace=active_workspace)
        st.success(f"Imported **{result['imported']}** sources, skipped {result['skipped']} duplicates.")
        st.rerun()


# ---------------------------------------------------------------------------
# ASK TAB
# ---------------------------------------------------------------------------

with tab_ask:
    st.markdown(f"### {_ask_cfg.get('heading', 'Ask Your Knowledge Base')}")

    with st.expander(_ask_cfg.get("search_options_label", "Search options"), expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            use_hybrid = st.toggle(
                _ask_cfg.get("hybrid_label", "Hybrid search"),
                value=config.retrieval().get("default_hybrid", True),
                help=_ask_cfg.get("hybrid_help", ""),
            )
            use_rerank = st.toggle(
                _ask_cfg.get("rerank_label", "Reranking"),
                value=config.retrieval().get("default_rerank", False),
                help=_ask_cfg.get("rerank_help", ""),
            )
        with col2:
            all_tags = db.get_all_tags(workspace=active_workspace)
            selected_tags = st.multiselect("Filter by tags", options=all_tags,
                                           help="Leave empty to search all sources")
            min_sim = st.slider(
                _ask_cfg.get("threshold_label", "Min similarity score"),
                min_value=0.0, max_value=1.0,
                value=config.retrieval().get("min_similarity", 0.0),
                step=0.05,
                help=_ask_cfg.get("threshold_help", ""),
            )
        with col3:
            llm_models = config.models("llm")
            llm_names = [m["name"] for m in llm_models]
            default_llm = next((i for i, m in enumerate(llm_models) if m.get("default")), 0)
            model_choice = st.selectbox(
                _ask_cfg.get("model_label", "Claude model"),
                llm_names,
                index=default_llm,
            )
            model_id = llm_models[llm_names.index(model_choice)]["id"]

            use_streaming = st.toggle(
                _ask_cfg.get("stream_label", "Stream response"),
                value=config.retrieval().get("default_stream", True),
                help=_ask_cfg.get("stream_help", ""),
            )

    question = st.text_input(
        "Your question",
        placeholder=_ask_cfg.get("question_placeholder", ""),
        label_visibility="collapsed",
    )

    col_ask, col_clear = st.columns([1, 5])
    with col_ask:
        ask_clicked = st.button("Ask", type="primary", use_container_width=True)
    with col_clear:
        if st.button("Clear conversation"):
            st.session_state.pop("chat_history", None)
            st.session_state.pop("last_result", None)
            st.session_state.pop("last_question", None)
            st.rerun()

    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    if ask_clicked:
        if not question.strip():
            st.error("Please enter a question.")
        elif use_streaming:
            sources = []
            answer_placeholder = st.empty()
            full_answer = ""
            final_history = None

            with st.spinner("Retrieving relevant chunks..."):
                stream = query.ask_stream(
                    question.strip(),
                    history=st.session_state["chat_history"],
                    tags=selected_tags or None,
                    use_rerank=use_rerank,
                    hybrid=use_hybrid,
                    model_id=model_id,
                    min_similarity=min_sim,
                    workspace=active_workspace,
                )
                first = True
                for token, srcs, updated_history in stream:
                    if first:
                        sources = srcs
                        first = False
                    full_answer += token
                    answer_placeholder.markdown(full_answer + "▌")
                    if updated_history is not None:
                        final_history = updated_history

            answer_placeholder.markdown(full_answer)

            if final_history:
                st.session_state["chat_history"] = final_history
            st.session_state["last_result"] = {"answer": full_answer, "sources": sources}
            st.session_state["last_question"] = question.strip()
            db.log_search(question.strip(), full_answer, sources, selected_tags or [])
        else:
            with st.spinner("Searching and generating answer..."):
                result = query.ask(
                    question.strip(),
                    history=st.session_state["chat_history"],
                    tags=selected_tags or None,
                    use_rerank=use_rerank,
                    hybrid=use_hybrid,
                    model_id=model_id,
                    min_similarity=min_sim,
                    workspace=active_workspace,
                )
            st.session_state["chat_history"] = result["history"]
            st.session_state["last_result"] = result
            st.session_state["last_question"] = question.strip()
            db.log_search(question.strip(), result["answer"], result.get("sources", []), selected_tags or [])

    # Display conversation
    if st.session_state["chat_history"]:
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        turns = st.session_state["chat_history"]
        for i in range(0, len(turns) - 1, 2):
            user_msg = turns[i]["content"]
            asst_msg = turns[i + 1]["content"] if i + 1 < len(turns) else ""
            st.markdown(f'<div class="chat-user"><strong>You</strong><br>{user_msg}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="chat-assistant">{asst_msg}</div>', unsafe_allow_html=True)

        # Sources for last answer
        last = st.session_state.get("last_result")
        if last and last.get("sources"):
            st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
            st.markdown("**Sources used for last answer**")
            for i, src in enumerate(last["sources"], 1):
                score = src.get("score", 0)
                with st.expander(f"Source {i}: {src['title']} (score: {score})"):
                    if src["url"]:
                        st.markdown(f"**URL:** {src['url']}")
                    st.text(src["text"][:500] + ("..." if len(src["text"]) > 500 else ""))

        # Export
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
# HISTORY TAB
# ---------------------------------------------------------------------------

with tab_history:
    _hist_cfg = config.ui("history")
    st.markdown(f"### {_hist_cfg.get('heading', 'Search History')}")

    history_items = db.get_search_history(limit=50)

    if not history_items:
        st.info(_hist_cfg.get("empty_message", "No searches yet."))
    else:
        col_count, col_clear = st.columns([3, 1])
        with col_count:
            st.caption(f"Showing {len(history_items)} most recent searches")
        with col_clear:
            if st.button("Clear all history", type="secondary"):
                db.delete_search_history()
                st.rerun()

        for item in history_items:
            searched_at = item["searched_at"][:16].replace("T", " ")
            tags_str = ", ".join(item.get("tags_used", [])) if item.get("tags_used") else "all"
            with st.expander(f"{searched_at} — {item['question'][:80]}"):
                st.markdown(f"**Tags:** {tags_str}")
                st.markdown("**Answer:**")
                st.markdown(item["answer"])
                if item.get("sources"):
                    st.markdown("**Sources:**")
                    for src in item["sources"][:3]:
                        st.caption(f"- {src.get('title', 'Unknown')} (score: {src.get('score', 'n/a')})")
                if st.button("Re-ask this question", key=f"reask_{item['id']}"):
                    st.session_state["reask_question"] = item["question"]
                    st.rerun()


# ---------------------------------------------------------------------------
# SOURCES TAB
# ---------------------------------------------------------------------------

with tab_sources:
    _src_cfg = config.ui("sources")
    st.markdown(f"### {_src_cfg.get('heading', 'Ingested Sources')}")

    col_filter, col_export = st.columns([3, 1])
    with col_filter:
        all_tags_filter = db.get_all_tags(workspace=active_workspace)
        filter_tags = st.multiselect("Filter by tag", options=all_tags_filter, key="src_filter_tags")
    with col_export:
        if st.button("Export entire KB"):
            with st.spinner("Exporting..."):
                export_data = ingest.export_knowledge_base(workspace=active_workspace)
            st.download_button(
                label="Download export",
                data=json.dumps(export_data, indent=2),
                file_name=f"secondbrain_export_{datetime.date.today()}.json",
                mime="application/json",
            )

    sources = db.get_all_sources(workspace=active_workspace)

    if filter_tags:
        sources = [s for s in sources if any(t in s["tags"] for t in filter_tags)]

    if not sources:
        st.info(_src_cfg.get("empty_message", "No sources ingested yet."))
    else:
        for src in sources:
            with st.expander(f"{src['title']}  —  {src['chunk_count']} chunks  |  {src['source_type']}  |  {src['ingested_at'][:10]}"):
                col1, col2 = st.columns([3, 1])
                with col1:
                    if src.get("url"):
                        st.caption(src["url"])
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

                    if src.get("url"):
                        if st.button("Check freshness", key=f"fresh_{src['id']}"):
                            with st.spinner("Checking..."):
                                result = ingest.check_url_freshness(src["id"])
                            if result.get("error"):
                                st.error(result["error"])
                            elif result["changed"]:
                                st.warning(f"Content changed ({result['old_length']} -> {result['new_length']} words)")
                                if st.button("Re-crawl now", key=f"recrawl_{src['id']}"):
                                    with st.spinner("Re-crawling..."):
                                        r = ingest.recrawl_source(src["id"], workspace=active_workspace)
                                    if r["error"]:
                                        st.error(r["error"])
                                    else:
                                        st.success(f"Re-crawled: {r['chunks']} chunks")
                                    st.rerun()
                            else:
                                st.success("Content unchanged since last ingest.")

                    if st.button("Re-ingest", key=f"reingest_{src['id']}",
                                 help="Re-embed all chunks (e.g. after switching embedding model)"):
                        with st.spinner("Re-embedding..."):
                            n = ingest.reingest_source(src["id"], workspace=active_workspace)
                        st.success(f"Re-ingested {n} chunks.")
                        st.rerun()

                    if st.button("Delete", key=f"del_{src['id']}", type="secondary"):
                        ingest.delete_source(src["id"], workspace=active_workspace)
                        st.rerun()

                # View / edit chunks
                if st.checkbox("View chunks", key=f"chunks_{src['id']}"):
                    chunks = db.get_chunks_for_source(src["id"])
                    for c in chunks:
                        edited = st.text_area(
                            f"Chunk {c['chunk_index']}",
                            value=c["text"],
                            height=120,
                            key=f"chunk_text_{c['id']}",
                        )
                        if edited != c["text"]:
                            if st.button("Save edit", key=f"save_chunk_{c['id']}"):
                                db.update_chunk_text(c["id"], edited)
                                st.success(f"Chunk {c['chunk_index']} updated.")
                                st.rerun()


# ---------------------------------------------------------------------------
# ANALYTICS TAB
# ---------------------------------------------------------------------------

with tab_analytics:
    _analytics_cfg = config.ui("analytics")
    st.markdown(f"### {_analytics_cfg.get('heading', 'Knowledge Base Analytics')}")

    stats = db.get_stats(workspace=active_workspace if active_workspace != "default" else None)

    # Metric cards
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{stats["source_count"]}</div>
            <div class="metric-label">Sources</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{stats["chunk_count"]}</div>
            <div class="metric-label">Chunks</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{stats["query_count"]}</div>
            <div class="metric-label">Queries</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    col_types, col_tags = st.columns(2)

    with col_types:
        st.markdown("#### Sources by Type")
        if stats["type_breakdown"]:
            for stype, count in stats["type_breakdown"].items():
                pct = count / max(stats["source_count"], 1) * 100
                st.markdown(f"**{stype}** — {count} ({pct:.0f}%)")
                st.progress(pct / 100)
        else:
            st.caption("No sources yet.")

    with col_tags:
        st.markdown("#### Tag Frequency")
        if stats["tag_frequency"]:
            max_count = max(stats["tag_frequency"].values())
            for tag, count in list(stats["tag_frequency"].items())[:15]:
                st.markdown(f"**{tag}** — {count} source(s)")
                st.progress(count / max_count)
        else:
            st.caption("No tags yet.")

    # Dedup
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    st.markdown(f"#### {_analytics_cfg.get('dedup_heading', 'Duplicate Detection')}")
    st.caption(_analytics_cfg.get("dedup_caption", ""))
    if st.button("Scan for duplicates"):
        with st.spinner("Comparing chunk embeddings..."):
            dupes = ingest.find_duplicate_chunks(workspace=active_workspace)
        if not dupes:
            st.success(_analytics_cfg.get("dedup_success", "No near-duplicate chunks found."))
        else:
            st.warning(f"Found **{len(dupes)}** near-duplicate chunk pair(s).")
            for d in dupes[:20]:
                with st.expander(f"Similarity {d['similarity']:.2%} — {d['title_a']} / {d['title_b']}"):
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.markdown(f"**{d['title_a']}**")
                        st.text(d["text_a"])
                    with col_b:
                        st.markdown(f"**{d['title_b']}**")
                        st.text(d["text_b"])
