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
import runtime_checks

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
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

:root {{
    --sb-primary: {_theme["primary_color"]};
    --sb-secondary: {_theme["secondary_color"]};
    --sb-bg: {_theme["background_dark"]};
    --sb-surface: {_theme["surface_color"]};
    --sb-surface-hover: {_theme["surface_hover"]};
    --sb-text: {_theme["text_primary"]};
    --sb-muted: {_theme["text_secondary"]};
    --sb-border: {_theme["border_color"]};
    --sb-success: {_theme["success_color"]};
    --sb-warning: {_theme["warning_color"]};
    --sb-error: {_theme["error_color"]};
}}

.stApp {{
    font-family: 'Space Grotesk', sans-serif;
    color: var(--sb-text);
    background:
        radial-gradient(circle at top left, {_theme["gradient_start"]}55, transparent 30%),
        radial-gradient(circle at top right, {_theme["secondary_color"]}22, transparent 22%),
        linear-gradient(180deg, var(--sb-bg) 0%, #050a14 100%);
}}

[data-testid="stAppViewContainer"] > .main {{
    background: transparent;
}}

[data-testid="stSidebar"] {{
    background:
        linear-gradient(180deg, rgba(6, 13, 25, 0.98) 0%, rgba(8, 18, 34, 0.94) 100%);
    border-right: 1px solid {_theme["border_color"]};
}}

.block-container {{
    max-width: 1280px;
    padding-top: 1.4rem;
    padding-bottom: 2.5rem;
}}

.app-header {{
    position: relative;
    overflow: hidden;
    background:
        radial-gradient(circle at top right, {_theme["secondary_color"]}35, transparent 32%),
        linear-gradient(135deg, {_theme["gradient_start"]}, {_theme["gradient_end"]});
    border: 1px solid {_theme["border_color"]};
    box-shadow: 0 18px 60px rgba(0, 0, 0, 0.28);
    padding: 1.7rem 1.8rem;
    border-radius: 22px;
    margin-bottom: 1rem;
}}

.app-header::after {{
    content: "";
    position: absolute;
    inset: auto -10% -60% auto;
    width: 18rem;
    height: 18rem;
    background: {_theme["primary_color"]}18;
    filter: blur(10px);
    border-radius: 999px;
}}

.app-header h1 {{
    color: #fff;
    font-size: 2.15rem;
    font-weight: 700;
    letter-spacing: -0.04em;
    margin: 0 0 0.35rem 0;
}}

.app-header p {{
    color: rgba(255,255,255,0.82);
    font-size: 0.98rem;
    margin: 0;
    line-height: 1.55;
    max-width: 56rem;
}}

.metric-card, .sidebar-panel, .guide-card, .status-card, .status-banner {{
    background: linear-gradient(180deg, rgba(12, 22, 39, 0.86) 0%, rgba(8, 16, 30, 0.94) 100%);
    border: 1px solid {_theme["border_color"]};
    box-shadow: 0 14px 40px rgba(0, 0, 0, 0.18);
}}

.metric-card {{
    border-radius: 18px;
    padding: 1rem 1.1rem;
    margin-bottom: 0.45rem;
    min-height: 8.2rem;
}}

.metric-card .metric-kicker {{
    color: var(--sb-muted);
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    margin-bottom: 0.35rem;
}}

.metric-card .metric-value {{
    color: #fff;
    font-size: 1.9rem;
    font-weight: 700;
    letter-spacing: -0.03em;
    line-height: 1.05;
}}

.metric-card .metric-label {{
    color: var(--sb-muted);
    font-size: 0.84rem;
    line-height: 1.45;
    margin-top: 0.35rem;
}}

.workspace-badge, .meta-pill, .status-pill {{
    display: inline-block;
    border-radius: 999px;
    padding: 0.22rem 0.62rem;
    font-size: 0.72rem;
    font-weight: 600;
    margin: 0 0.3rem 0.3rem 0;
    border: 1px solid {_theme["border_color"]};
}}

.workspace-badge {{
    background: {_theme["primary_color"]}14;
    border-color: {_theme["primary_color"]}55;
}}

.status-pass {{
    border-color: {_theme["success_color"]}55;
}}

.status-pass .status-pill {{
    background: {_theme["success_color"]}18;
    border-color: {_theme["success_color"]}55;
}}

.status-warning {{
    border-color: {_theme["warning_color"]}55;
}}

.status-warning .status-pill {{
    background: {_theme["warning_color"]}1A;
    border-color: {_theme["warning_color"]}55;
}}

.status-fail {{
    border-color: {_theme["error_color"]}55;
}}

.status-fail .status-pill {{
    background: {_theme["error_color"]}16;
    border-color: {_theme["error_color"]}55;
}}

.sidebar-panel {{
    border-radius: 18px;
    padding: 0.95rem 1rem;
    margin-bottom: 0.8rem;
}}

.sidebar-panel h4 {{
    color: var(--sb-muted);
    margin: 0 0 0.5rem 0;
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.14em;
}}

.guide-card {{
    border-radius: 18px;
    padding: 1rem 1.05rem;
    min-height: 10rem;
}}

.guide-card h4, .status-card h4 {{
    margin: 0 0 0.4rem 0;
    color: #fff;
    font-size: 1rem;
}}

.guide-card p, .status-card p, .status-banner p {{
    margin: 0;
    color: var(--sb-muted);
    font-size: 0.9rem;
    line-height: 1.55;
}}

.guide-kicker, .status-kicker, .tiny-label {{
    color: var(--sb-muted);
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    font-weight: 600;
}}

.status-card {{
    border-radius: 16px;
    padding: 0.95rem 1rem;
    margin-bottom: 0.7rem;
}}

.status-banner {{
    border-radius: 18px;
    padding: 1rem 1.1rem;
    margin: 0 0 1rem 0;
}}

.section-divider {{
    height: 1px;
    background: linear-gradient(90deg, transparent, {_theme["border_color"]}, transparent);
    margin: 1.2rem 0;
    border: none;
}}

.eval-score-1, .eval-score-2 {{ color: {_theme["error_color"]}; font-weight: 700; }}
.eval-score-3 {{ color: {_theme["warning_color"]}; font-weight: 700; }}
.eval-score-4, .eval-score-5 {{ color: {_theme["success_color"]}; font-weight: 700; }}

.stTabs [data-baseweb="tab-list"] {{
    gap: 0.35rem;
    padding: 0.2rem;
    background: rgba(8, 15, 28, 0.72);
    border: 1px solid {_theme["border_color"]};
    border-radius: 18px;
}}

.stTabs [data-baseweb="tab"] {{
    padding: 0.6rem 1rem;
    font-weight: 600;
    font-size: 0.88rem;
    border-radius: 14px;
}}

.source-summary {{
    opacity: 0.8;
    font-size: 0.9rem;
    line-height: 1.55;
}}

.source-tools {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
    margin-top: 0.35rem;
}}

.stButton > button, .stDownloadButton > button {{
    border-radius: 12px;
    border: 1px solid {_theme["border_color"]};
}}

code {{
    font-family: 'IBM Plex Mono', monospace !important;
}}

/* Follow-up buttons */
.stButton > button[kind="secondary"] {{
    transition: all 0.2s ease;
}}

.stButton > button:hover {{
    transform: translateY(-1px);
    box-shadow: 0 4px 16px rgba(59, 130, 246, 0.15);
}}

/* Strategy badges animation */
.meta-pill {{
    transition: all 0.2s ease;
}}

/* Discover tab cards */
.discover-card {{
    background: linear-gradient(180deg, rgba(12, 22, 39, 0.86) 0%, rgba(8, 16, 30, 0.94) 100%);
    border: 1px solid {_theme["border_color"]};
    border-radius: 16px;
    padding: 1rem;
    margin-bottom: 0.7rem;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.12);
}}

/* Smooth chat messages */
[data-testid="stChatMessage"] {{
    border-radius: 16px;
    border: 1px solid {_theme["border_color"]};
    margin-bottom: 0.5rem;
}}

/* Better expander styling */
details[data-testid="stExpander"] {{
    border-radius: 16px;
    border: 1px solid {_theme["border_color"]};
    overflow: hidden;
}}

/* Progress bar theming */
.stProgress > div > div > div {{
    background: linear-gradient(90deg, {_theme["primary_color"]}, {_theme["secondary_color"]});
    border-radius: 8px;
}}

/* Toggle switches */
.stToggle label {{
    font-size: 0.88rem;
}}

/* Chart container */
[data-testid="stVegaLiteChart"] {{
    border-radius: 12px;
    overflow: hidden;
}}
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
def _status_label(status: str) -> str:
    return {
        "ok": "Healthy",
        "degraded": "Needs attention",
        "fail": "Blocked",
        "pass": "Ready",
        "warning": "Attention",
    }.get(status, status.title())


def _status_class(status: str) -> str:
    return {
        "ok": "status-pass",
        "pass": "status-pass",
        "degraded": "status-warning",
        "warning": "status-warning",
        "fail": "status-fail",
    }.get(status, "status-warning")


def _render_guide_card(kicker: str, title: str, body: str) -> str:
    return f"""
    <div class="guide-card">
        <div class="guide-kicker">{html.escape(kicker)}</div>
        <h4>{html.escape(title)}</h4>
        <p>{html.escape(body)}</p>
    </div>
    """


def _render_status_cards(system_status: dict) -> str:
    cards = []
    for check in system_status.get("checks", []):
        hint = (
            f'<p style="margin-top:0.55rem;"><span class="status-kicker">Suggested action</span><br>{html.escape(check["hint"])}</p>'
            if check.get("hint")
            else ""
        )
        cards.append(
            f"""
            <div class="status-card {_status_class(check["status"])}">
                <div class="status-kicker">{html.escape(check["label"])}</div>
                <h4><span class="status-pill">{html.escape(_status_label(check["status"]))}</span></h4>
                <p>{html.escape(check["detail"])}</p>
                {hint}
            </div>
            """
        )
    return "".join(cards)


def _workspace_display(name: str, predefined_map: dict[str, dict]) -> str:
    match = predefined_map.get(name, {})
    icon = match.get("icon", "Folder")
    description = match.get("description", "Saved workspace")
    return f"{icon} {name} - {description}"


ws_cfg = config.workspaces()
with st.sidebar:
    if ws_cfg.get("enabled"):
        st.markdown("### Workspace")
        predefined = ws_cfg.get("predefined", [])
        predefined_map = {workspace["name"]: workspace for workspace in predefined}
        ws_names = list(dict.fromkeys([w["name"] for w in predefined] + db.get_workspaces()))
        if not ws_names:
            ws_names = [ws_cfg.get("default", "default")]

        if (
            "active_workspace" not in st.session_state
            or st.session_state["active_workspace"] not in ws_names
        ):
            default_workspace = ws_cfg.get("default", "default")
            st.session_state["active_workspace"] = (
                default_workspace if default_workspace in ws_names else ws_names[0]
            )

        active_workspace = st.selectbox(
            "Active workspace",
            ws_names,
            index=ws_names.index(st.session_state["active_workspace"]),
            format_func=lambda name: _workspace_display(name, predefined_map),
            label_visibility="collapsed",
        )
        st.session_state["active_workspace"] = active_workspace

        with st.expander("New workspace"):
            new_ws_name = st.text_input("Name", placeholder="e.g. projects", key="new_ws")
            new_ws_description = st.text_input(
                "Description",
                placeholder="What belongs in this workspace?",
                key="new_ws_description",
            )
            if st.button("Create") and new_ws_name.strip():
                try:
                    created_workspace = db.create_workspace(
                        new_ws_name,
                        description=new_ws_description.strip() or None,
                    )
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    st.session_state["active_workspace"] = created_workspace
                    st.rerun()

        st.markdown(f'<div class="workspace-badge">Active: {active_workspace}</div>', unsafe_allow_html=True)
    else:
        active_workspace = "default"

    workspace_stats = db.get_stats(workspace=active_workspace)
    workspace_usage = db.get_api_usage_stats(workspace=active_workspace)
    global_usage = db.get_api_usage_stats()
    workspace_models = db.get_embedding_models(workspace=active_workspace)
    system_status = runtime_checks.collect_system_status()

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

    st.markdown(
        f"""
        <div class="sidebar-panel {_status_class(system_status['status'])}">
            <h4>System Status</h4>
            <div class="source-tools">
                <span class="status-pill">{html.escape(_status_label(system_status['status']))}</span>
                <span class="meta-pill">{system_status['summary']['passed']}/{system_status['summary']['total']} checks</span>
            </div>
            <div class="source-summary" style="margin-top:0.3rem;">
                Data persists in <code>{html.escape(system_status['paths']['data_dir'])}</code>.
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
                    {workspace_usage['total_calls']} calls | ${workspace_usage['total_cost_usd']:.4f}
                </div>
                <div class="tiny-label">All workspaces</div>
                <div style="font-size:0.95rem; color: var(--sb-muted);">
                    {global_usage['total_calls']} calls | ${global_usage['total_cost_usd']:.4f}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

hero_col1, hero_col2, hero_col3, hero_col4 = st.columns(4)
with hero_col1:
    _render_metric_card(active_workspace, "Current workspace", kicker="Command")
with hero_col2:
    _render_metric_card(workspace_stats["source_count"], "Stored sources", kicker="Library")
with hero_col3:
    _render_metric_card(background_jobs.embedded_worker_status().title(), "Queue worker", kicker="Ingest")
with hero_col4:
    _render_metric_card(
        f"{system_status['summary']['passed']}/{system_status['summary']['total']}",
        _status_label(system_status["status"]),
        kicker="Validation",
    )

st.markdown(
    f"""
    <div class="status-banner {_status_class(system_status['status'])}">
        <p>{html.escape(system_status['persistence']['detail'])} Back up or mount <code>{html.escape(system_status['paths']['data_dir'])}</code> to keep your knowledge base across restarts.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
_ui = config.ui()
tab_ingest, tab_ask, tab_history, tab_sources, tab_discover, tab_rss, tab_analytics, tab_eval = st.tabs(
    ["📥 Ingest", "💬 Ask", "📜 History", "📚 Sources", "🔗 Discover", "📡 RSS Feeds", "📊 Analytics", "🧪 Eval"]
)


# ---------------------------------------------------------------------------
# INGEST TAB
# ---------------------------------------------------------------------------

with tab_ingest:
    st.subheader(_ingest_cfg.get("heading", "Add Knowledge"))

    guide_col1, guide_col2, guide_col3 = st.columns(3)
    with guide_col1:
        st.markdown(
            _render_guide_card(
                "Capture",
                "Ingest from any starting point",
                "Paste notes, save URLs, import files, or pull transcripts and RSS entries into the same workspace.",
            ),
            unsafe_allow_html=True,
        )
    with guide_col2:
        st.markdown(
            _render_guide_card(
                "Persist",
                "Keep data on local disk",
                f"Metadata and vectors persist under {system_status['paths']['data_dir']}. Keep that directory between restarts.",
            ),
            unsafe_allow_html=True,
        )
    with guide_col3:
        st.markdown(
            _render_guide_card(
                "Operate",
                "Queue larger imports",
                "Use background jobs for heavier imports so the UI stays responsive while the worker updates the library.",
            ),
            unsafe_allow_html=True,
        )

    with st.expander("Setup and validation", expanded=system_status["status"] != "ok" or workspace_stats["source_count"] == 0):
        st.markdown(
            f'<div class="source-summary">{html.escape(system_status["persistence"]["detail"])} Current storage root: <code>{html.escape(system_status["paths"]["data_dir"])}.</code></div>',
            unsafe_allow_html=True,
        )
        st.markdown(_render_status_cards(system_status), unsafe_allow_html=True)

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

    elif input_type == "Image":
        st.caption("Upload an image — Claude Vision will extract text, describe diagrams, and analyse the content.")
        uploaded_img = st.file_uploader("Upload an image",
                                        type=["png", "jpg", "jpeg", "gif", "webp"],
                                        help="Supported: PNG, JPG, GIF, WebP")
        title = st.text_input("Title", placeholder="e.g. Architecture Diagram — Auth Flow", key="img_title")
        tags = _tag_input("tags_img")
        if st.button("Analyse & Ingest", type="primary"):
            if uploaded_img is None:
                st.error("Please upload an image.")
            elif not title.strip():
                st.error("Please provide a title.")
            else:
                img_bytes = uploaded_img.read()
                # Determine media type
                ext = uploaded_img.name.rsplit(".", 1)[-1].lower() if "." in uploaded_img.name else "png"
                media_map = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                             "gif": "image/gif", "webp": "image/webp"}
                media_type = media_map.get(ext, "image/png")
                with st.spinner("Analysing image with Claude Vision..."):
                    extracted_text = query.analyse_image(img_bytes, media_type=media_type)
                st.markdown("**Extracted content preview:**")
                st.markdown(extracted_text[:500] + ("..." if len(extracted_text) > 500 else ""))
                with st.spinner("Chunking and embedding..."):
                    effective_tags = tags
                    if use_autotag and not effective_tags:
                        effective_tags = query.suggest_tags(extracted_text, workspace=active_workspace)
                    n = ingest.ingest_text(
                        extracted_text,
                        title=title.strip(),
                        source_type="image",
                        tags=effective_tags,
                        workspace=active_workspace,
                        embed_model_id=embed_model_id,
                    )
                st.success(f"Ingested **{n}** chunks from image analysis."
                           + (f" Tags: {', '.join(effective_tags)}." if effective_tags else ""))

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
    jobs_header_col, jobs_toggle_col, jobs_refresh_col = st.columns([3.2, 1.5, 1])
    with jobs_header_col:
        st.subheader(_ingest_cfg.get("jobs_heading", "Background Jobs"))
        worker_state = background_jobs.embedded_worker_status()
        if worker_state == "disabled":
            st.caption("Embedded worker disabled. Run `python worker.py` or use the Docker worker service.")
        elif worker_state == "online":
            st.caption("Embedded worker online. Jobs can also be picked up by standalone workers.")
        else:
            st.caption("Embedded worker starting.")
    with jobs_toggle_col:
        auto_refresh_jobs = st.toggle(
            "Auto-refresh queue",
            value=True,
            key=f"jobs_autorefresh_{active_workspace}",
            help="Refresh the jobs panel every 3 seconds while this toggle is enabled.",
        )
    with jobs_refresh_col:
        st.button("Refresh", key="refresh_background_jobs", use_container_width=True)

    @st.fragment(run_every="3s" if auto_refresh_jobs else None)
    def _render_jobs_fragment() -> None:
        if auto_refresh_jobs:
            st.caption("Queue updates every 3 seconds while auto-refresh is enabled.")

        jobs = background_jobs.list_jobs(limit=12, workspace=active_workspace)
        if not jobs:
            st.info(_ingest_cfg.get("jobs_empty_message", "No ingestion jobs yet."))
            return

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
                            f" | Finished {_format_timestamp(job.get('finished_at'))}"
                            if job.get("finished_at")
                            else ""
                        )
                    )
                    st.caption(
                        f"Attempts: {job.get('attempt_count', 0)}"
                        + (
                            f" | Last heartbeat {_format_timestamp(job.get('heartbeat_at'))}"
                            if job.get("heartbeat_at")
                            else ""
                        )
                    )
                    progress = _job_progress(job)
                    if progress is not None:
                        progress_text = progress[1].replace("•", "|")
                        st.progress(progress[0], text=progress_text)
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
                                    st.error(f"{item['url']} | {item['error']}")
                                elif item.get("warning"):
                                    st.warning(f"{item['url']} | {item.get('chunks', 0)} chunks (JS-rendered)")
                                else:
                                    st.write(f"{item['url']} | {item.get('chunks', 0)} chunks")
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

    _render_jobs_fragment()

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
            use_streaming = st.toggle(_ask_cfg.get("stream_label", "Stream response"),
                                      value=config.retrieval().get("default_stream", True))
        with col2:
            use_hyde = st.toggle(_ask_cfg.get("hyde_label", "HyDE retrieval"),
                                 value=config.retrieval().get("default_hyde", False),
                                 help=_ask_cfg.get("hyde_help", ""))
            use_decompose = st.toggle(_ask_cfg.get("decompose_label", "Query decomposition"),
                                      value=config.retrieval().get("default_decompose", False),
                                      help=_ask_cfg.get("decompose_help", ""))
            use_compress = st.toggle(_ask_cfg.get("compress_label", "Contextual compression"),
                                     value=config.retrieval().get("default_compress", False),
                                     help=_ask_cfg.get("compress_help", ""))
        with col3:
            all_tags = db.get_all_tags(workspace=active_workspace)
            selected_tags = st.multiselect("Filter by tags", options=all_tags)
            min_sim = st.slider(_ask_cfg.get("threshold_label", "Min similarity"),
                                0.0, 1.0, config.retrieval().get("min_similarity", 0.0), 0.05)
        col4, col5 = st.columns(2)
        with col4:
            llm_models = config.models("llm")
            llm_names = [m["name"] for m in llm_models]
            default_llm = next((i for i, m in enumerate(llm_models) if m.get("default")), 0)
            model_choice = st.selectbox(_ask_cfg.get("model_label", "Claude model"), llm_names, index=default_llm)
            model_id = llm_models[llm_names.index(model_choice)]["id"]
        with col5:
            use_followups = st.toggle("Suggest follow-ups",
                                      value=config.retrieval().get("default_followups", True),
                                      help="Generate follow-up question suggestions after each answer")

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
        # Show active retrieval strategy badges
        active_strategies = []
        if use_hybrid:
            active_strategies.append("Hybrid")
        if use_hyde:
            active_strategies.append("HyDE")
        if use_decompose:
            active_strategies.append("Decompose")
        if use_rerank:
            active_strategies.append("Rerank")
        if use_compress:
            active_strategies.append("Compress")
        if active_strategies:
            st.markdown(
                _render_badges([f"⚡ {s}" for s in active_strategies]),
                unsafe_allow_html=True,
            )

        if use_streaming:
            sources = []
            answer_placeholder = st.empty()
            full_answer = ""
            final_history = None
            with st.spinner("Retrieving..." + (" (HyDE)" if use_hyde else "") + (" (Decomposing)" if use_decompose else "")):
                # Advanced retrieval pre-processing
                if use_decompose:
                    sub_qs = query.decompose_query(question.strip(), workspace=active_workspace)
                    if len(sub_qs) > 1:
                        st.caption(f"Decomposed into {len(sub_qs)} sub-queries: {', '.join(sub_qs)}")

                stream = query.ask_stream(question.strip(), history=st.session_state["chat_history"],
                                          tags=selected_tags or None, use_rerank=use_rerank, hybrid=use_hybrid,
                                          model_id=model_id, min_similarity=min_sim, workspace=active_workspace,
                                          use_hyde=use_hyde, use_decompose=use_decompose, use_compress=use_compress)
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
                                   model_id=model_id, min_similarity=min_sim, workspace=active_workspace,
                                   use_hyde=use_hyde, use_decompose=use_decompose, use_compress=use_compress)
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

        # Follow-up suggestions
        if use_followups and st.session_state.get("last_result"):
            last_q = st.session_state.get("last_question", "")
            last_a = st.session_state["last_result"].get("answer", "")
            if last_q and last_a and last_a != config.ui("ask").get("empty_kb_message", ""):
                with st.spinner("Generating follow-ups..."):
                    followups = query.suggest_followups(last_q, last_a, workspace=active_workspace)
                if followups:
                    st.markdown("**Suggested follow-ups:**")
                    fup_cols = st.columns(len(followups))
                    for idx, (col, fup) in enumerate(zip(fup_cols, followups)):
                        with col:
                            if st.button(f"💡 {fup}", key=f"followup_{idx}", use_container_width=True):
                                st.session_state["reask_question"] = fup
                                st.rerun()

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
# DISCOVER TAB
# ---------------------------------------------------------------------------

with tab_discover:
    _discover_cfg = config.ui("discover") or {}
    st.subheader(_discover_cfg.get("heading", "Discover Connections"))

    discover_col1, discover_col2 = st.columns([1, 1])

    with discover_col1:
        st.markdown("#### 🧠 Workspace Digest")
        st.caption(_discover_cfg.get("digest_caption",
                                      "AI-generated summary of your knowledge base's key themes and connections."))
        if st.button("Generate Digest", type="primary"):
            with st.spinner("Analysing your knowledge base..."):
                digest = query.workspace_digest(workspace=active_workspace)
            st.markdown(digest)

        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        st.markdown("#### 🔍 Semantic Source Search")
        st.caption("Find sources by meaning, not just keywords.")
        sem_query = st.text_input("Search",
                                  placeholder=_discover_cfg.get("semantic_search_placeholder", "Search sources by meaning..."),
                                  key="sem_src_search")
        if sem_query.strip():
            with st.spinner("Searching..."):
                sem_results = query.semantic_source_search(sem_query.strip(), workspace=active_workspace)
            if sem_results:
                for r in sem_results:
                    relevance_pct = f"{r['relevance']:.0%}"
                    st.markdown(
                        f"**{r['title']}** — {relevance_pct} relevant ({r['matching_chunks']} matching chunks)"
                    )
                    if r.get("url"):
                        st.caption(r["url"])
            else:
                st.info("No matching sources found.")

    with discover_col2:
        st.markdown("#### 🔗 Related Sources")
        st.caption("Select a source to find related content in your knowledge base.")
        all_sources = db.get_all_sources(workspace=active_workspace)
        if all_sources:
            source_titles = {s["id"]: s["title"] for s in all_sources}
            selected_source_id = st.selectbox(
                "Source",
                options=list(source_titles.keys()),
                format_func=lambda sid: source_titles.get(sid, f"Source #{sid}"),
                key="related_source_picker",
            )
            if st.button("Find Related"):
                with st.spinner("Computing similarity..."):
                    related = query.find_related_sources(
                        selected_source_id, workspace=active_workspace
                    )
                if related:
                    for r in related:
                        sim_pct = f"{r['similarity']:.0%}"
                        st.markdown(
                            f"**{r['title']}** — {sim_pct} similar ({r['matching_chunks']} overlapping chunks)"
                        )
                        if r.get("url"):
                            st.caption(r["url"])
                else:
                    st.info("No related sources found. Try ingesting more content.")
        else:
            st.info("No sources in this workspace yet.")

        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        st.markdown("#### 📈 Knowledge Coverage")
        st.caption("Quick view of what your knowledge base covers.")
        coverage_stats = db.get_stats(workspace=active_workspace)
        if coverage_stats["tag_frequency"]:
            # Show top tags as a visual indicator
            top_tags = list(coverage_stats["tag_frequency"].items())[:10]
            if top_tags:
                mx = max(v for _, v in top_tags)
                for tag, count in top_tags:
                    pct = count / mx
                    st.progress(pct, text=f"{tag} ({count})")
        else:
            st.caption("No tags yet. Tag your sources for better coverage visibility.")


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
            import pandas as pd
            type_df = pd.DataFrame(
                list(stats["type_breakdown"].items()),
                columns=["Type", "Count"],
            )
            st.bar_chart(type_df, x="Type", y="Count", horizontal=True)
        else:
            st.caption("No sources yet.")
    with col_tags:
        st.markdown("#### Top Tags")
        if stats["tag_frequency"]:
            import pandas as pd
            tag_items = list(stats["tag_frequency"].items())[:12]
            tag_df = pd.DataFrame(tag_items, columns=["Tag", "Count"])
            st.bar_chart(tag_df, x="Tag", y="Count")
        else:
            st.caption("No tags yet.")
    with col_models:
        st.markdown("#### Embedding Models")
        if model_breakdown:
            import pandas as pd
            model_df = pd.DataFrame(
                sorted(model_breakdown.items(), key=lambda item: item[1], reverse=True),
                columns=["Model", "Sources"],
            )
            st.bar_chart(model_df, x="Model", y="Sources")
        else:
            st.caption("No embeddings yet.")

    # Ingestion timeline
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    st.markdown("#### Ingestion Timeline")
    timeline = db.get_ingestion_timeline(workspace=active_workspace, days=30)
    if timeline:
        import pandas as pd
        tl_df = pd.DataFrame(timeline)
        tl_df["day"] = pd.to_datetime(tl_df["day"])
        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            st.markdown("**Sources added per day**")
            st.area_chart(tl_df, x="day", y="sources")
        with chart_col2:
            st.markdown("**Chunks created per day**")
            st.area_chart(tl_df, x="day", y="chunks")
    else:
        st.caption("No ingestion data in the last 30 days.")

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
