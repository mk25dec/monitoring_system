"""Read-only dashboard — stable ``ui_dashboard`` view + status colors."""

from __future__ import annotations

import json
import sqlite3
import time

import pandas as pd
import streamlit as st

from monitoring_system.config import load_settings
from monitoring_system.db import init_db

STATUS_COLORS = {
    "running": "#fff3cd",
    "done": "#d1e7dd",
    "completed": "#d1e7dd",
    "success": "#d1e7dd",
    "failed": "#f8d7da",
    "error": "#f8d7da",
    "pending": "#e2e3e5",
    "skipped": "#cff4fc",
}


def _load_rows(db_path) -> pd.DataFrame:
    with sqlite3.connect(db_path) as conn:
        return pd.read_sql_query(
            "SELECT run_id, module, stage, status, ts, payload FROM ui_dashboard",
            conn,
        )


def _style_df(df: pd.DataFrame):
    if df.empty:
        return df

    def _row_color(row: pd.Series) -> list[str]:
        bg = STATUS_COLORS.get(str(row["status"]).lower(), "#ffffff")
        return [f"background-color: {bg}"] * len(row)

    return df.style.apply(_row_color, axis=1)


def main() -> None:
    settings = load_settings()
    db_path = settings.sqlite.resolved_path()
    init_db(db_path)

    st.set_page_config(page_title=settings.dashboard.page_title, layout="wide")
    st.title(settings.dashboard.page_title)

    col1, col2, col3 = st.columns(3)
    with col1:
        run_filter = st.text_input("Filter run_id (optional)")
    with col2:
        module_filter = st.text_input("Filter module (optional)")
    with col3:
        auto = st.checkbox("Auto-refresh", value=True)

    df = _load_rows(db_path)
    if run_filter:
        df = df[df["run_id"].astype(str).str.contains(run_filter, case=False, na=False)]
    if module_filter:
        df = df[df["module"].astype(str).str.contains(module_filter, case=False, na=False)]

    display = df.drop(columns=["payload"], errors="ignore")
    st.dataframe(_style_df(display), use_container_width=True, hide_index=True)

    with st.expander("Payload (latest per stage)"):
        if not df.empty:
            for _, row in df.iterrows():
                try:
                    payload = json.loads(row["payload"]) if row["payload"] else {}
                except json.JSONDecodeError:
                    payload = row["payload"]
                st.markdown(f"**{row['module']} / {row['stage']}**")
                st.json(payload)

    st.caption(
        "Colors: running=yellow, done=green, failed=red. "
        f"DB: `{db_path}`"
    )

    if auto:
        time.sleep(settings.dashboard.poll_seconds)
        st.rerun()


if __name__ == "__main__":
    main()
