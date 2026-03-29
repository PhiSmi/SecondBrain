"""SecondBrain — Streamlit UI."""

import datetime
import json

import streamlit as st

import config
import db
import evaluate
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
# Minimal, clean CSS that works with Streamlit's native theming
# ---------------------------------------------------------------------------
_theme = config.theme()

_css = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

.stApp {{
    font-family: {_theme.get("font_family", "Inter, sans-serif")};
}}

/* Gradient header */
.app-header {{
    background: linear-gradient(135deg, {_theme["gradient_start"]} 0%, {_theme["gradient_end"]} 100%);
    padding: 1.5rem 2rem;
    border-radius: 12px;
    margin-bottom: 1rem;
}}
.app-header h1 {{
    color: white; font-size: 1.8rem; font-weight: 700; margin: 0 0 0.2rem 0;
}}
.app-header p {{
    color: rgba(255,255,255,0.85); font-size: 0.95rem; margin: 0; font-weight: 300;
}}

/* Metric cards */
.metric-card {{
    border: 1px solid rgba(108, 92, 231, 0.2);
    border-radius: 10px;
    padding: 1rem 1.2rem;
    text-align: center;
    margin-bottom: 0.5rem;
}}
.metric-card .metric-value {{
    font-size: 2rem; font-weight: 700;
    background: linear-gradient(135deg, {_theme["primary_color"]}, {_theme["secondary_color"]});
    -webkit-background-clip: text; -webkit-text-fill-color: transparent; line-height: 1.2;
}}
.metric-card .metric-label {{
    font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px; margin-top: 0.2rem; opacity: 0.6;
}}

/* Workspace badge */
.workspace-badge {{
    display: inline-block;
    background: {_theme["primary_color"]}18;
    border: 1px solid {_theme["primary_color"]}33;
    border-radius: 16px; padding: 0.2rem 0.7rem; font-size: 0.8rem; font-weight: 500;
    color: {_theme["primary_color"]};
}}

/* Chat bubbles */
.chat-user {{
    border-left: 3px solid {_theme["primary_color"]};
    padding: 0.6rem 1rem; border-radius: 0 8px 8px 0; margin-bottom: 0.5rem;
    background: {_theme["primary_color"]}08;
}}
.chat-assistant {{ padding: 0.6rem 1rem; margin-bottom: 0.8rem; line-height: 1.6; }}

/* Divider */
.section-divider {{
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(128,128,128,0.2), transparent);
    margin: 1.2rem 0; border: none;
}}

/* Eval score colours */
.eval-score-1, .eval-score-2 {{ color: {_theme["error_color"]}; font-weight: 700; }}
.eval-score-3 {{ color: {_theme["warning_color"]}; font-weight: 700; }}
.eval-score-4, .eval-score-5 {{ color: {_theme["success_color"]}; font-weight: 700; }}

/* Tab styling */
.stTabs [data-baseweb="tab-list"] {{ gap: 0.3rem; }}
.stTabs [data-baseweb="tab"] {{ border-radius: 8px 8px 0 0; padding: 0.4rem 1rem; font-weight: 500; }}
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
    with st.form("login_form"):
        pwd = st.text_input("Password", type="password", label_visibility="collapsed")
        if st.form_submit_button("Enter", type="primary", use_container_width=True):
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
# Sidebar — workspace + settings
# ---------------------------------------------------------------------------
ws_cfg = config.workspaces()
with st.sidebar:
    if ws_cfg.get("enabled"):
        st.markdown("### Workspace")
        predefined = ws_cfg.get("predefined", [])
        ws_names = [w["name"] for w in predefined]
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
            "Active workspace", range(len(ws_names)),
            format_func=lambda i: ws_display[i], label_visibility="collapsed",
        )
        active_workspace = ws_names[selected_ws_idx]

        with st.expander("New workspace"):
            new_ws_name = st.text_input("Name", placeholder="e.g. projects", key="new_ws")
            if st.button("Create") and new_ws_name.strip():
                active_workspace = new_ws_name.strip().lower().replace(" ", "-")
                st.rerun()

        st.markdown(f'<div class="workspace-badge">Active: {active_workspace}</div>', unsafe_allow_html=True)
    else:
        active_workspace = "default"

    # Cost summary
    usage = db.get_api_usage_stats()
    if usage["total_calls"] > 0:
        st.markdown("---")
        st.caption(f"API calls: {usage['total_calls']}  ·  Cost: ${usage['total_cost_usd']:.4f}")


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
_ui = config.ui()
tab_ingest, tab_ask, tab_history, tab_sources, tab_rss, tab_analytics, tab_eval = st.tabs(
    ["📥 Ingest", "💬 Ask", "📜 History", "📚 Sources", "📡 RSS Feeds", "📊 Analytics", "🧪 Eval"]
)

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
        "", "## Answer", result["answer"], "", "## Sources",
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
    st.subheader(_ingest_cfg.get("heading", "Add Knowledge"))

    input_types = _ingest_cfg.get("input_types", ["Paste text", "URL", "File upload", "YouTube", "Bulk URLs"])
    input_type = st.radio("Input type", input_types, horizontal=True, label_visibility="collapsed")

    # Embedding model picker
    embed_models = config.models("embedding")
    embed_names = [m["name"] for m in embed_models]
    default_idx = next((i for i, m in enumerate(embed_models) if m.get("default")), 0)

    col_embed, col_autotag, col_ocr = st.columns([2, 1, 1])
    with col_embed:
        embed_choice = st.selectbox("Embedding model", embed_names, index=default_idx)
        embed_model_id = embed_models[embed_names.index(embed_choice)]["id"]
    with col_autotag:
        use_autotag = st.toggle("Auto-tag with AI", value=False,
                                help="Use Claude to suggest tags automatically")
    with col_ocr:
        use_ocr = st.toggle("OCR for scanned PDFs", value=False,
                             help="Use Tesseract OCR for image-based PDFs")

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    if input_type == "Paste text":
        title = st.text_input("Title", placeholder=_ingest_cfg.get("paste_title_placeholder", ""))
        text = st.text_area("Content", placeholder=_ingest_cfg.get("paste_area_placeholder", "Paste content here"),
                            height=250)
        tags = _tag_input("tags_text")

        if use_autotag and text.strip():
            if st.button("💡 Suggest tags"):
                with st.spinner("Asking Claude for tag suggestions..."):
                    suggested = query.suggest_tags(text)
                st.info(f"Suggested: **{', '.join(suggested)}**")

        if st.button("Ingest", type="primary"):
            if not text.strip():
                st.error("Please paste some text.")
            elif not title.strip():
                st.error("Please provide a title.")
            else:
                if use_autotag and not tags:
                    with st.spinner("Auto-tagging..."):
                        tags = query.suggest_tags(text)
                with st.spinner("Chunking and embedding..."):
                    n = ingest.ingest_text(text, title=title.strip(), tags=tags,
                                           workspace=active_workspace, embed_model_id=embed_model_id)
                st.success(f"Ingested **{n}** chunks from \"{title.strip()}\"" +
                           (f" with tags: {', '.join(tags)}" if tags else ""))

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
                        if use_autotag and not tags:
                            text_content, _ = ingest.fetch_url_text(url.strip())
                            tags = query.suggest_tags(text_content)
                        if js_warn:
                            st.warning(f"Only {n} chunk(s) — page likely requires JavaScript.")
                        else:
                            st.success(f"Ingested **{n}** chunks.")
                    except Exception as e:
                        st.error(f"Failed: {e}")

    elif input_type == "File upload":
        uploaded = st.file_uploader("Upload a file",
                                    type=["pdf", "docx", "txt", "md", "csv", "json", "rst"],
                                    help=_ingest_cfg.get("file_help", ""))
        title = st.text_input("Title", placeholder="e.g. AWS Security Whitepaper")
        tags = _tag_input("tags_file")
        if st.button("Ingest file", type="primary"):
            if uploaded is None:
                st.error("Please upload a file.")
            elif not title.strip():
                st.error("Please provide a title.")
            else:
                file_bytes = uploaded.read()
                if use_autotag and not tags:
                    with st.spinner("Auto-tagging..."):
                        preview = file_bytes[:3000].decode("utf-8", errors="replace")
                        tags = query.suggest_tags(preview)
                with st.spinner("Extracting and embedding..."):
                    n = ingest.ingest_file(file_bytes, uploaded.name, title=title.strip(), tags=tags,
                                           workspace=active_workspace, embed_model_id=embed_model_id,
                                           ocr=use_ocr)
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
                for idx, u in enumerate(urls):
                    try:
                        count, js_warning = ingest.ingest_url(u.strip(), tags=tags,
                                                              workspace=active_workspace, embed_model_id=embed_model_id)
                        results.append({"url": u, "chunks": count, "warning": js_warning, "error": None})
                    except Exception as e:
                        results.append({"url": u, "chunks": 0, "warning": False, "error": str(e)})
                    progress.progress((idx + 1) / len(urls))
                progress.empty()
                for r in results:
                    if r["error"]:
                        st.error(f"{r['url']} — {r['error']}")
                    elif r["warning"]:
                        st.warning(f"{r['url']} — {r['chunks']} chunks (JS-rendered)")
                    else:
                        st.success(f"{r['url']} — {r['chunks']} chunks")

    # Import KB
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    with st.expander(_ingest_cfg.get("import_heading", "Import Knowledge Base")):
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
    st.subheader(_ask_cfg.get("heading", "Ask Your Knowledge Base"))

    with st.expander("⚙️ Search options", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            use_hybrid = st.toggle(_ask_cfg.get("hybrid_label", "Hybrid search"),
                                   value=config.retrieval().get("default_hybrid", True),
                                   help=_ask_cfg.get("hybrid_help", ""))
            use_rerank = st.toggle(_ask_cfg.get("rerank_label", "Reranking"),
                                   value=config.retrieval().get("default_rerank", False),
                                   help=_ask_cfg.get("rerank_help", ""))
        with col2:
            all_tags = db.get_all_tags(workspace=active_workspace)
            selected_tags = st.multiselect("Filter by tags", options=all_tags)
            min_sim = st.slider(_ask_cfg.get("threshold_label", "Min similarity"),
                                0.0, 1.0, config.retrieval().get("min_similarity", 0.0), 0.05)
        with col3:
            llm_models = config.models("llm")
            llm_names = [m["name"] for m in llm_models]
            default_llm = next((i for i, m in enumerate(llm_models) if m.get("default")), 0)
            model_choice = st.selectbox(_ask_cfg.get("model_label", "Claude model"), llm_names, index=default_llm)
            model_id = llm_models[llm_names.index(model_choice)]["id"]
            use_streaming = st.toggle(_ask_cfg.get("stream_label", "Stream response"),
                                      value=config.retrieval().get("default_stream", True))

    # Form so pressing Enter submits the question
    with st.form("ask_form", clear_on_submit=False):
        question = st.text_input("Your question", placeholder=_ask_cfg.get("question_placeholder", ""),
                                 label_visibility="collapsed")
        col_ask, col_clear = st.columns([1, 5])
        with col_ask:
            ask_clicked = st.form_submit_button("Ask", type="primary", use_container_width=True)
        with col_clear:
            clear_clicked = st.form_submit_button("Clear conversation")

    if clear_clicked:
        for k in ["chat_history", "last_result", "last_question"]:
            st.session_state.pop(k, None)
        st.rerun()

    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    if ask_clicked and question.strip():
        if use_streaming:
            sources = []
            answer_placeholder = st.empty()
            full_answer = ""
            final_history = None
            with st.spinner("Retrieving..."):
                stream = query.ask_stream(question.strip(), history=st.session_state["chat_history"],
                                          tags=selected_tags or None, use_rerank=use_rerank, hybrid=use_hybrid,
                                          model_id=model_id, min_similarity=min_sim, workspace=active_workspace)
                first = True
                for token, srcs, updated in stream:
                    if first:
                        sources = srcs
                        first = False
                    full_answer += token
                    answer_placeholder.markdown(full_answer + "▌")
                    if updated is not None:
                        final_history = updated
            answer_placeholder.markdown(full_answer)
            if final_history:
                st.session_state["chat_history"] = final_history
            st.session_state["last_result"] = {"answer": full_answer, "sources": sources}
            st.session_state["last_question"] = question.strip()
            db.log_search(question.strip(), full_answer, sources, selected_tags or [])
        else:
            with st.spinner("Searching..."):
                result = query.ask(question.strip(), history=st.session_state["chat_history"],
                                   tags=selected_tags or None, use_rerank=use_rerank, hybrid=use_hybrid,
                                   model_id=model_id, min_similarity=min_sim, workspace=active_workspace)
            st.session_state["chat_history"] = result["history"]
            st.session_state["last_result"] = result
            st.session_state["last_question"] = question.strip()
            db.log_search(question.strip(), result["answer"], result.get("sources", []), selected_tags or [])
    elif ask_clicked:
        st.warning("Please enter a question.")

    # Display conversation
    if st.session_state["chat_history"]:
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        turns = st.session_state["chat_history"]
        for i in range(0, len(turns) - 1, 2):
            u = turns[i]["content"]
            a = turns[i + 1]["content"] if i + 1 < len(turns) else ""
            st.markdown(f'<div class="chat-user"><strong>You:</strong> {u}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="chat-assistant">{a}</div>', unsafe_allow_html=True)

        last = st.session_state.get("last_result")
        if last and last.get("sources"):
            st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
            st.markdown("**Sources used**")
            for i, src in enumerate(last["sources"], 1):
                with st.expander(f"{i}. {src['title']} (score: {src.get('score', 0)})"):
                    if src["url"]:
                        st.markdown(f"[{src['url']}]({src['url']})")
                    st.text(src["text"][:500] + ("..." if len(src["text"]) > 500 else ""))

        last_result = st.session_state.get("last_result")
        if last_result:
            md = _build_export_md(st.session_state.get("last_question", ""), last_result)
            st.download_button("📄 Export as Markdown", data=md,
                               file_name=f"secondbrain_{datetime.date.today()}.md", mime="text/markdown")


# ---------------------------------------------------------------------------
# HISTORY TAB
# ---------------------------------------------------------------------------

with tab_history:
    st.subheader(config.ui("history").get("heading", "Search History"))
    history_items = db.get_search_history(limit=50)
    if not history_items:
        st.info(config.ui("history").get("empty_message", "No searches yet."))
    else:
        col_count, col_clear = st.columns([3, 1])
        with col_count:
            st.caption(f"{len(history_items)} most recent searches")
        with col_clear:
            if st.button("Clear all history", type="secondary"):
                db.delete_search_history()
                st.rerun()
        for item in history_items:
            at = item["searched_at"][:16].replace("T", " ")
            with st.expander(f"🕒 {at} — {item['question'][:80]}"):
                st.markdown(item["answer"])
                if st.button("Re-ask this question", key=f"reask_{item['id']}"):
                    st.session_state["reask_question"] = item["question"]
                    st.rerun()


# ---------------------------------------------------------------------------
# SOURCES TAB
# ---------------------------------------------------------------------------

with tab_sources:
    st.subheader(config.ui("sources").get("heading", "Ingested Sources"))

    col_filter, col_export = st.columns([3, 1])
    with col_filter:
        filter_tags = st.multiselect("Filter by tag", options=db.get_all_tags(workspace=active_workspace), key="src_ft")
    with col_export:
        if st.button("Export KB"):
            with st.spinner("Exporting..."):
                export_data = ingest.export_knowledge_base(workspace=active_workspace)
            st.download_button("Download JSON", data=json.dumps(export_data, indent=2),
                               file_name=f"secondbrain_export_{datetime.date.today()}.json", mime="application/json")

    sources = db.get_all_sources(workspace=active_workspace)
    if filter_tags:
        sources = [s for s in sources if any(t in s["tags"] for t in filter_tags)]

    if not sources:
        st.info(config.ui("sources").get("empty_message", "No sources ingested yet."))
    else:
        for src in sources:
            label = f"**{src['title']}**  ·  {src['chunk_count']} chunks  ·  {src['source_type']}  ·  {src['ingested_at'][:10]}"
            with st.expander(label):
                col1, col2 = st.columns([3, 1])
                with col1:
                    if src.get("url"):
                        st.caption(src["url"])
                    current_tags = ", ".join(src.get("tags") or [])
                    new_tags = st.text_input("Tags", value=current_tags, key=f"tags_{src['id']}")
                    if st.button("Save tags", key=f"st_{src['id']}"):
                        db.update_source_tags(src["id"], [t.strip() for t in new_tags.split(",") if t.strip()])
                        st.rerun()
                with col2:
                    st.metric("Chunks", src["chunk_count"])
                    if st.button("Summarise", key=f"sum_{src['id']}"):
                        with st.spinner("Summarising..."):
                            st.markdown(query.summarise_source(src["id"]))
                    if src.get("url") and st.button("Check freshness", key=f"fr_{src['id']}"):
                        with st.spinner("Checking..."):
                            r = ingest.check_url_freshness(src["id"])
                        if r.get("error"):
                            st.error(r["error"])
                        elif r["changed"]:
                            st.warning(f"Changed ({r['old_length']} → {r['new_length']} words)")
                        else:
                            st.success("Unchanged")
                    if st.button("Re-ingest", key=f"ri_{src['id']}"):
                        with st.spinner("Re-embedding..."):
                            n = ingest.reingest_source(src["id"], workspace=active_workspace)
                        st.success(f"Re-ingested {n} chunks.")
                        st.rerun()
                    if st.button("Delete", key=f"del_{src['id']}", type="secondary"):
                        ingest.delete_source(src["id"], workspace=active_workspace)
                        st.rerun()
                if st.checkbox("View/edit chunks", key=f"ch_{src['id']}"):
                    for c in db.get_chunks_for_source(src["id"]):
                        edited = st.text_area(f"Chunk {c['chunk_index']}", value=c["text"], height=120,
                                              key=f"ct_{c['id']}")
                        if edited != c["text"] and st.button("Save", key=f"sc_{c['id']}"):
                            db.update_chunk_text(c["id"], edited)
                            st.rerun()


# ---------------------------------------------------------------------------
# RSS FEEDS TAB
# ---------------------------------------------------------------------------

with tab_rss:
    st.subheader("RSS Feeds")
    st.caption("Subscribe to blogs and news feeds. New entries are ingested into your knowledge base.")

    with st.expander("Add new feed", expanded=True):
        rss_url = st.text_input("Feed URL", placeholder="https://blog.example.com/feed.xml", key="rss_url")
        rss_title = st.text_input("Feed title (optional)", key="rss_title")
        rss_tags = _tag_input("rss_tags")
        if st.button("Subscribe", type="primary"):
            if rss_url.strip():
                db.add_rss_feed(rss_url.strip(), title=rss_title.strip() or None,
                                tags=rss_tags, workspace=active_workspace)
                st.success("Feed added.")
                st.rerun()

    feeds = db.get_rss_feeds(workspace=active_workspace)
    if not feeds:
        st.info("No RSS feeds subscribed yet.")
    else:
        if st.button("Fetch all feeds"):
            total_new = 0
            for f in feeds:
                if not f.get("active"):
                    continue
                with st.spinner(f"Fetching {f.get('title') or f['url']}..."):
                    r = ingest.ingest_rss_feed(f["id"])
                total_new += r["new_entries"]
                if r["errors"]:
                    for e in r["errors"]:
                        st.error(e)
            st.success(f"Fetched {total_new} new entries across all feeds.")

        for f in feeds:
            status = "🟢 Active" if f.get("active") else "⏸️ Paused"
            last = f.get("last_fetched", "never")
            if last and last != "never":
                last = last[:16].replace("T", " ")
            with st.expander(f"{f.get('title') or f['url']}  ·  {status}  ·  Last: {last}"):
                st.caption(f["url"])
                if f.get("tags"):
                    st.caption(f"Tags: {', '.join(f['tags'])}")
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    if st.button("Fetch now", key=f"rfetch_{f['id']}"):
                        with st.spinner("Fetching..."):
                            r = ingest.ingest_rss_feed(f["id"])
                        st.success(f"{r['new_entries']} new entries, {r['total_chunks']} chunks")
                with col_b:
                    label = "Pause" if f.get("active") else "Resume"
                    if st.button(label, key=f"rpause_{f['id']}"):
                        db.toggle_rss_feed(f["id"], not f.get("active"))
                        st.rerun()
                with col_c:
                    if st.button("Remove", key=f"rdel_{f['id']}", type="secondary"):
                        db.delete_rss_feed(f["id"])
                        st.rerun()


# ---------------------------------------------------------------------------
# ANALYTICS TAB
# ---------------------------------------------------------------------------

with tab_analytics:
    st.subheader(config.ui("analytics").get("heading", "Knowledge Base Analytics"))

    stats = db.get_stats(workspace=active_workspace if active_workspace != "default" else None)

    col1, col2, col3, col4 = st.columns(4)
    for col, val, label in [(col1, stats["source_count"], "Sources"),
                             (col2, stats["chunk_count"], "Chunks"),
                             (col3, stats["query_count"], "Queries"),
                             (col4, f"${usage['total_cost_usd']:.4f}", "API Cost")]:
        with col:
            st.markdown(f'<div class="metric-card"><div class="metric-value">{val}</div>'
                        f'<div class="metric-label">{label}</div></div>', unsafe_allow_html=True)

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    col_types, col_tags = st.columns(2)
    with col_types:
        st.markdown("#### Sources by Type")
        if stats["type_breakdown"]:
            for stype, count in stats["type_breakdown"].items():
                pct = count / max(stats["source_count"], 1)
                st.markdown(f"**{stype}** — {count} ({pct:.0%})")
                st.progress(pct)
        else:
            st.caption("No sources yet.")
    with col_tags:
        st.markdown("#### Tag Frequency")
        if stats["tag_frequency"]:
            mx = max(stats["tag_frequency"].values())
            for tag, count in list(stats["tag_frequency"].items())[:15]:
                st.markdown(f"**{tag}** — {count}")
                st.progress(count / mx)
        else:
            st.caption("No tags yet.")

    # Cost breakdown
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    st.markdown("#### API Cost Breakdown")
    if usage["by_model"]:
        for m in usage["by_model"]:
            st.markdown(f"**{m['model_id']}** — {m['calls']} calls, "
                        f"{m['inp']:,} in / {m['out']:,} out tokens, ${m['cost']:.4f}")
    if usage["by_operation"]:
        st.markdown("**By operation:**")
        for op in usage["by_operation"]:
            st.caption(f"- {op['operation']}: {op['calls']} calls, ${op['cost']:.4f}")

    # Dedup
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    st.markdown("#### Duplicate Detection")
    if st.button("Scan for duplicates"):
        with st.spinner("Comparing embeddings..."):
            dupes = ingest.find_duplicate_chunks(workspace=active_workspace)
        if not dupes:
            st.success("No duplicates found.")
        else:
            st.warning(f"**{len(dupes)}** duplicate pair(s)")
            for d in dupes[:20]:
                with st.expander(f"{d['similarity']:.2%} — {d['title_a']} / {d['title_b']}"):
                    ca, cb = st.columns(2)
                    with ca:
                        st.text(d["text_a"])
                    with cb:
                        st.text(d["text_b"])


# ---------------------------------------------------------------------------
# EVALUATION TAB
# ---------------------------------------------------------------------------

with tab_eval:
    st.subheader("Evaluation Framework")
    st.caption("Define question-answer pairs and measure retrieval quality.")

    with st.expander("Add evaluation pair", expanded=False):
        eq = st.text_input("Question", key="eval_q")
        ea = st.text_area("Expected answer", key="eval_a", height=100)
        et = _tag_input("eval_tags")
        if st.button("Add pair"):
            if eq.strip() and ea.strip():
                db.add_eval_pair(eq.strip(), ea.strip(), tags=et, workspace=active_workspace)
                st.success("Pair added.")
                st.rerun()

    pairs = db.get_eval_pairs(workspace=active_workspace)
    if not pairs:
        st.info("No evaluation pairs yet. Add some above.")
    else:
        st.markdown(f"**{len(pairs)} evaluation pair(s)**")
        for p in pairs:
            with st.expander(f"{p['question'][:80]}"):
                st.markdown(f"**Expected:** {p['expected_answer']}")
                if st.button("Delete", key=f"edel_{p['id']}", type="secondary"):
                    db.delete_eval_pair(p["id"])
                    st.rerun()

        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

        if st.button("Run evaluation", type="primary"):
            with st.spinner("Running evaluation (this calls Claude for each pair)..."):
                results = evaluate.run_evaluation(workspace=active_workspace)
                summary = evaluate.compute_summary(results)

            # Summary metrics
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Avg Score", f"{summary['avg_score']}/5")
            with c2:
                st.metric("Min", summary["min_score"])
            with c3:
                st.metric("Max", summary["max_score"])

            # Distribution
            st.markdown("**Score distribution:**")
            for s in range(1, 6):
                count = summary["score_distribution"].get(s, 0)
                st.markdown(f'<span class="eval-score-{s}">{"★" * s}{"☆" * (5-s)}</span> — {count} pair(s)',
                            unsafe_allow_html=True)

            # Detail
            st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
            for r in results:
                with st.expander(f"{'★' * r['score']}{'☆' * (5 - r['score'])} — {r['question'][:60]}"):
                    st.markdown(f"**Expected:** {r['expected']}")
                    st.markdown(f"**Actual:** {r['actual']}")
                    st.markdown(f"**Reasoning:** {r['reasoning']}")
