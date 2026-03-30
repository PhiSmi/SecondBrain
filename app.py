"""SecondBrain — Streamlit UI."""

import datetime
import html
import json
import logging

import streamlit as st

import background_jobs
import config
import db
import evaluate
import ingest
import query

background_jobs.ensure_worker_running()

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
# Product-style visual layer that still plays well with native Streamlit widgets
# ---------------------------------------------------------------------------
_theme = config.theme()

_css = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

.stApp {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}}

/* ---- Header ---- */
.app-header {{
    background: linear-gradient(135deg, {_theme["gradient_start"]}, {_theme["gradient_end"]});
    padding: 1.4rem 1.8rem;
    border-radius: 12px;
    margin-bottom: 1rem;
}}
.app-header h1 {{
    color: #fff; font-size: 1.6rem; font-weight: 700; margin: 0 0 0.2rem 0;
}}
.app-header p {{
    color: rgba(255,255,255,0.8); font-size: 0.92rem; margin: 0; line-height: 1.5;
}}

/* ---- Metric cards ---- */
.metric-card {{
    border: 1px solid {_theme["border_color"]};
    border-radius: 10px;
    padding: 0.9rem 1rem;
    margin-bottom: 0.4rem;
}}
.metric-card .metric-kicker {{
    font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.08em;
    opacity: 0.5; margin-bottom: 0.2rem;
}}
.metric-card .metric-value {{
    font-size: 1.6rem; font-weight: 700; line-height: 1.1;
}}
.metric-card .metric-label {{
    font-size: 0.78rem; opacity: 0.55; margin-top: 0.15rem;
}}

/* ---- Pills / badges ---- */
.workspace-badge, .meta-pill {{
    display: inline-block;
    border: 1px solid {_theme["border_color"]};
    border-radius: 6px;
    padding: 0.18rem 0.55rem;
    font-size: 0.72rem;
    font-weight: 600;
    margin: 0 0.3rem 0.3rem 0;
}}
.workspace-badge {{
    background: {_theme["primary_color"]}18;
    border-color: {_theme["primary_color"]}44;
}}

/* ---- Sidebar panels ---- */
.sidebar-panel {{
    border: 1px solid {_theme["border_color"]};
    border-radius: 10px;
    padding: 0.8rem 0.9rem;
    margin-bottom: 0.7rem;
}}
.sidebar-panel h4 {{
    margin: 0 0 0.4rem 0; font-size: 0.72rem;
    text-transform: uppercase; letter-spacing: 0.08em; opacity: 0.5;
}}

/* ---- Divider ---- */
.section-divider {{
    height: 1px;
    background: linear-gradient(90deg, transparent, {_theme["border_color"]}, transparent);
    margin: 1rem 0; border: none;
}}

/* ---- Eval scores ---- */
.eval-score-1, .eval-score-2 {{ color: {_theme["error_color"]}; font-weight: 700; }}
.eval-score-3 {{ color: {_theme["warning_color"]}; font-weight: 700; }}
.eval-score-4, .eval-score-5 {{ color: {_theme["success_color"]}; font-weight: 700; }}

/* ---- Tabs ---- */
.stTabs [data-baseweb="tab-list"] {{ gap: 0.15rem; }}
.stTabs [data-baseweb="tab"] {{ padding: 0.4rem 0.9rem; font-weight: 600; font-size: 0.88rem; }}

/* ---- Misc ---- */
.source-summary {{ opacity: 0.6; font-size: 0.88rem; line-height: 1.45; }}
.source-tools {{ display: flex; flex-wrap: wrap; gap: 0.4rem; margin-top: 0.3rem; }}
.tiny-label {{ font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.08em; opacity: 0.5; font-weight: 600; }}
code {{ font-family: 'JetBrains Mono', monospace !important; }}
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
# Helpers
# ---------------------------------------------------------------------------
_ingest_cfg = config.ui("ingest")
_ask_cfg = config.ui("ask")
_ingestion_cfg = config.ingestion()
logger = logging.getLogger(__name__)


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


def _render_metric_card(value: str | int | float, label: str, kicker: str = "Workspace") -> None:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-kicker">{html.escape(kicker)}</div>
            <div class="metric-value">{html.escape(str(value))}</div>
            <div class="metric-label">{html.escape(label)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_badges(items: list[str], class_name: str = "meta-pill") -> str:
    return "".join(
        f'<span class="{class_name}">{html.escape(item)}</span>'
        for item in items if item
    )


def _format_model_name(model_id: str | None) -> str:
    if not model_id:
        return "default"
    model = next((m for m in config.models("embedding") if m["id"] == model_id), None)
    return model["name"] if model else model_id


def _source_preview(source_id: int, limit: int = 220) -> str:
    preview = db.get_chunk_preview_for_source(source_id).strip().replace("\n", " ")
    if not preview:
        return "No extracted text stored for this source yet."
    return preview[:limit] + ("..." if len(preview) > limit else "")


def _format_timestamp(value: str | None) -> str:
    if not value:
        return "Not started"
    try:
        parsed = datetime.datetime.fromisoformat(value)
    except ValueError:
        return value
    return parsed.astimezone().strftime("%Y-%m-%d %H:%M")


def _job_summary(job: dict) -> str:
    status = job.get("status")
    result = job.get("result") or {}
    if status == "pending":
        return "Queued and waiting for the worker."
    if status == "running":
        started_at = _format_timestamp(job.get("started_at"))
        return f"Running since {started_at}."
    if status == "cancelling":
        return "Cancellation requested. The worker will stop at the next safe checkpoint."
    if status == "cancelled":
        return "Cancelled."
    if status == "failed":
        return job.get("error") or "Job failed."
    if job.get("job_type") == "bulk_urls":
        return f"Completed {result.get('succeeded', 0)} of {result.get('total_urls', 0)} URLs."
    if "chunks" in result:
        return f"Stored {result['chunks']} chunks."
    return "Completed."


def _job_progress(job: dict) -> tuple[float, str] | None:
    total = int(job.get("progress_total") or 0)
    if total <= 0:
        return None
    current = int(job.get("progress_current") or 0)
    if job.get("status") in {"succeeded", "cancelled"}:
        current = total
    ratio = min(max(current / total, 0.0), 1.0)
    message = job.get("progress_message") or _job_summary(job)
    return ratio, f"{current}/{total} • {message}"

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

    workspace_stats = db.get_stats(workspace=active_workspace)
    workspace_usage = db.get_api_usage_stats(workspace=active_workspace)
    global_usage = db.get_api_usage_stats()
    workspace_models = db.get_embedding_models(workspace=active_workspace)

    st.markdown(
        f"""
        <div class="sidebar-panel">
            <h4>Workspace Snapshot</h4>
            <div class="source-tools">
                {_render_badges([
                    f"{workspace_stats['source_count']} sources",
                    f"{workspace_stats['chunk_count']} chunks",
                    f"{workspace_stats['query_count']} searches",
                ], class_name="workspace-badge")}
            </div>
            <div class="source-tools">
                {_render_badges(
                    [f"{len(workspace_models)} embedding model(s)"] + [_format_model_name(m) for m in workspace_models[:2]]
                )}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if workspace_usage["total_calls"] > 0 or global_usage["total_calls"] > 0:
        st.markdown(
            f"""
            <div class="sidebar-panel">
                <h4>Usage</h4>
                <div class="tiny-label">Current workspace</div>
                <div style="font-size:1.15rem; font-weight:800; margin:0.25rem 0 0.55rem 0;">
                    {workspace_usage['total_calls']} calls · ${workspace_usage['total_cost_usd']:.4f}
                </div>
                <div class="tiny-label">All workspaces</div>
                <div style="font-size:0.95rem; color: var(--muted);">
                    {global_usage['total_calls']} calls · ${global_usage['total_cost_usd']:.4f}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )



# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
_ui = config.ui()
tab_ingest, tab_ask, tab_history, tab_sources, tab_rss, tab_analytics, tab_eval = st.tabs(
    ["📥 Ingest", "💬 Ask", "📜 History", "📚 Sources", "📡 RSS Feeds", "📊 Analytics", "🧪 Eval"]
)


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

    col_embed, col_autotag, col_ocr, col_queue = st.columns([2, 1, 1, 1.2])
    with col_embed:
        embed_choice = st.selectbox("Embedding model", embed_names, index=default_idx)
        embed_model_id = embed_models[embed_names.index(embed_choice)]["id"]
    with col_autotag:
        use_autotag = st.toggle("Auto-tag with AI", value=False,
                                help="Use Claude to suggest tags automatically")
    with col_ocr:
        use_ocr = st.toggle("OCR for scanned PDFs", value=False,
                             help="Use Tesseract OCR for image-based PDFs")
    with col_queue:
        queue_ingest = st.toggle(
            _ingest_cfg.get("background_label", "Run in background"),
            value=True,
            help=_ingest_cfg.get(
                "background_help",
                "Queue ingestion in a background worker so the UI stays responsive.",
            ),
        )

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    if input_type == "Paste text":
        title = st.text_input("Title", placeholder=_ingest_cfg.get("paste_title_placeholder", ""))
        text = st.text_area("Content", placeholder=_ingest_cfg.get("paste_area_placeholder", "Paste content here"),
                            height=250)
        tags = _tag_input("tags_text")

        if use_autotag and text.strip():
            if st.button("💡 Suggest tags"):
                with st.spinner("Asking Claude for tag suggestions..."):
                    suggested = query.suggest_tags(text, workspace=active_workspace)
                st.info(f"Suggested: **{', '.join(suggested)}**")

        if st.button("Ingest", type="primary"):
            if not text.strip():
                st.error("Please paste some text.")
            elif not title.strip():
                st.error("Please provide a title.")
            elif queue_ingest:
                job_id = background_jobs.queue_text_ingest(
                    text,
                    title=title.strip(),
                    tags=tags,
                    workspace=active_workspace,
                    embed_model_id=embed_model_id,
                    auto_tag=use_autotag and not tags,
                )
                st.success(f'Queued background job #{job_id} for "{title.strip()}".')
            else:
                if use_autotag and not tags:
                    with st.spinner("Auto-tagging..."):
                        tags = query.suggest_tags(text, workspace=active_workspace)
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
            elif queue_ingest:
                job_id = background_jobs.queue_url_ingest(
                    url.strip(),
                    title=title.strip() or None,
                    tags=tags,
                    workspace=active_workspace,
                    embed_model_id=embed_model_id,
                    auto_tag=use_autotag and not tags,
                )
                st.success(f"Queued background job #{job_id} for {url.strip()}.")
            else:
                with st.spinner("Fetching and processing..."):
                    try:
                        text_content, js_warn = ingest.fetch_url_text(url.strip())
                        effective_tags = tags
                        if use_autotag and not effective_tags and text_content.strip():
                            effective_tags = query.suggest_tags(text_content, workspace=active_workspace)
                        n = ingest.ingest_text(
                            text_content,
                            title=title.strip() or url.strip(),
                            source_type="url",
                            url=url.strip(),
                            tags=effective_tags,
                            workspace=active_workspace,
                            embed_model_id=embed_model_id,
                        )
                        if js_warn:
                            st.warning(f"Only {n} chunk(s) — page likely requires JavaScript.")
                        else:
                            st.success(
                                f"Ingested **{n}** chunks."
                                + (f" Tags: {', '.join(effective_tags)}." if effective_tags else "")
                            )
                    except Exception as e:
                        st.error(f"Failed: {e}")

    elif input_type == "File upload":
        file_help = _ingest_cfg.get("file_help", "")
        max_upload_mb = _ingestion_cfg.get("max_upload_mb")
        if max_upload_mb:
            upload_note = f"Max upload: {max_upload_mb} MB"
            file_help = f"{file_help}. {upload_note}" if file_help else upload_note
        uploaded = st.file_uploader("Upload a file",
                                    type=["pdf", "docx", "txt", "md", "csv", "json", "rst"],
                                    help=file_help)
        title = st.text_input("Title", placeholder="e.g. AWS Security Whitepaper")
        tags = _tag_input("tags_file")
        if st.button("Ingest file", type="primary"):
            if uploaded is None:
                st.error("Please upload a file.")
            elif not title.strip():
                st.error("Please provide a title.")
            elif max_upload_mb and uploaded.size > int(max_upload_mb) * 1024 * 1024:
                st.error(
                    f'File is {uploaded.size / (1024 * 1024):.1f} MB, which exceeds the '
                    f"configured limit of {max_upload_mb} MB."
                )
            else:
                file_bytes = uploaded.read()
                if queue_ingest:
                    job_id = background_jobs.queue_file_ingest(
                        file_bytes,
                        uploaded.name,
                        title=title.strip(),
                        tags=tags,
                        workspace=active_workspace,
                        embed_model_id=embed_model_id,
                        ocr=use_ocr,
                        auto_tag=use_autotag and not tags,
                    )
                    st.success(f'Queued background job #{job_id} for "{title.strip()}".')
                else:
                    logger.info(
                        "Starting file ingest for '%s' (%s bytes) in workspace=%s",
                        uploaded.name,
                        uploaded.size,
                        active_workspace,
                    )
                    if use_autotag and not tags:
                        with st.spinner("Auto-tagging..."):
                            preview = file_bytes[:3000].decode("utf-8", errors="replace")
                            tags = query.suggest_tags(preview, workspace=active_workspace)
                    with st.spinner("Extracting and embedding..."):
                        n = ingest.ingest_file(file_bytes, uploaded.name, title=title.strip(), tags=tags,
                                               workspace=active_workspace, embed_model_id=embed_model_id,
                                               ocr=use_ocr)
                    st.success(f'Ingested **{n}** chunks from "{title.strip()}"')

    elif input_type == "YouTube":
        url = st.text_input("YouTube URL", placeholder=_ingest_cfg.get("youtube_placeholder", ""))
        title = st.text_input("Title (optional)", placeholder="Defaults to URL")
        tags = _tag_input("tags_yt")
        st.caption(_ingest_cfg.get("youtube_caption", ""))
        if st.button("Ingest transcript", type="primary"):
            if not url.strip():
                st.error("Please enter a YouTube URL.")
            elif queue_ingest:
                job_id = background_jobs.queue_youtube_ingest(
                    url.strip(),
                    title=title.strip() or None,
                    tags=tags,
                    workspace=active_workspace,
                    embed_model_id=embed_model_id,
                    auto_tag=use_autotag and not tags,
                )
                st.success(f"Queued background job #{job_id} for the transcript import.")
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
            elif queue_ingest:
                job_id = background_jobs.queue_bulk_url_ingest(
                    urls,
                    tags=tags,
                    workspace=active_workspace,
                    embed_model_id=embed_model_id,
                    auto_tag=use_autotag and not tags,
                )
                st.success(f"Queued background job #{job_id} for {len(urls)} URLs.")
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

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    jobs_header_col, jobs_refresh_col = st.columns([4, 1])
    with jobs_header_col:
        st.subheader(_ingest_cfg.get("jobs_heading", "Background Jobs"))
        worker_state = background_jobs.embedded_worker_status()
        if worker_state == "disabled":
            st.caption("Embedded worker disabled. Run `python worker.py` or use the Docker worker service.")
        elif worker_state == "online":
            st.caption("Embedded worker online. Jobs can also be picked up by standalone workers.")
        else:
            st.caption("Embedded worker starting.")
    with jobs_refresh_col:
        st.button("Refresh", key="refresh_background_jobs", use_container_width=True)

    jobs = background_jobs.list_jobs(limit=12, workspace=active_workspace)
    if not jobs:
        st.info(_ingest_cfg.get("jobs_empty_message", "No ingestion jobs yet."))
    else:
        pending_jobs = sum(1 for job in jobs if job["status"] == "pending")
        active_jobs = sum(1 for job in jobs if job["status"] in {"running", "cancelling"})
        failed_jobs = sum(1 for job in jobs if job["status"] == "failed")
        completed_jobs = sum(1 for job in jobs if job["status"] in {"succeeded", "cancelled"})
        job_col1, job_col2, job_col3, job_col4 = st.columns(4)
        with job_col1:
            _render_metric_card(pending_jobs, "Pending", kicker="Jobs")
        with job_col2:
            _render_metric_card(active_jobs, "Active", kicker="Jobs")
        with job_col3:
            _render_metric_card(completed_jobs, "Completed", kicker="Jobs")
        with job_col4:
            _render_metric_card(failed_jobs, "Failed", kicker="Jobs")

        for job in jobs:
            with st.container(border=True):
                content_col, action_col = st.columns([6, 1])
                with content_col:
                    st.markdown(f"**{job['title']}**")
                    st.markdown(
                        _render_badges(
                            [
                                f"#{job['id']}",
                                job["job_type"].replace("_", " "),
                                job["status"],
                                job["workspace"],
                            ]
                        ),
                        unsafe_allow_html=True,
                    )
                    st.caption(
                        f"Queued {_format_timestamp(job.get('created_at'))}"
                        + (
                            f" • Finished {_format_timestamp(job.get('finished_at'))}"
                            if job.get("finished_at")
                            else ""
                        )
                    )
                    st.caption(
                        f"Attempts: {job.get('attempt_count', 0)}"
                        + (
                            f" • Last heartbeat {_format_timestamp(job.get('heartbeat_at'))}"
                            if job.get("heartbeat_at")
                            else ""
                        )
                    )
                    progress = _job_progress(job)
                    if progress is not None:
                        st.progress(progress[0], text=progress[1])
                    summary = _job_summary(job)
                    if job["status"] == "failed":
                        st.error(summary)
                    elif job["status"] in {"cancelled", "cancelling"}:
                        st.warning(summary)
                    elif job["status"] == "succeeded":
                        st.success(summary)
                    else:
                        st.caption(summary)

                    if job["job_type"] == "bulk_urls" and job.get("result", {}).get("results"):
                        with st.expander("Batch details", expanded=False):
                            for item in job["result"]["results"]:
                                if item.get("error"):
                                    st.error(f"{item['url']} — {item['error']}")
                                elif item.get("warning"):
                                    st.warning(f"{item['url']} — {item.get('chunks', 0)} chunks (JS-rendered)")
                                else:
                                    st.write(f"{item['url']} — {item.get('chunks', 0)} chunks")
                with action_col:
                    if job["status"] in {"pending", "running"} and st.button(
                        "Cancel" if job["status"] == "pending" else "Stop",
                        key=f"cancel_job_{job['id']}",
                        use_container_width=True,
                    ):
                        cancel_status = background_jobs.cancel_job(job["id"])
                        if cancel_status == "cancelled":
                            st.success(f"Cancelled job #{job['id']}.")
                            st.rerun()
                        if cancel_status == "cancelling":
                            st.warning(f"Cancellation requested for job #{job['id']}.")
                            st.rerun()
                        st.warning(f"Job #{job['id']} could not be cancelled.")


# ---------------------------------------------------------------------------
# ASK TAB
# ---------------------------------------------------------------------------

with tab_ask:
    st.subheader(_ask_cfg.get("heading", "Ask Your Knowledge Base"))
    if "reask_question" in st.session_state:
        st.session_state["ask_question"] = st.session_state.pop("reask_question")

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
        question = st.text_input(
            "Your question",
            placeholder=_ask_cfg.get("question_placeholder", ""),
            label_visibility="collapsed",
            key="ask_question",
        )
        col_ask, col_clear = st.columns([1, 5])
        with col_ask:
            ask_clicked = st.form_submit_button("Ask", type="primary", use_container_width=True)
        with col_clear:
            clear_clicked = st.form_submit_button("Clear conversation")

    if clear_clicked:
        for k in ["chat_history", "last_result", "last_question", "ask_question"]:
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
            db.log_search(
                question.strip(),
                full_answer,
                sources,
                selected_tags or [],
                workspace=active_workspace,
            )
        else:
            with st.spinner("Searching..."):
                result = query.ask(question.strip(), history=st.session_state["chat_history"],
                                   tags=selected_tags or None, use_rerank=use_rerank, hybrid=use_hybrid,
                                   model_id=model_id, min_similarity=min_sim, workspace=active_workspace)
            st.session_state["chat_history"] = result["history"]
            st.session_state["last_result"] = result
            st.session_state["last_question"] = question.strip()
            db.log_search(
                question.strip(),
                result["answer"],
                result.get("sources", []),
                selected_tags or [],
                workspace=active_workspace,
            )
    elif ask_clicked:
        st.warning("Please enter a question.")

    # Display conversation
    if st.session_state["chat_history"]:
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        turns = st.session_state["chat_history"]
        for i in range(0, len(turns) - 1, 2):
            u = turns[i]["content"]
            a = turns[i + 1]["content"] if i + 1 < len(turns) else ""
            with st.chat_message("user"):
                st.markdown(u)
            with st.chat_message("assistant"):
                st.markdown(a)

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
    history_items = db.get_search_history(limit=50, workspace=active_workspace)
    if not history_items:
        st.info(config.ui("history").get("empty_message", "No searches yet."))
    else:
        col_count, col_clear = st.columns([3, 1])
        with col_count:
            st.caption(f"{len(history_items)} recent searches in {active_workspace}")
        with col_clear:
            if st.button("Clear workspace history", type="secondary"):
                db.delete_search_history(workspace=active_workspace)
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

    col_search, col_filter, col_export = st.columns([2, 2, 1])
    with col_search:
        source_query = st.text_input("Search sources", placeholder="Filter by title or URL", key="src_query")
    with col_filter:
        filter_tags = st.multiselect("Filter by tag", options=db.get_all_tags(workspace=active_workspace), key="src_ft")
    with col_export:
        if st.button("Export KB"):
            with st.spinner("Exporting..."):
                export_data = ingest.export_knowledge_base(workspace=active_workspace)
            st.session_state["kb_export_payload"] = json.dumps(export_data, indent=2)
            st.session_state["kb_export_workspace"] = active_workspace

    if (
        st.session_state.get("kb_export_payload")
        and st.session_state.get("kb_export_workspace") == active_workspace
    ):
        st.download_button(
            "Download JSON",
            data=st.session_state["kb_export_payload"],
            file_name=f"secondbrain_export_{datetime.date.today()}.json",
            mime="application/json",
        )

    sources = db.get_all_sources(workspace=active_workspace)
    if source_query.strip():
        q = source_query.strip().lower()
        sources = [
            s for s in sources
            if q in s["title"].lower() or q in (s.get("url") or "").lower()
        ]
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
                    st.markdown(
                        _render_badges(
                            [
                                src["source_type"],
                                _format_model_name(src.get("embedding_model")),
                                f"{len(src.get('tags') or [])} tag(s)",
                            ]
                            + list(src.get("tags") or []),
                        ),
                        unsafe_allow_html=True,
                    )
                    if src.get("url"):
                        st.caption(src["url"])
                    st.markdown(
                        f'<div class="source-summary">{html.escape(_source_preview(src["id"]))}</div>',
                        unsafe_allow_html=True,
                    )
                    current_tags = ", ".join(src.get("tags") or [])
                    new_tags = st.text_input("Tags", value=current_tags, key=f"tags_{src['id']}")
                    if st.button("Save tags", key=f"st_{src['id']}"):
                        try:
                            ingest.update_source_tags(
                                src["id"],
                                [t.strip() for t in new_tags.split(",") if t.strip()],
                            )
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to save tags: {e}")
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
                            try:
                                ingest.update_chunk_text(c["id"], edited)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed to save chunk: {e}")


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

    stats = db.get_stats(workspace=active_workspace)
    usage = db.get_api_usage_stats(workspace=active_workspace)
    sources_in_workspace = db.get_all_sources(workspace=active_workspace)
    model_breakdown: dict[str, int] = {}
    for src in sources_in_workspace:
        model_name = _format_model_name(src.get("embedding_model"))
        model_breakdown[model_name] = model_breakdown.get(model_name, 0) + 1

    col1, col2, col3, col4 = st.columns(4)
    for col, val, label in [(col1, stats["source_count"], "Sources"),
                             (col2, stats["chunk_count"], "Chunks"),
                             (col3, stats["query_count"], "Queries"),
                             (col4, f"${usage['total_cost_usd']:.4f}", "API Cost")]:
        with col:
            st.markdown(f'<div class="metric-card"><div class="metric-value">{val}</div>'
                        f'<div class="metric-label">{label}</div></div>', unsafe_allow_html=True)

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    col_types, col_tags, col_models = st.columns(3)
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
    with col_models:
        st.markdown("#### Embedding Models")
        if model_breakdown:
            mx = max(model_breakdown.values())
            for model_name, count in sorted(model_breakdown.items(), key=lambda item: item[1], reverse=True):
                st.markdown(f"**{model_name}** — {count}")
                st.progress(count / mx)
        else:
            st.caption("No embeddings yet.")

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
                with st.expander(
                    f"{d['similarity']:.2%} — {d['title_a']} / {d['title_b']} [{d['embedding_model']}]"
                ):
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
