"""Grouped HTML table — job + steps stay in one tbody; no interactive column sort."""

from __future__ import annotations

import html
from typing import Any

from monitoring_system.dashboard.theme import FAILED, NAVY, PAGE_BG, PROGRESS_BAR_COLOR

TABLE_COLUMNS = (
    "",
    "Seq",
    "Run",
    "Job",
    "Stage",
    "Progress",
    "Started",
    "Ended",
    "Duration",
    "Message",
    "Error",
    "Updated",
)


def _esc(value: Any) -> str:
    if value is None:
        return ""
    return html.escape(str(value))


def _progress_cell(pct: int) -> str:
    pct = max(0, min(100, int(pct)))
    style = f"width:{pct}%;background:{PROGRESS_BAR_COLOR};"
    return (
        f'<div class="prog-cell">'
        f'<div class="prog-track"><div class="prog-fill" style="{style}"></div></div>'
        f'<span class="prog-label">{pct}%</span></div>'
    )


def _cell(col: str, row: dict[str, Any]) -> str:
    if col == "Progress":
        return _progress_cell(int(row.get("Progress") or 0))
    if col == "Error":
        text = _esc(row.get("Error", ""))
        return f'<span class="col-error">{text}</span>' if text else ""
    return _esc(row.get(col, ""))


def _row_html(row: dict[str, Any], *, show_updated: bool) -> str:
    kind = row.get("_row_kind", "stage")
    row_class = "job-summary-row" if kind == "job" else "stage-row"
    cells = []
    for col in TABLE_COLUMNS:
        if col == "Updated" and not show_updated:
            continue
        cells.append(f"<td>{_cell(col, row)}</td>")
    return f'<tr class="{row_class}">{"".join(cells)}</tr>'


def render_grouped_table(blocks: list[list[dict[str, Any]]], *, show_updated: bool) -> str:
    """One <table>; each job block is a <tbody> so rows cannot separate on sort."""
    headers = [c for c in TABLE_COLUMNS if c != "Updated" or show_updated]
    head = "".join(f"<th>{_esc(h) if h else ''}</th>" for h in headers)

    bodies: list[str] = []
    for block_rows in blocks:
        if not block_rows:
            continue
        rows_html = "".join(
            _row_html(r, show_updated=show_updated) for r in block_rows
        )
        bodies.append(f'<tbody class="job-block">{rows_html}</tbody>')

    if not bodies:
        return ""

    # Single-line HTML — indented multiline strings break st.markdown (code-block rule).
    return (
        '<div class="jobs-table-wrap">'
        f'<table class="jobs-consolidated-table"><thead><tr>{head}</tr></thead>'
        f'{"".join(bodies)}</table></div>'
    )


JOB_TABLE_CSS = f"""
.jobs-table-wrap {{
    overflow-x: auto;
    background: #fff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
}}
.jobs-consolidated-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.875rem;
}}
.jobs-consolidated-table thead th {{
    background: {PAGE_BG};
    color: {NAVY};
    font-weight: 600;
    text-align: left;
    padding: 0.55rem 0.65rem;
    border-bottom: 2px solid #e2e8f0;
    white-space: nowrap;
}}
.jobs-consolidated-table tbody.job-block {{
    border-bottom: 2px solid #cbd5e1;
}}
.jobs-consolidated-table tbody.job-block:last-child {{
    border-bottom: none;
}}
.jobs-consolidated-table td {{
    padding: 0.45rem 0.65rem;
    border-bottom: 1px solid #f1f5f9;
    vertical-align: middle;
}}
.jobs-consolidated-table tr.job-summary-row td {{
    background: #f8fafc;
    font-weight: 500;
}}
.jobs-consolidated-table tr.stage-row td {{
    background: #fff;
}}
.jobs-consolidated-table tr.stage-row td:nth-child(1) {{
    padding-left: 1.25rem;
}}
.jobs-consolidated-table .col-error {{
    color: {FAILED};
    font-weight: 500;
}}
.prog-cell {{
    display: flex;
    align-items: center;
    gap: 0.45rem;
    min-width: 7rem;
}}
.prog-track {{
    flex: 1;
    height: 0.45rem;
    background: #e2e8f0;
    border-radius: 4px;
    overflow: hidden;
}}
.prog-fill {{
    height: 100%;
    border-radius: 4px;
}}
.prog-label {{
    font-size: 0.8rem;
    color: #475569;
    min-width: 2.5rem;
}}
"""
