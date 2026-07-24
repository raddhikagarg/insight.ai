

"""
InsightAI visual theme — "Modern Institutional" (Charcoal / Off-White / Burgundy).

Call `apply_theme()` once near the top of every page, right after
`st.set_page_config(...)`, so every screen in the app shares the same
typography, palette, spacing, and card styling instead of each page
drifting on its own.

Font note
---------
`CS Rhona Demo` is a paid display font (Craft Supply Co.) and isn't on a
public CDN we can safely hare-load at runtime, and its free "Demo" cut is
personal-use-only / missing glyphs -- not something to ship in a real
product. Drop a licensed copy of the font file(s) here:

    streamlit/static/fonts/CSRhonaDemo.woff2
    streamlit/static/fonts/CSRhonaDemo.otf

and it will be picked up automatically (Streamlit serves anything under
`streamlit/static/` at the `app/static/...` URL once
`enableStaticServing = true` is set in `.streamlit/config.toml`, which is
already done). Until the file is added, the browser silently falls back
to the next font in the stack below (a serif that reads as close in
spirit -- editorial, high-contrast, a little formal).
"""
import streamlit as st

_FONT_STACK = (
    "'CS Rhona Demo', 'Playfair Display', Georgia, 'Times New Roman', serif"
)

_CSS = f"""
<style>
/* ---- self-hosted display font (falls back gracefully if not present) ---- */
@font-face {{
    font-family: 'CS Rhona Demo';
    src: url('app/static/fonts/CSRhonaDemo.woff2') format('woff2'),
         url('app/static/fonts/CSRhonaDemo.otf') format('opentype');
    font-weight: 400;
    font-style: normal;
    font-display: swap;
}}

:root {{
    --insight-bg: #FFFFFF;
    --insight-text: #334155;
    --insight-accent: #881337;
    --insight-accent-hover: #6e1029;
    --insight-border: #E4E1DC;
    --insight-surface: #FBFAF8;
}}

/* ---------------- base page ---------------- */
html, body, [class^="st-"], [class*=" st-"], 
.stApp {{
    font-family: {_FONT_STACK} !important;
    color: var(--insight-text) !important;
}}


[data-testid="stHeader"] {{
    background-color: var(--insight-bg) !important;
}}

[data-testid="stSidebar"] {{
    background-color: var(--insight-surface) !important;
    border-right: 1px solid var(--insight-border);
}}

/* ---------------- typography ---------------- */
h1, h2, h3, h4, h5, h6 {{
    font-family: {_FONT_STACK} !important;
    color: var(--insight-text) !important;
    text-align: center;
    font-weight: 600;
    letter-spacing: 0.01em;
}}

h1 {{
    border-bottom: 1px solid var(--insight-border);
    padding-bottom: 0.6rem;
    margin-bottom: 1.2rem;
}}

.stMarkdown p, .stCaption, [data-testid="stCaptionContainer"],
label, .stMarkdown li {{
    text-align: center;
}}

.stMarkdown {{
    text-align: center;
}}

/* keep tabular / code content left-aligned for readability */
[data-testid="stDataFrame"], [data-testid="stTable"],
.stCodeBlock, pre, code {{
    text-align: left !important;
}}

/* ---------------- buttons ---------------- */
.stButton > button {{
    font-family: {_FONT_STACK} !important;
    border-radius: 6px;
    border: 1px solid var(--insight-border);
    color: var(--insight-text);
}}

.stButton > button[kind="primary"] {{
    background-color: var(--insight-accent);
    border-color: var(--insight-accent);
    color: #FFFFFF;
}}

.stButton > button[kind="primary"]:hover {{
    background-color: var(--insight-accent-hover);
    border-color: var(--insight-accent-hover);
}}

.stButton > button:hover {{
    border-color: var(--insight-accent);
    color: var(--insight-accent);
}}

/* links */
a, .stPageLink a {{
    color: var(--insight-accent) !important;
}}

/* ---------------- inputs ---------------- */
.stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] {{
    border-radius: 6px !important;
    border-color: var(--insight-border) !important;
}}

/* ---------------- metrics ---------------- */
[data-testid="stMetric"] {{
    text-align: center;
    background-color: var(--insight-surface);
    border: 1px solid var(--insight-border);
    border-radius: 10px;
    padding: 1rem 0.5rem;
}}
[data-testid="stMetricLabel"] {{
    justify-content: center;
    color: var(--insight-text) !important;
}}
[data-testid="stMetricValue"] {{
    color: var(--insight-accent) !important;
    justify-content: center;
}}

/* ---------------- bordered "card" containers ---------------- */
/* produced by st.container(border=True) -- used to box the login form, */
/* dashboard sections, etc. instead of raw text floating on the page.   */
[data-testid="stVerticalBlockBorderWrapper"] {{
    border: 1px solid var(--insight-border) !important;
    border-radius: 12px !important;
    background-color: var(--insight-surface);
    box-shadow: 0 1px 3px rgba(51, 65, 85, 0.06);
    padding: 0.25rem;
}}

/* alerts (success / info / warning / error) -- flatten to the palette */
[data-testid="stAlert"] {{
    border-radius: 8px;
    text-align: center;
}}

hr {{
    border-color: var(--insight-border) !important;
}}
</style>
"""


def apply_theme() -> None:
    """Inject the InsightAI 'Modern Institutional' theme into the page."""
    st.markdown(_CSS, unsafe_allow_html=True)


def centered_container(max_width: int = 480):
    """
    Returns a bordered, centered container -- used to box the login card
    and other single-column sections so they don't sit flush against the
    edges of the page.
    """
    left, mid, right = st.columns([1, 2, 1])
    with mid:
        box = st.container(border=True)
    return box
