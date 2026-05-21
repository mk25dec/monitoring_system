"""Operations console theme."""

NAVY = "#0c2340"
NAVY_MID = "#1a3a5c"
RUNNING = "#b45309"
RUNNING_BG = "#fef3c7"
RUNNING_BORDER = "#f59e0b"
SUCCESS = "#15803d"
SUCCESS_BG = "#dcfce7"
SUCCESS_BORDER = "#22c55e"
PROGRESS_BAR_COLOR = "#16a34a"
FAILED = "#b91c1c"
FAILED_BG = "#fee2e2"
FAILED_BORDER = "#ef4444"
TOTAL_BG = "#dbeafe"
TOTAL_BORDER = "#3b82f6"
MUTED = "#64748b"
BORDER = "#e2e8f0"
PAGE_BG = "#f1f5f9"

STATUS_LABEL = {
    "running": "In progress",
    "success": "Completed",
    "failed": "Failed",
    "other": "Other",
}

LED_ONLY = {
    "running": "🟠",
    "success": "🟢",
    "failed": "🔴",
    "other": "⚪",
}


def kpi_button_css(active: str | None) -> str:
    """Full-fill KPI buttons via Streamlit widget keys."""
    styles = {
        "kpi_running": (RUNNING_BG, RUNNING_BORDER, RUNNING),
        "kpi_success": (SUCCESS_BG, SUCCESS_BORDER, SUCCESS),
        "kpi_failed": (FAILED_BG, FAILED_BORDER, FAILED),
        "kpi_total": (TOTAL_BG, TOTAL_BORDER, NAVY),
    }
    active_key = {
        "running": "kpi_running",
        "success": "kpi_success",
        "failed": "kpi_failed",
        None: "kpi_total",
    }.get(active)

    css = ""
    for key, (bg, border, text) in styles.items():
        css += f"""
        div[data-testid="stVerticalBlock"]:has(.kpi-mark) ~ div div.st-key-{key} button,
        .st-key-{key} button {{
            width: 100% !important;
            min-height: 5.5rem !important;
            background-color: {bg} !important;
            background-image: none !important;
            border: 2px solid {border} !important;
            border-radius: 10px !important;
            color: {text} !important;
            font-weight: 600 !important;
            font-size: 0.95rem !important;
            line-height: 1.45 !important;
            white-space: pre-line !important;
            text-align: left !important;
            padding: 1rem 1.1rem !important;
            box-shadow: 0 1px 2px rgba(0,0,0,0.06) !important;
        }}
        .st-key-{key} button:hover {{
            background-color: {bg} !important;
            color: {text} !important;
            border-color: {border} !important;
            filter: brightness(0.97) !important;
        }}
        """
        if key == active_key:
            css += f"""
        .st-key-{key} button {{
            border: 3px solid {NAVY} !important;
            box-shadow: 0 4px 12px rgba(12,35,64,0.18) !important;
            font-weight: 700 !important;
        }}
        """
    return css


THEME_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;500;600;700&display=swap');

#MainMenu, footer, header[data-testid="stHeader"] {{
    visibility: hidden;
    height: 0;
}}

.stApp {{ background: {PAGE_BG} !important; }}
html, body, [class*="css"] {{
    font-family: 'Source Sans 3', sans-serif !important;
}}

.block-container {{ padding: 0 !important; max-width: 100% !important; }}
[data-testid="stMainBlockContainer"] {{ padding: 0 !important; }}
[data-testid="stSidebar"] {{
    background: #fff;
    border-right: 1px solid {BORDER};
}}

.app-header {{
    background: linear-gradient(135deg, {NAVY} 0%, {NAVY_MID} 100%);
    padding: 1.1rem 2rem 1.25rem 2rem;
    color: #fff;
}}
.app-header h1 {{
    margin: 0;
    font-size: 1.4rem;
    font-weight: 700;
    color: #fff !important;
}}
.app-header p {{
    margin: 0.2rem 0 0 0;
    font-size: 0.85rem;
    color: rgba(255,255,255,0.9) !important;
}}

.header-btn-row {{
    margin-top: -3.25rem;
    margin-bottom: 0.5rem;
    padding-right: 2rem;
    position: relative;
    z-index: 10;
}}
.header-btn-row .stButton > button {{
    background: rgba(255,255,255,0.18) !important;
    color: #fff !important;
    border: 1px solid rgba(255,255,255,0.5) !important;
    border-radius: 6px !important;
    font-weight: 600 !important;
}}

.kpi-zone {{
    padding: 0.75rem 2rem 0 2rem;
}}

.filter-hint {{
    font-size: 0.8rem;
    color: {MUTED};
    padding: 0.25rem 2rem 0.5rem 2rem;
    margin: 0;
}}

.table-zone {{ padding: 0.75rem 2rem 2rem 2rem; }}
.table-head {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.65rem;
}}
.table-head h2 {{
    margin: 0;
    font-size: 1.05rem;
    font-weight: 700;
    color: {NAVY};
}}
.table-head span {{ font-size: 0.8rem; color: {MUTED}; }}

div[data-testid="stVerticalBlockBorderWrapper"] {{
    border-radius: 10px !important;
    border-color: {BORDER} !important;
    background: #fff !important;
}}
div[data-testid="stDataFrame"] th {{
    background: {PAGE_BG} !important;
    color: {NAVY} !important;
    font-weight: 600 !important;
}}

/* Progress bars in stage table — green fill */
div[data-testid="stDataFrame"] [role="progressbar"] > div {{
    background-color: {PROGRESS_BAR_COLOR} !important;
}}
div[data-testid="stDataFrame"] [data-testid="stProgressBar"] > div > div {{
    background-color: {PROGRESS_BAR_COLOR} !important;
}}

div[data-testid="stDataFrame"] td:nth-child(9) {{
    color: {FAILED};
    font-weight: 500;
}}
</style>
"""
