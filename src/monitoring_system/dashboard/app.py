"""Operations console — one table; job rows from DB (sequence=0), stages when expanded."""

from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st

from monitoring_system.config import load_settings
from monitoring_system.dashboard.table_render import JOB_TABLE_CSS, render_grouped_table
from monitoring_system.dashboard.theme import LED_ONLY, THEME_CSS, kpi_button_css
from monitoring_system.db import clear_database, delete_run, init_db
from monitoring_system.db.job_summary import JOB_SEQUENCE
from monitoring_system.timefmt import format_duration, format_ts

def _render_html(fragment: str) -> None:
    """Render raw HTML (avoids markdown treating indented tags as code blocks)."""
    if hasattr(st, "html"):
        st.html(fragment)
    else:
        st.markdown(fragment, unsafe_allow_html=True)


FILTER_LABELS = {
    None: "Showing all jobs",
    "running": "Showing in progress only",
    "success": "Showing completed only",
    "failed": "Showing failed only",
}


def _blank(value: str) -> str:
    return "" if value == "—" else value


def _load_rows(db_path) -> pd.DataFrame:
    with sqlite3.connect(db_path) as conn:
        return pd.read_sql_query("SELECT * FROM ui_dashboard", conn)


def _parse_payload(raw: Any) -> dict[str, Any]:
    if not raw or (isinstance(raw, float) and pd.isna(raw)):
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


def _payload_text(payload: dict[str, Any], key: str) -> str:
    val = payload.get(key)
    if val is None:
        return ""
    return str(val).strip()


def _is_job_row(sequence: Any, payload: dict[str, Any]) -> bool:
    if payload.get("row_kind") == "job":
        return True
    if pd.notna(sequence) and int(sequence) == JOB_SEQUENCE:
        return True
    return False


def _enrich(df: pd.DataFrame) -> pd.DataFrame:
    """Map DB + payload to display columns only — no aggregation or progress math."""
    if df.empty:
        return df
    payloads = df["payload"].map(_parse_payload)
    out = df.copy()
    out["row_kind"] = [
        "job" if _is_job_row(seq, p) else "stage"
        for seq, p in zip(out["sequence"], payloads, strict=True)
    ]
    out["progress_pct"] = payloads.map(lambda p: p.get("progress_pct"))
    out["status_bucket"] = payloads.map(lambda p: str(p.get("status_bucket") or ""))
    out["led"] = out["status_bucket"].map(lambda b: LED_ONLY.get(b, "⚪") if b else "⚪")
    out["started_display"] = out["started_at"].map(format_ts).map(_blank)
    out["ended_display"] = [
        _blank(format_ts(e)) if not str(p.get("display_ended") or "").strip() else str(p["display_ended"])
        for e, p in zip(out["ended_at"], payloads, strict=True)
    ]
    out["updated_display"] = out["ts"].map(format_ts).map(_blank)
    out["duration_display"] = out["duration_sec"].map(format_duration).map(_blank)
    out["message_display"] = payloads.map(lambda p: _payload_text(p, "message"))
    out["error_display"] = payloads.map(lambda p: _payload_text(p, "error"))
    out["seq_display"] = out.apply(
        lambda r: "" if r["row_kind"] == "job" else (int(r["sequence"]) if pd.notna(r["sequence"]) else ""),
        axis=1,
    )
    return out


def _toggle_filter(key: str | None) -> None:
    current = st.session_state.get("kpi_filter")
    st.session_state.kpi_filter = None if current == key else key


def _apply_sidebar_filters(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        st.sidebar.markdown("### Filters")
        st.sidebar.info("No data yet.")
        return df

    st.sidebar.markdown("### Filters")
    filtered = df.copy()

    for field, label in (
        ("run_id", "Run ID"),
        ("job", "Job"),
        ("stage", "Stage"),
    ):
        options = sorted(filtered[field].astype(str).unique().tolist())
        if field == "stage":
            options = [o for o in options if not o.startswith("(")]
        chosen = st.sidebar.multiselect(label, options=options, default=[], key=f"sf_{field}")
        if chosen:
            filtered = filtered[filtered[field].astype(str).isin(chosen)]

    return filtered


def _apply_kpi_filter(df: pd.DataFrame) -> pd.DataFrame:
    f = st.session_state.get("kpi_filter")
    if not f or df.empty:
        return df
    jobs = df.loc[df["row_kind"] == "job", ["run_id", "job"]]
    matching = df[df["status_bucket"] == f]
    if jobs.empty:
        return matching
    keys = set(zip(matching["run_id"].astype(str), matching["job"].astype(str), strict=True))
    if not keys:
        return df.iloc[0:0]
    mask = df.apply(
        lambda r: (str(r["run_id"]), str(r["job"])) in keys,
        axis=1,
    )
    return df[mask]


def _kpi_row(vals: dict[str, int]) -> None:
    st.markdown(
        f"<style>{kpi_button_css(st.session_state.get('kpi_filter'))}</style>",
        unsafe_allow_html=True,
    )
    st.markdown('<div class="kpi-zone"><span class="kpi-mark"></span>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4, gap="medium")
    cards = [
        (c1, "running", "In progress", vals["running"], "kpi_running"),
        (c2, "success", "Completed", vals["success"], "kpi_success"),
        (c3, "failed", "Failed", vals["failed"], "kpi_failed"),
        (c4, None, "All jobs", vals["total"], "kpi_total"),
    ]
    for col, fkey, label, count, btn_key in cards:
        with col:
            st.button(
                f"{label}\n{count}",
                key=btn_key,
                type="secondary",
                use_container_width=True,
                on_click=_toggle_filter,
                args=(fkey,),
            )
    st.markdown("</div>", unsafe_allow_html=True)

    hint = FILTER_LABELS.get(st.session_state.get("kpi_filter"))
    if hint:
        st.markdown(
            f'<p class="filter-hint">{hint} — click the same card again to clear</p>',
            unsafe_allow_html=True,
        )


def _display_row(r: pd.Series) -> dict[str, Any]:
    is_job = r["row_kind"] == "job"
    prog = r["progress_pct"]
    try:
        progress = int(round(float(prog))) if prog is not None and pd.notna(prog) else 0
    except (TypeError, ValueError):
        progress = 0
    return {
        "": str(r["led"]),
        "Seq": r["seq_display"] if r["seq_display"] != "" else "",
        "Run": str(r["run_id"]) if is_job else "",
        "Job": str(r["job"]) if is_job else "",
        "Stage": str(r["stage"]),
        "Progress": progress,
        "Started": str(r["started_display"]),
        "Ended": str(r["ended_display"]),
        "Duration": str(r["duration_display"]),
        "Message": str(r["message_display"]),
        "Error": str(r["error_display"]),
        "Updated": "" if is_job else str(r["updated_display"]),
        "_row_kind": r["row_kind"],
        "_run_id": str(r["run_id"]),
        "_job": str(r["job"]),
        "_sequence": int(r["sequence"]) if pd.notna(r["sequence"]) else JOB_SEQUENCE,
    }


JOB_SORT_OPTIONS = {
    "started_desc": "Started (newest first)",
    "started_asc": "Started (oldest first)",
    "run_id": "Run ID",
    "job": "Job name",
    "progress_desc": "Progress (high first)",
    "duration_desc": "Duration (longest first)",
}


def _progress_num(row: pd.Series) -> float:
    prog = row.get("progress_pct")
    try:
        return float(prog) if prog is not None and pd.notna(prog) else 0.0
    except (TypeError, ValueError):
        return 0.0


def _build_job_blocks(df: pd.DataFrame, show_stages: bool) -> list[dict[str, Any]]:
    """Each block is one job summary row plus optional stage rows (fixed order)."""
    if df.empty:
        return []

    jobs = df[df["row_kind"] == "job"]
    if jobs.empty:
        return []

    blocks: list[dict[str, Any]] = []
    for (run_id, job), _ in jobs.groupby(["run_id", "job"], sort=False):
        job_rows = df[(df["run_id"] == run_id) & (df["job"] == job)]
        job_row = job_rows[job_rows["row_kind"] == "job"]
        if job_row.empty:
            continue
        summary = job_row.iloc[0]
        block_rows = [_display_row(summary)]
        if show_stages:
            stages = job_rows[job_rows["row_kind"] == "stage"].sort_values(
                ["sequence", "stage"],
                na_position="last",
            )
            for _, stage in stages.iterrows():
                block_rows.append(_display_row(stage))

        blocks.append(
            {
                "run_id": str(run_id),
                "job": str(job),
                "started_at": summary.get("started_at"),
                "duration_sec": summary.get("duration_sec"),
                "progress": _progress_num(summary),
                "rows": block_rows,
            }
        )
    return blocks


def _sort_job_blocks(blocks: list[dict[str, Any]], sort_key: str) -> list[dict[str, Any]]:
    if not blocks:
        return blocks

    def started_key(block: dict[str, Any]) -> str:
        raw = block.get("started_at")
        return "" if raw is None or (isinstance(raw, float) and pd.isna(raw)) else str(raw)

    def duration_key(block: dict[str, Any]) -> float:
        raw = block.get("duration_sec")
        try:
            return float(raw) if raw is not None and pd.notna(raw) else -1.0
        except (TypeError, ValueError):
            return -1.0

    if sort_key == "started_asc":
        return sorted(blocks, key=started_key)
    if sort_key == "started_desc":
        return sorted(blocks, key=started_key, reverse=True)
    if sort_key == "run_id":
        return sorted(blocks, key=lambda b: (b["run_id"], b["job"]))
    if sort_key == "job":
        return sorted(blocks, key=lambda b: (b["job"], b["run_id"]))
    if sort_key == "progress_desc":
        return sorted(blocks, key=lambda b: b["progress"], reverse=True)
    if sort_key == "duration_desc":
        return sorted(blocks, key=duration_key, reverse=True)
    return blocks


def _data_sidebar(db_path, df: pd.DataFrame) -> None:
    st.sidebar.markdown("### Data")
    run_ids = (
        sorted(df.loc[df["row_kind"] == "job", "run_id"].astype(str).unique().tolist())
        if not df.empty
        else []
    )

    if run_ids:
        pick = st.sidebar.selectbox(
            "Run to delete",
            options=run_ids,
            key="delete_run_pick",
        )
        if st.sidebar.button("Delete this run", key="delete_run_btn", type="secondary"):
            st.session_state.confirm_delete_run = pick
    else:
        st.sidebar.caption("No runs to delete.")

    pending_run = st.session_state.get("confirm_delete_run")
    if pending_run:
        st.sidebar.warning(f"Delete all data for **{pending_run}**?")
        y, n = st.sidebar.columns(2)
        if y.button("Yes, delete run", key="confirm_delete_run_yes", type="primary"):
            counts = delete_run(db_path, pending_run)
            st.session_state.pop("confirm_delete_run", None)
            st.session_state.refreshed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.sidebar.success(
                f"Removed run `{pending_run}` "
                f"({counts['current_state']} snapshot rows, {counts['events']} events)."
            )
            st.rerun()
        if n.button("Cancel", key="confirm_delete_run_no"):
            st.session_state.pop("confirm_delete_run", None)
            st.rerun()

    st.sidebar.divider()
    if st.sidebar.button("Clear entire database", key="clear_all_btn", type="secondary"):
        st.session_state.confirm_clear_all = True

    if st.session_state.get("confirm_clear_all"):
        st.sidebar.error("Delete **all** runs and history?")
        y, n = st.sidebar.columns(2)
        if y.button("Yes, clear all", key="confirm_clear_all_yes", type="primary"):
            counts = clear_database(db_path)
            st.session_state.pop("confirm_clear_all", None)
            st.session_state.kpi_filter = None
            st.session_state.refreshed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.sidebar.success(
                f"Cleared database ({counts['current_state']} snapshots, {counts['events']} events)."
            )
            st.rerun()
        if n.button("Cancel", key="confirm_clear_all_no"):
            st.session_state.pop("confirm_clear_all", None)
            st.rerun()


def _stage_table(df: pd.DataFrame, refreshed: str) -> None:
    st.markdown('<div class="table-zone">', unsafe_allow_html=True)
    job_rows = df[df["row_kind"] == "job"] if not df.empty else df
    job_count = len(job_rows.groupby(["run_id", "job"], sort=False)) if not job_rows.empty else 0
    stage_count = int((df["row_kind"] == "stage").sum()) if not df.empty else 0

    st.markdown(
        f"""
        <div class="table-head">
          <h2>Jobs &amp; stages</h2>
          <span>{job_count} job(s) · {stage_count} stage(s) · Updated {refreshed}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if "show_stage_details" not in st.session_state:
        st.session_state.show_stage_details = False

    c1, c2, c3 = st.columns([2, 2, 3])
    with c1:
        label = "Hide step details" if st.session_state.show_stage_details else "Show step details"
        if st.button(label, key="toggle_stage_details", type="primary"):
            st.session_state.show_stage_details = not st.session_state.show_stage_details
            st.rerun()
    with c2:
        if st.button("Expand all", key="jobs_expand_all"):
            st.session_state.show_stage_details = True
            st.rerun()
    with c3:
        if st.button("Collapse all", key="jobs_collapse_all"):
            st.session_state.show_stage_details = False
            st.rerun()

    sort_key = st.session_state.get("job_sort", "started_desc")
    blocks = _sort_job_blocks(
        _build_job_blocks(df, st.session_state.show_stage_details),
        sort_key,
    )
    block_rows = [b["rows"] for b in blocks]

    if not block_rows:
        with st.container(border=True):
            st.markdown(
                "<p style='text-align:center;color:#64748b;padding:2rem 0;'>"
                "No jobs for this filter. Click <b>All jobs</b> or another card."
                "</p>",
                unsafe_allow_html=True,
            )
    else:
        html_table = render_grouped_table(
            block_rows,
            show_updated=st.session_state.show_stage_details,
        )
        st.markdown(f"<style>{JOB_TABLE_CSS}</style>", unsafe_allow_html=True)
        _render_html(html_table)
        mode = "job summary + steps" if st.session_state.show_stage_details else "job summary only"
        st.caption(
            f"{job_count} job(s) · {mode} · grouped by job (use sidebar to sort job blocks) · "
            "values from DB / emitter payload"
        )

    st.markdown("</div>", unsafe_allow_html=True)


def main() -> None:
    settings = load_settings()
    db_path = settings.sqlite.resolved_path()
    init_db(db_path)

    st.set_page_config(page_title=settings.dashboard.page_title, layout="wide")

    if "kpi_filter" not in st.session_state:
        st.session_state.kpi_filter = None
    if "show_stage_details" not in st.session_state:
        st.session_state.show_stage_details = False
    if "refreshed_at" not in st.session_state:
        st.session_state.refreshed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    st.markdown(THEME_CSS, unsafe_allow_html=True)

    st.sidebar.markdown("### Options")
    if "job_sort" not in st.session_state:
        st.session_state.job_sort = "started_desc"
    st.sidebar.selectbox(
        "Sort job blocks",
        options=list(JOB_SORT_OPTIONS.keys()),
        format_func=lambda k: JOB_SORT_OPTIONS[k],
        key="job_sort",
    )
    st.sidebar.caption("Sorts whole jobs (summary + steps stay together).")
    auto = st.sidebar.toggle("Auto-refresh", value=False)
    if auto:
        st.sidebar.caption(f"Every {int(settings.dashboard.poll_seconds)}s")

    raw = _enrich(_load_rows(db_path))
    _data_sidebar(db_path, raw)
    base = _apply_sidebar_filters(raw)

    st.markdown(
        f"""
        <div class="app-header">
          <h1>{settings.dashboard.page_title}</h1>
          <p>Click a colored card to filter the table below</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<div class="header-btn-row">', unsafe_allow_html=True)
    _, btn_col = st.columns([5, 1])
    with btn_col:
        if st.button("↻  Refresh", key="refresh_main", use_container_width=True):
            st.session_state.refreshed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    job_only = base[base["row_kind"] == "job"] if not base.empty else base
    if job_only.empty:
        vals = dict(running=0, success=0, failed=0, total=0)
    else:
        b = job_only["status_bucket"]
        vals = {
            "running": int((b == "running").sum()),
            "success": int((b == "success").sum()),
            "failed": int((b == "failed").sum()),
            "total": len(job_only),
        }

    _kpi_row(vals)
    shown = _apply_kpi_filter(base)
    _stage_table(shown, st.session_state.refreshed_at)

    if auto:
        time.sleep(settings.dashboard.poll_seconds)
        st.session_state.refreshed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.rerun()


if __name__ == "__main__":
    main()
