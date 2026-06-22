import streamlit as st
import requests
import folium
import os
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
from datetime import datetime

try:
    from chat_utils import get_chat_response, format_prediction_for_chat
    CHAT_AVAILABLE = True
except ImportError:
    CHAT_AVAILABLE = False

API = os.getenv("API_URL", "http://127.0.0.1:8000")

st.set_page_config(
    page_title="Gridlock — Traffic Congestion Command Center",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ══════════════════════════════════════════════
# DESIGN SYSTEM — CSS
# ══════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600&display=swap');

:root{
  --bg:#0B1220;
  --card:#111827;
  --card-alt:#0F172A;
  --border:#1F2937;
  --success:#22C55E;
  --warning:#F59E0B;
  --danger:#EF4444;
  --info:#3B82F6;
  --text:#F1F5F9;
  --text-dim:#B6C2D1;
  --text-faint:#8A97AA;
  --radius:12px;
  --shadow: 0 4px 16px rgba(0,0,0,0.35), 0 1px 3px rgba(0,0,0,0.4);
  --shadow-sm: 0 2px 8px rgba(0,0,0,0.25);
}

html, body, [class*="css"]{
  font-family:'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  font-size:17px;
}
/* Floor for the smallest label/caption classes used throughout — these
   were as small as 0.68rem (≈9px), illegible at normal zoom. Using fixed
   rem (not em) avoids any nested-compounding risk. */
.gx-kpi-label, .gx-tile-label, .gx-header-stat-label, .gx-section-title,
.gx-feed-head, .gx-badge, .gx-pill, .gx-chip, .gx-best-tag, .gx-wf,
[data-testid="stCaptionContainer"], .stCaption,
[data-testid="stWidgetLabel"] p, section[data-testid="stSidebar"] label{
  font-size:0.95rem !important;
}
.gx-kpi-sub, .gx-subtitle, .gx-step, .gx-mem-title, .gx-zone-name{
  font-size:1rem !important;
}

.stApp{
  background:
    radial-gradient(circle at 15% 0%, rgba(59,130,246,0.06), transparent 40%),
    radial-gradient(circle at 85% 0%, rgba(34,197,94,0.05), transparent 40%),
    var(--bg);
}

#MainMenu, footer, header[data-testid="stHeader"]{visibility:hidden; height:0;}
.block-container{padding-top:1rem; padding-bottom:2rem;}
/* Full-width main content only above the mobile breakpoint. Forcing this
   unconditionally was fighting Streamlit's own responsive behavior, which
   normally turns the sidebar into a sliding overlay on narrow screens —
   the forced 100% width was causing the main content and the sidebar
   overlay to occupy the same space simultaneously instead of one
   yielding to the other. */
@media (min-width: 641px){
  .block-container{ max-width:100%; width:100%; }
  [data-testid="stMain"], [data-testid="stMainBlockContainer"], .main .block-container{
    max-width:100% !important;
    width:100% !important;
  }
}

/* ---------- Sidebar ---------- */
section[data-testid="stSidebar"]{
  background: linear-gradient(180deg, #0D1424 0%, #0A0F1C 100%);
  border-right:1px solid var(--border);
}
section[data-testid="stSidebar"] .block-container{padding-top:1.25rem;}
section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3{
  color:var(--text); font-weight:700; letter-spacing:.02em;
}
section[data-testid="stSidebar"] .stExpander{
  background:var(--card);
  border:1px solid var(--border);
  border-radius:var(--radius);
  margin-bottom:10px;
  overflow:hidden;
}
section[data-testid="stSidebar"] .stExpander summary{
  font-weight:600; font-size:0.85rem; letter-spacing:.03em; text-transform:uppercase;
  color:var(--text-dim);
}
section[data-testid="stSidebar"] label{color:var(--text-dim) !important; font-size:0.8rem;}

/* ---------- Generic text ---------- */
h1,h2,h3,h4,h5{color:var(--text); font-weight:700;}
p, span, label, .stMarkdown{color:var(--text);}
.stCaption, [data-testid="stCaptionContainer"]{color:var(--text-faint) !important;}

/* ---------- Card primitive ---------- */
.gx-card{
  background:var(--card);
  border:1px solid var(--border);
  border-radius:var(--radius);
  padding:20px 22px;
  box-shadow:var(--shadow-sm);
  margin-bottom:14px;
}
.gx-card-tight{padding:14px 16px;}
.gx-section-title{
  font-size:0.78rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase;
  color:var(--text-dim); margin-bottom:14px; display:flex; align-items:center; gap:8px;
}
.gx-section-title .dot{
  width:6px;height:6px;border-radius:50%;background:var(--info);
  box-shadow:0 0 8px var(--info);
}

/* ---------- Header ---------- */
.gx-header{
  display:flex; justify-content:space-between; align-items:center;
  background:linear-gradient(135deg, rgba(17,24,39,0.9), rgba(11,18,32,0.9));
  border:1px solid var(--border);
  border-radius:var(--radius);
  padding:18px 26px;
  margin-bottom:18px;
  box-shadow:var(--shadow);
}
.gx-header-left{display:flex; align-items:center; gap:14px;}
.gx-logo-badge{
  width:46px;height:46px;border-radius:10px;
  background:linear-gradient(135deg,#1D4ED8,#3B82F6);
  display:flex;align-items:center;justify-content:center;
  font-size:22px; box-shadow:0 4px 14px rgba(59,130,246,0.35);
}
.gx-title{font-size:1.35rem; font-weight:800; color:#fff; letter-spacing:.01em; line-height:1.1;}
.gx-subtitle{font-size:0.78rem; color:var(--text-dim); font-weight:500; margin-top:2px;}
.gx-header-right{display:flex; gap:22px; align-items:center;}
.gx-header-stat{text-align:right;}
.gx-header-stat-label{font-size:0.68rem; color:var(--text-faint); text-transform:uppercase; letter-spacing:.06em;}
.gx-header-stat-value{font-size:0.9rem; font-weight:600; color:var(--text); font-family:'JetBrains Mono',monospace;}
.gx-pill{
  display:inline-flex; align-items:center; gap:6px;
  padding:5px 12px; border-radius:999px; font-size:0.75rem; font-weight:600;
  border:1px solid var(--border);
}
.gx-pill .pulse{width:7px;height:7px;border-radius:50%;}
.gx-pill-ok{background:rgba(34,197,94,0.1); color:var(--success); border-color:rgba(34,197,94,0.3);}
.gx-pill-ok .pulse{background:var(--success); box-shadow:0 0 6px var(--success); animation:gxpulse 2s infinite;}
.gx-pill-bad{background:rgba(239,68,68,0.1); color:var(--danger); border-color:rgba(239,68,68,0.3);}
.gx-pill-bad .pulse{background:var(--danger); box-shadow:0 0 6px var(--danger);}
@keyframes gxpulse{0%,100%{opacity:1;}50%{opacity:.4;}}

/* ---------- KPI cards ---------- */
.gx-kpi{
  background:var(--card);
  border:1px solid var(--border);
  border-radius:var(--radius);
  padding:16px 18px;
  box-shadow:var(--shadow-sm);
  position:relative;
  overflow:hidden;
}
.gx-kpi-label{
  font-size:0.7rem; color:var(--text-faint); text-transform:uppercase;
  letter-spacing:.06em; font-weight:700; margin-bottom:8px;
}
.gx-kpi-value{font-size:1.7rem; font-weight:800; color:var(--text); line-height:1; font-family:'JetBrains Mono',monospace;}
.gx-kpi-sub{font-size:0.74rem; color:var(--text-dim); margin-top:6px;}
.gx-kpi-accent{position:absolute; left:0; top:0; bottom:0; width:4px;}
.gx-kpi-dominant{padding:22px 22px; border-width:1.5px;}
.gx-kpi-dominant .gx-kpi-value{font-size:2.3rem;}

/* ---------- Status badges ---------- */
.gx-badge{
  display:inline-flex; align-items:center; gap:8px;
  padding:8px 16px; border-radius:999px; font-weight:700; font-size:0.95rem;
  border:1px solid;
}
.gx-badge-severe{background:rgba(239,68,68,0.12); color:var(--danger); border-color:rgba(239,68,68,0.4);}
.gx-badge-moderate{background:rgba(245,158,11,0.12); color:var(--warning); border-color:rgba(245,158,11,0.4);}
.gx-badge-quick{background:rgba(34,197,94,0.12); color:var(--success); border-color:rgba(34,197,94,0.4);}
.gx-badge-neutral{background:rgba(148,163,184,0.1); color:var(--text-dim); border-color:var(--border);}

/* ---------- Chips ---------- */
.gx-chip{
  display:inline-flex; align-items:center; gap:6px;
  background:rgba(34,197,94,0.08); color:var(--success);
  border:1px solid rgba(34,197,94,0.25);
  padding:6px 12px; border-radius:8px; font-size:0.82rem; font-weight:600;
  margin:0 8px 8px 0;
}

/* ---------- Metric tiles (resources) ---------- */
.gx-tile{
  background:var(--card-alt);
  border:1px solid var(--border);
  border-radius:10px;
  padding:14px;
  text-align:center;
}
.gx-tile-icon{font-size:1.3rem; margin-bottom:4px;}
.gx-tile-value{font-size:1.4rem; font-weight:800; color:var(--text); font-family:'JetBrains Mono',monospace;}
.gx-tile-label{font-size:0.7rem; color:var(--text-faint); text-transform:uppercase; letter-spacing:.04em; margin-top:2px;}

/* ---------- Action steps ---------- */
.gx-step{
  display:flex; gap:10px; align-items:flex-start;
  padding:8px 0; border-bottom:1px solid var(--border);
  font-size:0.86rem; color:var(--text-dim);
}
.gx-step:last-child{border-bottom:none;}
.gx-step-num{
  flex-shrink:0; width:20px;height:20px;border-radius:6px;
  background:rgba(59,130,246,0.15); color:var(--info);
  display:flex;align-items:center;justify-content:center;
  font-size:0.7rem; font-weight:700;
}

/* ---------- Memory engine cards ---------- */
.gx-mem-card{
  background:var(--card-alt);
  border:1px solid var(--border);
  border-radius:10px;
  padding:16px 18px;
  margin-bottom:12px;
}
.gx-mem-card-best{border-color:rgba(34,197,94,0.45); box-shadow:0 0 0 1px rgba(34,197,94,0.15);}
.gx-mem-header{display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;}
.gx-mem-title{font-weight:700; font-size:0.92rem; color:var(--text);}
.gx-sim-track{
  width:100%; height:6px; border-radius:999px; background:#1E293B; overflow:hidden; margin:6px 0 12px 0;
}
.gx-sim-fill{height:100%; border-radius:999px; background:linear-gradient(90deg,#3B82F6,#22C55E);}

/* ---------- Digital Twin scenario cards ---------- */
.gx-scenario{
  background:var(--card-alt);
  border:1px solid var(--border);
  border-radius:10px;
  padding:16px;
  height:100%;
}
.gx-scenario-best{border-color:var(--success); box-shadow:0 0 0 1px rgba(34,197,94,0.2), 0 0 18px rgba(34,197,94,0.08);}
.gx-best-tag{
  font-size:0.68rem; font-weight:800; color:var(--success); letter-spacing:.05em;
  margin-bottom:6px; display:block;
}

/* ---------- Operations feed table ---------- */
.gx-feed-row{
  display:grid; grid-template-columns: 0.6fr 2.4fr 1.4fr 1fr 1.1fr;
  gap:10px; align-items:center;
  padding:10px 14px; border-bottom:1px solid var(--border);
  font-size:0.84rem;
}
.gx-feed-row:last-child{border-bottom:none;}
.gx-feed-head{
  font-size:0.68rem; color:var(--text-faint); text-transform:uppercase; letter-spacing:.06em; font-weight:700;
  padding:0 14px 10px 14px; border-bottom:1px solid var(--border); margin-bottom:2px;
}
.gx-dot{width:8px;height:8px;border-radius:50%; display:inline-block;}

/* ---------- Zone / corridor cards ---------- */
.gx-zone-card{
  background:var(--card-alt); border:1px solid var(--border); border-radius:10px;
  padding:14px 16px; margin-bottom:10px;
}
.gx-zone-row{display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;}
.gx-zone-name{font-weight:600; font-size:0.88rem; color:var(--text);}
.gx-risk-track{width:100%; height:7px; border-radius:999px; background:#1E293B; overflow:hidden;}
.gx-risk-fill{height:100%; border-radius:999px;}

.gx-rank-row{
  display:flex; align-items:center; gap:14px;
  padding:10px 4px; border-bottom:1px solid var(--border);
}
.gx-rank-row:last-child{border-bottom:none;}
.gx-rank-num{
  width:26px;height:26px;border-radius:7px; background:var(--card-alt); border:1px solid var(--border);
  display:flex;align-items:center;justify-content:center; font-size:0.74rem; font-weight:700; color:var(--text-dim);
  flex-shrink:0;
}

/* ---------- Workflow timeline ---------- */
.gx-wf{
  display:flex; align-items:center; gap:6px; background:var(--card-alt);
  border:1px solid var(--border); border-radius:999px; padding:8px 14px; font-size:0.78rem; font-weight:600;
  justify-content:center;
}

/* ---------- Chat ---------- */
/* NOTE: these were previously scoped under .gx-chat-wrap, but Streamlit's
   native widget blocks (st.form, st.container, st.chat_message) are NOT
   actual DOM children of the markdown div they appear after — the
   open/close <div> pattern via separate st.markdown calls does not nest
   them. Scoped rules silently never matched, which is why the Send button
   and chat input rendered with default (white) Streamlit styling. Made
   global since this app only has a single chat instance. */
[data-testid="stChatMessage"]{
  background:var(--card-alt);
  border:1px solid var(--border);
  border-radius:12px;
}
[data-testid="stChatMessageAvatarUser"],
[data-testid="stChatMessageAvatarAssistant"]{
  background:var(--info) !important;
}

/* Chat scroll container (the st.container(height=420) that holds messages) */
div[data-testid="stVerticalBlockBorderWrapper"]{
  background:var(--card-alt) !important;
  border:1px solid var(--border) !important;
  border-radius:10px !important;
}

/* In-card AI assistant input row (st.text_input + send button inside the form) */
div[data-testid="stTextInput"] input{
  background:var(--card-alt) !important;
  border:1px solid var(--border) !important;
  color:var(--text) !important;
  border-radius:10px !important;
}
div[data-testid="stTextInput"] input::placeholder{
  color:var(--text-faint) !important;
}
div[data-testid="stTextInput"] input:focus{
  border-color:var(--info) !important;
  box-shadow:0 0 0 1px var(--info) !important;
}
/* Form submit buttons (e.g. the chat Send button) were completely
   unstyled before — stFormSubmitButton is a distinct testid from the
   regular .stButton, so the generic button rule never reached it. */
div[data-testid="stFormSubmitButton"] button{
  background:linear-gradient(135deg,#1D4ED8,#3B82F6) !important;
  color:#fff !important;
  border:none !important;
  border-radius:10px !important;
  height:42px;
  font-weight:700 !important;
}
div[data-testid="stFormSubmitButton"] button:hover{
  filter:brightness(1.1);
  color:#fff !important;
}
div[data-testid="stFormSubmitButton"] button p{
  color:#fff !important;
}

/* ---------- Map ---------- */
.gx-map-wrap{
  background:var(--card-alt) !important;
  overflow:hidden;
}
.gx-map-wrap iframe{
  background:var(--card-alt) !important;
  border-radius:8px;
}
.gx-map-wrap div[data-testid="stIFrame"]{
  background:var(--card-alt) !important;
}
.leaflet-container{
  background:#0A0F1C !important;
}

/* ---------- Streamlit native overrides ---------- */
div[data-testid="stMetric"]{
  background:var(--card);
  border:1px solid var(--border);
  border-radius:var(--radius);
  padding:14px 16px;
  box-shadow:var(--shadow-sm);
}
div[data-testid="stMetric"] label{color:var(--text-faint) !important; font-size:0.72rem !important; text-transform:uppercase; letter-spacing:.05em;}
div[data-testid="stMetricValue"]{
  font-family:'JetBrains Mono',monospace;
  color:var(--text) !important;
}
div[data-testid="stMetricValue"] div{ color:var(--text) !important; }
div[data-testid="stMetricDelta"]{ color:var(--text-dim) !important; }

.stButton>button{
  border-radius:10px; font-weight:600; border:1px solid var(--border);
  background:var(--card); color:var(--text);
  transition:all .15s ease;
}
.stButton>button:hover{border-color:var(--info); color:var(--info); transform:translateY(-1px); box-shadow:var(--shadow-sm);}
.stButton>button[kind="primary"]{
  background:linear-gradient(135deg,#1D4ED8,#3B82F6); border:none; color:#fff;
  box-shadow:0 4px 14px rgba(59,130,246,0.3);
}
.stButton>button[kind="primary"]:hover{transform:translateY(-1px); box-shadow:0 6px 18px rgba(59,130,246,0.4); color:#fff;}

div[data-testid="stExpander"]{
  background:var(--card); border:1px solid var(--border); border-radius:var(--radius);
}

.stProgress > div > div{background:linear-gradient(90deg,#3B82F6,#22C55E) !important;}

div[data-testid="stForm"]{
  background:var(--card); border:1px solid var(--border); border-radius:var(--radius); padding:20px;
}

hr{border-color:var(--border) !important; margin:1.6rem 0 !important;}

[data-testid="stAlert"]{border-radius:10px;}

/* ---------- Widget labels (fixes invisible/illegible text on dark bg) ---------- */
[data-testid="stWidgetLabel"] p, [data-testid="stWidgetLabel"] label{
  color:var(--text-dim) !important; font-size:0.82rem !important; font-weight:500 !important;
}

/* ---------- Selectbox / dropdown (BaseWeb) — dark theme, white text ---------- */
div[data-baseweb="select"] > div{
  background:var(--card-alt) !important;
  border:1px solid var(--border) !important;
  border-radius:9px !important;
  color:#FFFFFF !important;
}
/* Force the visible selected-value text to bright white — using *
   alone left it too dim/low-contrast against the dark fill */
div[data-baseweb="select"] div[class*="ValueContainer"],
div[data-baseweb="select"] div[class*="singleValue"],
div[data-baseweb="select"] span,
div[data-baseweb="select"] div[class*="ValueContainer"] *{
  color:#FFFFFF !important;
  -webkit-text-fill-color:#FFFFFF !important;
  opacity:1 !important;
}
div[data-baseweb="select"] svg{ fill:var(--text-faint) !important; }

/* Dropdown popup menu — BaseWeb renders this in a portal, and depending
   on version uses different internal markup (ul>li, or role=listbox with
   role=option divs). Covering every variant since the previous narrower
   selector silently missed the actual structure being used here. */
ul[data-baseweb="menu"],
div[data-baseweb="popover"],
div[data-baseweb="popover"] ul,
div[role="listbox"]{
  background:#0F172A !important;
  border:1px solid #3B82F6 !important;
}
ul[data-baseweb="menu"] li,
div[role="listbox"] div[role="option"],
div[data-baseweb="popover"] li,
div[data-baseweb="popover"] [role="option"]{
  background:#0F172A !important;
}
ul[data-baseweb="menu"] li,
ul[data-baseweb="menu"] li *,
div[role="listbox"] div[role="option"],
div[role="listbox"] div[role="option"] *,
div[data-baseweb="popover"] li,
div[data-baseweb="popover"] li *,
div[data-baseweb="popover"] [role="option"],
div[data-baseweb="popover"] [role="option"] *{
  color:#FFFFFF !important;
  -webkit-text-fill-color:#FFFFFF !important;
  opacity:1 !important;
}
ul[data-baseweb="menu"] li:hover,
div[role="listbox"] div[role="option"]:hover,
div[data-baseweb="popover"] [role="option"]:hover{
  background:#1D4ED8 !important;
}
ul[data-baseweb="menu"] li[aria-selected="true"],
div[role="listbox"] div[role="option"][aria-selected="true"],
div[data-baseweb="popover"] [role="option"][aria-selected="true"]{
  background:#1D4ED8 !important;
}

/* ---------- Incident Details & Location sidebar panels — dark blue ---------- */
section[data-testid="stSidebar"] [data-testid="stExpander"]:nth-of-type(1),
section[data-testid="stSidebar"] [data-testid="stExpander"]:nth-of-type(2){
  background:#0B1736 !important;
  border:1px solid #1E3A8A !important;
}
section[data-testid="stSidebar"] [data-testid="stExpander"]:nth-of-type(1) summary,
section[data-testid="stSidebar"] [data-testid="stExpander"]:nth-of-type(2) summary{
  background:#0B1736 !important;
}
section[data-testid="stSidebar"] [data-testid="stExpander"]:nth-of-type(1) div[data-testid="stExpanderDetails"],
section[data-testid="stSidebar"] [data-testid="stExpander"]:nth-of-type(2) div[data-testid="stExpanderDetails"]{
  background:#0B1736 !important;
}

/* ---------- Text / number / textarea inputs — same white-box issue ---------- */
.stTextInput input, .stNumberInput input, .stTextArea textarea{
  background:var(--card-alt) !important;
  border:1px solid var(--border) !important;
  color:var(--text) !important;
  border-radius:9px !important;
  caret-color:var(--info) !important;
}
.stTextInput input::placeholder, .stTextArea textarea::placeholder{ color:var(--text-faint) !important; }
.stNumberInput button{ background:#1A2436 !important; border-color:var(--border) !important; }
.stNumberInput button svg{ fill:var(--text-dim) !important; }

/* ---------- Sliders ---------- */
.stSlider [data-baseweb="slider"] [role="slider"]{
  background:var(--info) !important; border:2px solid var(--bg) !important;
  box-shadow:0 0 0 3px rgba(59,130,246,0.25) !important;
}
.stSlider [data-baseweb="slider"] > div > div{ background:var(--border) !important; }
.stSlider [data-baseweb="slider"] > div > div > div{ background:var(--info) !important; }
.stSlider [data-testid="stTickBar"]{ color:var(--text-faint) !important; }
/* The floating number above the slider thumb (e.g. "6", "2.40") — real
   testid is stSliderThumbValue, not stThumbValue as previously written,
   which is why the earlier rule never matched anything. Styled as a small
   rounded pill so it reads as a tooltip rather than a jarring rectangle. */
div[data-testid="stSliderThumbValue"]{
  background:var(--info) !important;
  color:#FFFFFF !important;
  font-weight:700 !important;
  border-radius:999px !important;
  padding:1px 10px !important;
  font-size:0.85em !important;
}
div[data-testid="stSliderThumbValue"] p{ color:#FFFFFF !important; margin:0 !important; }
/* Tick-bar min/max endpoint labels ("0", "23") should stay plain muted
   text, not get swept into the thumb-value pill styling. */
div[data-testid="stTickBar"] [data-testid="stMarkdownContainer"] p{
  color:var(--text-faint) !important;
  background:transparent !important;
  font-weight:400 !important;
}

/* ---------- Checkboxes ---------- */
.stCheckbox label p{ color:var(--text-dim) !important; }
/* Streamlit's checkbox renders a real (visually hidden) <input
   type="checkbox"> alongside a styled "Checkmark" box whose checked
   appearance is driven by styled-components props ($checked) that are
   deliberately NOT forwarded to the DOM — so no CSS attribute selector
   (e.g. [aria-checked="true"]) ever matches it, which is why earlier
   attempts silently did nothing. :has() lets us style the checkbox
   container based on its real native input's actual :checked state
   instead, without needing BaseWeb's internal (hashed, unstable) class
   names at all. */
.stCheckbox [data-baseweb="checkbox"]{
  border-radius:4px;
}
.stCheckbox [data-baseweb="checkbox"]:not(:has(input:checked)) > span:first-of-type{
  background:var(--card-alt) !important;
  border-color:var(--border) !important;
}
.stCheckbox [data-baseweb="checkbox"]:has(input:checked) > span:first-of-type{
  background:#1D4ED8 !important;
  border-color:#3B82F6 !important;
}
.stCheckbox [data-baseweb="checkbox"]:has(input:checked) > span:first-of-type svg{
  fill:#FFFFFF !important;
  opacity:1 !important;
}
.stCheckbox [data-baseweb="checkbox"]:has(input:checked) ~ label,
.stCheckbox:has(input:checked) label p{
  color:#FFFFFF !important;
}

/* ---------- Tighter, denser layout: reduce dead vertical air ---------- */
.block-container{ padding-left:2rem; padding-right:2rem; }
div[data-testid="stVerticalBlock"] > div[style*="flex-direction"]{ gap:0.5rem; }
hr{ margin:1.1rem 0 !important; }
.gx-card{ margin-bottom:10px; }
[data-testid="column"]{ padding:0 6px; }
section[data-testid="stSidebar"] [data-testid="stExpander"] div[data-testid="stExpanderDetails"]{
  padding-top:6px;
}

/* ══════════════════════════════════════════════
   RESPONSIVE — make the app fit every screen size.
   Streamlit's own st.columns() already auto-stacks below ~640px, but the
   hand-built raw CSS grids below (header, feed rows, resource tiles,
   memory-card detail grid) don't get that behavior for free since they're
   plain HTML/CSS, not Streamlit layout primitives — each needs its own
   breakpoint or it will overflow / get unreadably squeezed on narrow
   screens (tablets, phones, split-screen windows).
   ══════════════════════════════════════════════ */

/* Large laptop / smaller desktop */
@media (max-width: 1200px){
  .block-container{ padding-left:1.25rem; padding-right:1.25rem; }
  .gx-header{ padding:14px 18px; }
  .gx-header-right{ gap:14px; }
}

/* Tablet */
@media (max-width: 900px){
  html, body, [class*="css"]{ font-size:15px; }
  .gx-header{ flex-wrap:wrap; gap:12px; row-gap:10px; }
  .gx-header-right{ width:100%; justify-content:space-between; flex-wrap:wrap; gap:10px; }
  .gx-feed-row, .gx-feed-head > .gx-feed-row{
    grid-template-columns: 1fr 1fr;
    row-gap:4px;
  }
  div[style*="grid-template-columns:repeat(3,1fr)"]{
    grid-template-columns:1fr 1fr !important;
  }
  /* KPI card labels ("ESTIMATED DELAY", "CONFIDENCE") were breaking
     mid-word at this width because uppercase + letter-spacing made the
     full word too wide for a single line in a 4-column st.columns() row,
     and the browser had no good word-boundary to wrap at. Tightening
     letter-spacing and font-size here lets the full word fit; word-break
     is pinned to normal as a backstop so it never splits a word again
     even if a future label is longer. */
  .gx-kpi-label{
    font-size:0.62rem;
    letter-spacing:.02em;
    word-break:normal;
    overflow-wrap:normal;
    white-space:normal;
  }
  .gx-kpi-value{ font-size:1.35rem; }
  .gx-kpi-dominant .gx-kpi-value{ font-size:1.7rem; }
}

/* Phone / narrow window */
@media (max-width: 640px){
  .block-container{ padding-left:0.75rem; padding-right:0.75rem; }
  html, body, [class*="css"]{ font-size:14px; }
  .gx-header{ padding:12px 14px; }
  .gx-title{ font-size:1.1rem; }
  .gx-subtitle{ font-size:0.7rem; }
  .gx-header-stat{ text-align:left; }
  .gx-kpi-dominant .gx-kpi-value{ font-size:1.7rem; }
  .gx-kpi-value{ font-size:1.3rem; }
  .gx-card{ padding:14px 14px; }
  .gx-feed-row{
    grid-template-columns: 1fr !important;
    gap:4px;
    padding:10px 8px;
  }
  .gx-feed-head{ display:none; } /* column headers don't make sense in a single-column stacked layout */
  div[style*="grid-template-columns:1fr 1fr; gap:6px 18px"]{
    grid-template-columns:1fr !important;
  }
  div[style*="grid-template-columns:repeat(3,1fr)"]{
    grid-template-columns:1fr !important;
  }
  .gx-scenario{ padding:12px; }
  /* Verified empirically (Playwright) that Streamlit's sidebar does NOT
     automatically become an overlay on narrow viewports — it stays in
     normal document flow at a fixed ~300px width, which on a ~390px phone
     leaves only a thin sliver for the main content, visible bleeding
     through alongside it. Force it into a fixed, full-width overlay here
     instead so it properly takes over the screen when open, matching how
     a responsive drawer should behave. */
  section[data-testid="stSidebar"]{
    position:fixed !important;
    top:0; left:0; bottom:0;
    width:100vw !important;
    max-width:100vw !important;
    z-index:999999 !important;
  }
  section[data-testid="stSidebar"][aria-expanded="false"]{
    transform:translateX(-100%);
  }
}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════
SEVERITY_DISPLAY = {
    "Severe":   {"emoji": "🔴", "folium_color": "red",    "radius": 1000, "badge": "gx-badge-severe",   "hex": "#EF4444"},
    "Moderate": {"emoji": "🟡", "folium_color": "orange", "radius": 600,  "badge": "gx-badge-moderate", "hex": "#F59E0B"},
    "Quick":    {"emoji": "🟢", "folium_color": "green",  "radius": 300,  "badge": "gx-badge-quick",    "hex": "#22C55E"},
}

ZONE_COORDS = {
    "Central Zone 1": [12.9716, 77.5946],
    "Central Zone 2": [12.9800, 77.6000],
    "North Zone 1"  : [13.0500, 77.5800],
    "North Zone 2"  : [13.0800, 77.6000],
    "South Zone 1"  : [12.9000, 77.5700],
    "South Zone 2"  : [12.8700, 77.6000],
    "East Zone 1"   : [12.9900, 77.6500],
    "East Zone 2"   : [12.9600, 77.7000],
    "West Zone 1"   : [12.9700, 77.5300],
    "West Zone 2"   : [12.9400, 77.5000],
}

# ══════════════════════════════════════════════
# API HEALTH CHECK (for header status pill)
# ══════════════════════════════════════════════
api_online = False
try:
    _health = requests.get(f"{API}/", timeout=3)
    api_online = _health.status_code in (200, 404)  # server responding at all
except Exception:
    try:
        _health = requests.get(f"{API}/kpi-summary", timeout=3)
        api_online = _health.status_code == 200
    except Exception:
        api_online = False

# ══════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════
_now_str = datetime.now().strftime("%H:%M:%S")
_date_str = datetime.now().strftime("%d %b %Y")
_status_class = "gx-pill-ok" if api_online else "gx-pill-bad"
_status_text = "OPERATIONAL" if api_online else "OFFLINE"

st.markdown(f"""
<div class="gx-header">
  <div class="gx-header-left">
    <div class="gx-logo-badge">🚦</div>
    <div>
      <div class="gx-title">GRIDLOCK</div>
      <div class="gx-subtitle">Traffic Congestion Command Center</div>
    </div>
  </div>
  <div class="gx-header-right">
    <div class="gx-header-stat">
      <div class="gx-header-stat-label">Local Time</div>
      <div class="gx-header-stat-value">{_now_str} · {_date_str}</div>
    </div>
    <div class="gx-header-stat">
      <div class="gx-header-stat-label">System Status</div>
      <div class="gx-header-stat-value">Active Session</div>
    </div>
    <div class="gx-pill {_status_class}">
      <span class="pulse"></span> API {_status_text}
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════
# SIDEBAR — EVENT INPUT (organized into expanders)
# ══════════════════════════════════════════════
st.sidebar.markdown(
    "<div style='font-size:0.95rem;font-weight:800;color:#fff;letter-spacing:.02em;"
    "margin-bottom:4px;'>⚙️ MISSION CONTROL</div>"
    "<div style='font-size:0.72rem;color:#64748B;margin-bottom:16px;'>Configure incident parameters</div>",
    unsafe_allow_html=True
)

with st.sidebar.expander("🚨 INCIDENT DETAILS", expanded=True):
    event_type = st.selectbox("Event Type", ["unplanned", "planned"])

    PLANNED_CAUSES = [
        "public_event",
        "procession",
        "vip_movement",
        "construction",
        "test_demo"
    ]
    UNPLANNED_CAUSES = [
        "accident",
        "vehicle_breakdown",
        "tree_fall",
        "water_logging",
        "debris",
        "congestion",
        "pot_holes",
        "road_conditions"
    ]

    if event_type == "planned":
        event_cause = st.selectbox(
            "Event Cause",
            PLANNED_CAUSES,
            help="Only planned event causes available"
        )
    else:
        event_cause = st.selectbox(
            "Event Cause",
            UNPLANNED_CAUSES,
            help="Only unplanned event causes available"
        )

    priority = st.selectbox("Priority", ["High", "Low"])
    requires_road_closure = st.checkbox("Requires Road Closure?")
    # Vehicle type only relevant for accident/vehicle_breakdown
    VEHICLE_CAUSES = ["accident", "vehicle_breakdown"]
    if event_cause in VEHICLE_CAUSES:
      veh_type = st.selectbox("Vehicle Type", [
        "none", "car", "bus", "truck", "two_wheeler", "auto", "heavy_vehicle"
      ])
    else:
      veh_type = "none"
      st.caption("🚫 Vehicle type not applicable for this cause")


with st.sidebar.expander("📍 LOCATION", expanded=True):
    zone = st.selectbox("Zone", [
        "Central Zone 1", "Central Zone 2", "North Zone 1", "North Zone 2",
        "South Zone 1", "South Zone 2", "East Zone 1", "East Zone 2",
        "West Zone 1", "West Zone 2"
    ])
    corridor = st.selectbox("Corridor", [
        "Non-corridor", "Mysore Road", "Bellary Road 1", "Bellary Road 2",
        "Tumkur Road", "Hosur Road", "ORR North 1", "Old Madras Road",
        "Magadi Road", "ORR East 1"
    ])
    # Police Station and Junction fields removed — not used downstream by the
    # model or the memory engine in a way that justified the extra input friction.

with st.sidebar.expander("⏰ TIME CONTEXT", expanded=True):
    now         = datetime.now()
    hour        = st.slider("Hour of Day", 0, 23, now.hour)
    day_of_week = st.selectbox("Day of Week",
        ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"],
        index=now.weekday()
    )
    month   = st.slider("Month", 1, 12, now.month)
    day_idx = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"].index(day_of_week)

with st.sidebar.expander("🧪 DIGITAL TWIN", expanded=True):
    attendance_multiplier = st.slider("Attendance Multiplier", 1.0, 5.0, 2.4, 0.1)
    extra_barricades      = st.slider("Extra Barricades", 0, 10, 4)
    close_main_road        = st.checkbox("Close Main Road?")

center = ZONE_COORDS.get(zone, [12.9716, 77.5946])

payload = {
    "event_type"            : event_type,
    "event_cause"           : event_cause,
    "priority"               : priority,
    "requires_road_closure"   : requires_road_closure,
    "latitude"                 : center[0],
    "longitude"                 : center[1],
    "zone"                       : zone,
    "corridor"                    : corridor,
    "veh_type"                     : veh_type,
    "police_station"                 : "Unknown",
    "junction"                         : None,
    "hour"                               : hour,
    "day_of_week"                         : day_idx,
    "month"                                : month,
}

twin_payload = {
    **payload,
    "extra_barricades"      : extra_barricades,
    "close_main_road"       : close_main_road or requires_road_closure,
    "attendance_multiplier" : attendance_multiplier,
}

# ══════════════════════════════════════════════
# TOP KPI ROW — Current Prediction (dominant) + Live Aggregates
# ══════════════════════════════════════════════
st.markdown('<div class="gx-section-title"><span class="dot"></span>CURRENT PREDICTION SUMMARY</div>', unsafe_allow_html=True)

k1, k2, k3, k4 = st.columns(4)

if "last_prediction" in st.session_state:
    data  = st.session_state["last_prediction"]
    level = data["severity"]
    disp  = SEVERITY_DISPLAY.get(level, {"hex": "#94A3B8", "emoji": "⚪"})
    conf_pct = (data.get('confidence') or 0) * 100
    clearance = data.get('estimated_clearance', 60)
    zone_risk = "High" if level == "Severe" else "Medium" if level == "Moderate" else "Low"
    zone_risk_hex = {"High": "#EF4444", "Medium": "#F59E0B", "Low": "#22C55E"}[zone_risk]

    with k1:
        st.markdown(f"""
        <div class="gx-kpi gx-kpi-dominant">
          <div class="gx-kpi-accent" style="background:{disp['hex']};"></div>
          <div class="gx-kpi-label">Severity</div>
          <div class="gx-kpi-value" style="color:{disp['hex']};">{disp['emoji']} {level}</div>
          <div class="gx-kpi-sub">Zone-dominant classification</div>
        </div>
        """, unsafe_allow_html=True)
    with k2:
        st.markdown(f"""
        <div class="gx-kpi">
          <div class="gx-kpi-accent" style="background:#3B82F6;"></div>
          <div class="gx-kpi-label">Confidence</div>
          <div class="gx-kpi-value">{conf_pct:.0f}%</div>
          <div class="gx-kpi-sub">Model certainty</div>
        </div>
        """, unsafe_allow_html=True)
    with k3:
        st.markdown(f"""
        <div class="gx-kpi">
          <div class="gx-kpi-accent" style="background:#F59E0B;"></div>
          <div class="gx-kpi-label">Estimated Delay</div>
          <div class="gx-kpi-value">{data['delay_minutes']:.0f}<span style="font-size:0.9rem;">min</span></div>
          <div class="gx-kpi-sub">Clearance ~{clearance} min</div>
        </div>
        """, unsafe_allow_html=True)
    with k4:
        st.markdown(f"""
        <div class="gx-kpi">
          <div class="gx-kpi-accent" style="background:{zone_risk_hex};"></div>
          <div class="gx-kpi-label">Zone Risk</div>
          <div class="gx-kpi-value" style="color:{zone_risk_hex};">{zone_risk}</div>
          <div class="gx-kpi-sub">{zone}</div>
        </div>
        """, unsafe_allow_html=True)
else:
    for col, label in zip([k1, k2, k3, k4], ["Severity", "Confidence", "Estimated Delay", "Zone Risk"]):
        with col:
            st.markdown(f"""
            <div class="gx-kpi">
              <div class="gx-kpi-accent" style="background:#374151;"></div>
              <div class="gx-kpi-label">{label}</div>
              <div class="gx-kpi-value" style="color:#64748B;">—</div>
              <div class="gx-kpi-sub">Run a prediction to populate</div>
            </div>
            """, unsafe_allow_html=True)

st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)
st.markdown('<div class="gx-section-title"><span class="dot"></span>LIVE AGGREGATE — LAST 24 HOURS</div>', unsafe_allow_html=True)

try:
    kpi_res = requests.get(f"{API}/kpi-summary", timeout=10)
    if kpi_res.status_code == 200:
        kpi = kpi_res.json()
        ka1, ka2, ka3, ka4 = st.columns(4)
        ka1.metric("🚨 Active Incidents",       kpi["active_incidents"])
        ka2.metric("🔴 Predicted Severe Cases",  kpi["predicted_severe_cases"])
        ka3.metric("⏱️ Avg Expected Delay",      f"{kpi['avg_expected_delay_mins']:.0f} min")
        ka4.metric("🗺️ High Risk Zones",         kpi["high_risk_zones_flagged"])
    else:
        st.info("KPI data unavailable.")
except Exception:
    st.info("Start API to see KPI summary.")

st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
st.divider()

# ══════════════════════════════════════════════
# MAIN WORKSPACE — Prediction Center + Congestion Map
# ══════════════════════════════════════════════
col1, col2 = st.columns([1, 1])

with col1:
    st.markdown('<div class="gx-section-title"><span class="dot"></span>🔮 PREDICTION CENTER</div>', unsafe_allow_html=True)

    if st.button("⚡ Predict & Log Event", type="primary", use_container_width=True):
        with st.spinner("Predicting..."):
            try:
                res = requests.post(f"{API}/predict-and-log", json=payload, timeout=15)
            except requests.exceptions.RequestException as ex:
                st.error(f"Could not reach API: {ex}")
                res = None

        if res is not None:
            if res.status_code == 200:
                data = res.json()
                st.session_state["last_prediction"] = data
                st.session_state["last_payload"]    = payload
                # A new prediction invalidates any historical-similarity
                # markers drawn for the previous event.
                st.session_state.pop("similar_events", None)
                st.rerun()
            else:
                st.error(f"API error {res.status_code}: {res.text}")

    if "last_prediction" in st.session_state:
        data  = st.session_state["last_prediction"]
        level = data["severity"]
        disp  = SEVERITY_DISPLAY.get(level, {"emoji": "⚪", "badge": "gx-badge-neutral"})

        st.markdown(f"""
        <div class="gx-card">
          <span class="gx-badge {disp['badge']}">{disp['emoji']} {level.upper()}</span>
          <div style="margin-top:14px; display:flex; gap:28px;">
            <div>
              <div class="gx-kpi-label">Predicted Delay</div>
              <div style="font-size:1.5rem;font-weight:800;font-family:'JetBrains Mono',monospace;">{data['delay_minutes']:.0f} min</div>
            </div>
            <div>
              <div class="gx-kpi-label">Confidence</div>
              <div style="font-size:1.5rem;font-weight:800;font-family:'JetBrains Mono',monospace;">{(data.get('confidence') or 0)*100:.0f}%</div>
            </div>
            <div>
              <div class="gx-kpi-label">Est. Clearance</div>
              <div style="font-size:1.5rem;font-weight:800;font-family:'JetBrains Mono',monospace;">{data.get('estimated_clearance', 60)} min</div>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="gx-section-title" style="margin-top:6px;"><span class="dot"></span>RECOMMENDED RESPONSE STRATEGY</div>', unsafe_allow_html=True)
        resources = data["resources"]
        priority_label = {"Severe": "🚨 IMMEDIATE", "Moderate": "⚠️ HIGH", "Quick": "🟢 STANDARD"}

        st.markdown(f"""
        <div class="gx-card gx-card-tight">
          <div style="font-weight:700; margin-bottom:12px;">
            Priority: {priority_label.get(level, '⚠️ HIGH')}
          </div>
          <div style="display:grid; grid-template-columns:repeat(3,1fr); gap:10px;">
            <div class="gx-tile"><div class="gx-tile-icon">👮</div><div class="gx-tile-value">{resources['officers']}</div><div class="gx-tile-label">Officers</div></div>
            <div class="gx-tile"><div class="gx-tile-icon">🚧</div><div class="gx-tile-value">{resources['barricades']}</div><div class="gx-tile-label">Barricades</div></div>
            <div class="gx-tile"><div class="gx-tile-icon">🔀</div><div class="gx-tile-value">{resources['diversions']}</div><div class="gx-tile-label">Diversions</div></div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        action_steps = {
            "Severe": [
                "Deploy 8+ Officers to incident site immediately",
                "Deploy 4+ Barricades on all approach roads",
                "Activate 2 Diversion Routes",
                "Alert Traffic Control Center",
                "Notify nearest police station",
            ],
            "Moderate": [
                "Deploy 4-6 Officers to incident site",
                "Deploy 2-3 Barricades on main approach",
                "Activate 1 Diversion Route",
                "Monitor situation every 15 minutes",
            ],
            "Quick": [
                "Deploy 1-2 Officers to incident site",
                "Standard monitoring — no diversion needed",
                "Update status every 30 minutes",
            ],
        }
        steps_html = "".join(
            f'<div class="gx-step"><span class="gx-step-num">{i+1}</span><span>{step}</span></div>'
            for i, step in enumerate(action_steps.get(level, []))
        )
        st.markdown(f"""
        <div class="gx-card gx-card-tight">
          <div class="gx-section-title" style="margin-bottom:8px;">ACTION STEPS</div>
          {steps_html}
        </div>
        """, unsafe_allow_html=True)

        # Use the snapshotted payload from when THIS prediction was made,
        # not the live `payload` variable — `payload` reflects whatever
        # the sidebar currently says, which can have changed since the
        # prediction ran (e.g. checking "Requires Road Closure?" after
        # the fact). Reading live state here made the banner pop up/down
        # based on sidebar edits that the displayed prediction never
        # actually accounted for — looking like the checkbox was wired
        # backwards when it was actually just out of sync with the
        # results being shown above it.
        snapshot_payload = st.session_state.get("last_payload", payload)
        if snapshot_payload["hour"] in [8, 9, 10, 17, 18, 19]:
            st.warning("⚠️ Peak hour — expect higher congestion impact")
        if snapshot_payload["requires_road_closure"]:
            st.error("🚫 Road closure required — activate diversion plan immediately")

        st.caption(f"Event ID: {data.get('event_id','—')} | Corridor: {snapshot_payload['corridor']} | Zone: {snapshot_payload['zone']}")
    else:
        st.markdown("""
        <div class="gx-card" style="text-align:center; padding:36px 20px; color:#64748B;">
          Run a prediction to populate the command center.
        </div>
        """, unsafe_allow_html=True)

with col2:
    st.markdown('<div class="gx-section-title"><span class="dot"></span>🗺️ INTERACTIVE CONGESTION MAP</div>', unsafe_allow_html=True)
    st.markdown("""
    <div style="display:flex; gap:14px; margin-bottom:10px; font-size:0.78rem; color:#94A3B8;">
      <span>🔴 High Risk</span><span>🟠 Moderate Risk</span><span>🟢 Low Risk</span>
      <span>⭕ Risk Radius</span><span>📍 Historical Incident</span>
    </div>
    """, unsafe_allow_html=True)

    m = folium.Map(
        location=center,
        zoom_start=13,
        tiles=None,
    )
    folium.TileLayer(
        tiles="https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        attr="&copy; OpenStreetMap contributors",
        name="Dark Base",
    ).add_to(m)
    # The map renders inside an <iframe>, which the outer page's CSS cannot
    # reach (browsers block cross-document style leakage even for
    # same-origin iframes built from inline HTML). Standard OSM tiles are
    # light by default, so invert+hue-rotate them here, inside the iframe's
    # own HTML, to match the dark theme without depending on a third-party
    # dark-tile CDN (CartoDB's dark_matter endpoint was unreliable).
    m.get_root().html.add_child(folium.Element("""
        <style>
          .leaflet-tile-pane{ filter: invert(1) hue-rotate(180deg) brightness(0.92) contrast(0.9) saturate(0.7); }
          .leaflet-container{ background:#0A0F1C !important; }
        </style>
    """))

    # ── 1. Current incident marker + 3. risk radius circle ──
    if "last_prediction" in st.session_state:
        level = st.session_state["last_prediction"]["severity"]
        disp  = SEVERITY_DISPLAY.get(level, {"folium_color": "blue", "radius": 400})

        folium.Circle(
            location=center,
            radius=disp["radius"],
            color=disp["folium_color"],
            fill=True,
            fill_opacity=0.15,
            weight=2,
            popup=f"Risk Radius — {level} ({disp['radius']}m)"
        ).add_to(m)

        folium.Marker(
            location=center,
            popup=folium.Popup(
                f"<b>Current Incident</b><br>"
                f"{event_cause} — {corridor}<br>"
                f"Severity: {level}<br>"
                f"Delay: {st.session_state['last_prediction']['delay_minutes']:.0f} min",
                max_width=250
            ),
            tooltip="Current Incident",
            icon=folium.Icon(color=disp["folium_color"], icon="warning-sign", prefix="glyphicon")
        ).add_to(m)
    else:
        # No prediction yet — still show the selected zone center as a
        # neutral reference point so the map isn't empty.
        folium.Marker(
            location=center,
            tooltip="Selected zone center",
            icon=folium.Icon(color="blue", icon="map-marker", prefix="glyphicon")
        ).add_to(m)

    # ── 2. Similar historical incident markers + 4. MarkerCluster hotspots ──
    similar = st.session_state.get("similar_events", [])
    geocoded_similar = [e for e in similar if e.get("latitude") is not None and e.get("longitude") is not None]

    if geocoded_similar:
        cluster = MarkerCluster(name="Historical Incidents").add_to(m)
        for e in geocoded_similar:
            sev      = e.get("predicted_severity", "Moderate")
            sev_disp = SEVERITY_DISPLAY.get(sev, {"folium_color": "gray"})
            plan     = e.get("plan_used") or "No plan logged"
            delay    = e.get("predicted_delay_mins")
            delay_txt = f"{delay:.0f} min" if delay is not None else "N/A"

            folium.Marker(
                location=[e["latitude"], e["longitude"]],
                popup=folium.Popup(
                    f"<b>Historical Incident</b><br>"
                    f"{e.get('event_cause','—')} — {e.get('corridor','—')}<br>"
                    f"Severity: {sev}<br>"
                    f"Delay: {delay_txt}<br>"
                    f"Plan used: {plan}<br>"
                    f"Similarity: {e.get('similarity_score', 0):.0f}%",
                    max_width=250
                ),
                tooltip=f"{sev} — {e.get('event_cause','—')}",
                icon=folium.Icon(color=sev_disp["folium_color"], icon="info-sign", prefix="glyphicon")
            ).add_to(cluster)
    elif similar and not geocoded_similar:
        st.caption("ℹ️ Similar events found, but no location data was stored for them yet.")

    st.markdown('<div class="gx-card gx-card-tight gx-map-wrap">', unsafe_allow_html=True)
    st_folium(m, use_container_width=True, height=420, returned_objects=[])
    st.markdown('</div>', unsafe_allow_html=True)

    if "last_prediction" in st.session_state:
        lvl = st.session_state["last_prediction"]["severity"]
        st.markdown(f"""
        <div class="gx-card gx-card-tight" style="margin-top:10px;">
          <div style="font-size:0.8rem; color:#94A3B8;"><b>Current Incident:</b> {event_cause} — {corridor} ({lvl})</div>
          <div style="font-size:0.8rem; color:#94A3B8; margin-top:4px;"><b>Historical Incidents Shown:</b> {len(geocoded_similar)}</div>
          <div style="font-size:0.8rem; color:#94A3B8; margin-top:4px;"><b>Risk Radius:</b> {SEVERITY_DISPLAY.get(lvl,{}).get('radius','—')} m</div>
        </div>
        """, unsafe_allow_html=True)

st.divider()

# ══════════════════════════════════════════════
# ANALYTICS SECTION
# ══════════════════════════════════════════════
st.markdown('<div class="gx-section-title"><span class="dot"></span>📡 OPERATIONS ANALYTICS</div>', unsafe_allow_html=True)

# ---------- EXPLAINABILITY ----------
if "last_prediction" in st.session_state:
    st.markdown("#### 🔍 Why This Prediction?")
    explanation = st.session_state["last_prediction"].get("explanation", [])
    if explanation:
        chips_html = "".join(f'<span class="gx-chip">✓ {reason}</span>' for reason in explanation)
        st.markdown(f'<div class="gx-card">{chips_html}</div>', unsafe_allow_html=True)
    else:
        st.info("Standard incident — no high-risk factors detected")

    # ---------- EXPLAINABILITY CARD (memory-engine grounded) ----------
    st.markdown("#### 🧠 Why This Recommendation?")
    similar = st.session_state.get("similar_events", [])
    pred    = st.session_state["last_prediction"]

    with st.container(border=True):
        if similar:
            delays = [e["predicted_delay_mins"] for e in similar if e.get("predicted_delay_mins") is not None]
            reductions = [e["delay_reduced_pct"] for e in similar if e.get("delay_reduced_pct")]

            avg_delay = sum(delays) / len(delays) if delays else None
            avg_reduction = sum(reductions) / len(reductions) if reductions else None

            ec1, ec2, ec3 = st.columns(3)
            ec1.metric("📚 Similar Incidents", len(similar))
            ec2.metric("⏱️ Avg Similar Delay", f"{avg_delay:.0f} min" if avg_delay is not None else "—")
            ec3.metric("📉 Avg Delay Reduction", f"{avg_reduction:.0f}%" if avg_reduction is not None else "—")

            st.markdown(f"✓ **{len(similar)} similar historical incidents** found in memory")
            if avg_delay is not None:
                st.markdown(f"✓ Average delay across similar incidents: **{avg_delay:.0f} min**")
            if avg_reduction is not None:
                st.markdown(f"✓ Similar past response plans reduced delay by **{avg_reduction:.0f}%** on average")
        else:
            st.markdown("✓ No similar incidents in memory yet — click **Find Similar Past Events** below to populate this card")

        top_factors = pred.get("explanation", [])[:3]
        if top_factors:
            st.markdown("**Top factors influencing this prediction:**")
            for factor in top_factors:
                st.markdown(f"{factor}")

        conf = pred.get("confidence")
        if conf is not None:
            st.markdown(f"✓ Model confidence: **{conf*100:.0f}%**")

    st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)

# ---------- DIGITAL TWIN SIMULATOR ----------
st.markdown("#### 🔧 Digital Twin Simulator — What If?")
st.caption("Simulates how different interventions would change the predicted outcome. Post-hoc adjustment, clearly labeled.")

if st.button("🔄 Run Digital Twin Simulation", use_container_width=True):
    with st.spinner("Simulating scenarios..."):
        try:
            res = requests.post(f"{API}/digital-twin", json=twin_payload, timeout=15)
        except requests.exceptions.RequestException as ex:
            st.error(f"Could not reach API: {ex}")
            res = None

    if res is not None and res.status_code == 200:
        twin = res.json()
        st.session_state["twin_result"] = twin
    elif res is not None:
        st.error(f"API error {res.status_code}: {res.text}")

if "twin_result" in st.session_state:
    twin      = st.session_state["twin_result"]
    baseline  = twin["baseline"]
    scenarios = twin["scenarios"]
    best      = twin["best_scenario"]

    base_disp = SEVERITY_DISPLAY.get(baseline["severity"], {"emoji": "⚪", "hex": "#94A3B8"})
    st.markdown(f"""
    <div class="gx-card gx-card-tight">
      <div class="gx-kpi-label">📍 BASELINE PREDICTION (no intervention)</div>
      <div style="display:flex; gap:32px; margin-top:8px;">
        <div><div class="gx-kpi-label">Severity</div>
          <div style="font-weight:800;color:{base_disp['hex']};font-size:1.1rem;">{base_disp['emoji']} {baseline['severity']}</div></div>
        <div><div class="gx-kpi-label">Predicted Delay</div>
          <div style="font-weight:800;font-size:1.1rem;font-family:'JetBrains Mono',monospace;">{baseline['delay_minutes']:.0f} min</div></div>
        <div><div class="gx-kpi-label">Est. Clearance</div>
          <div style="font-weight:800;font-size:1.1rem;font-family:'JetBrains Mono',monospace;">{baseline['estimated_clearance']} min</div></div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("**🔄 What-If Scenarios (simulated):**")
    sc_cols = st.columns(3)
    for i, sc in enumerate(scenarios):
        with sc_cols[i]:
            is_best = sc["scenario"] == best
            change  = sc["delay_change_mins"]
            arrow   = "📉" if change < 0 else "📈"
            sev_disp = SEVERITY_DISPLAY.get(sc["adjusted_severity"], {"emoji":"⚪"})
            card_class = "gx-scenario gx-scenario-best" if is_best else "gx-scenario"
            best_tag = '<span class="gx-best-tag">⭐ BEST OPTION</span>' if is_best else ""
            st.markdown(f"""
            <div class="{card_class}">
              {best_tag}
              <div style="font-weight:700;font-size:0.95rem;margin-bottom:10px;">{sc['scenario']}</div>
              <div class="gx-kpi-label">Adjusted Delay</div>
              <div style="font-size:1.3rem;font-weight:800;font-family:'JetBrains Mono',monospace;">{sc['adjusted_delay_mins']:.0f} min</div>
              <div style="font-size:0.78rem; color:{'#22C55E' if change < 0 else '#F59E0B'}; margin-bottom:8px;">{change:+.0f} min</div>
              <div style="font-size:0.85rem;">{sev_disp['emoji']} {sc['adjusted_severity']}</div>
              <div style="font-size:0.8rem; color:#94A3B8; margin-top:4px;">{arrow} {abs(sc['delay_change_pct']):.0f}% {'reduction' if change < 0 else 'increase'}</div>
            </div>
            """, unsafe_allow_html=True)

    st.info(f"✅ **Best Option: {best}** — lowest predicted delay after intervention")
    st.caption(twin["simulation_note"])

st.divider()

# ---------- MEMORY ENGINE — Similar Past Events ----------
st.markdown("#### 🧠 Memory Engine — Similar Past Events")
st.caption("Most unique feature — retrieves what worked in similar past incidents, ranked by similarity %")

if st.button("🔍 Find Similar Past Events", use_container_width=True):
    with st.spinner("Searching memory..."):
        try:
            res = requests.post(f"{API}/similar-events", json=payload, timeout=15)
        except requests.exceptions.RequestException as ex:
            st.error(f"Could not reach API: {ex}")
            res = None

    if res is not None and res.status_code == 200:
        st.session_state["similar_events"] = res.json().get("results", [])
        st.rerun()
    elif res is not None:
        st.error(f"API error {res.status_code}: {res.text}")

if "similar_events" in st.session_state:
    similar = st.session_state["similar_events"]
    if not similar:
        st.info("No similar past events found in memory yet.")
    else:
        best_idx = max(range(len(similar)), key=lambda i: similar[i].get("similarity_score", 0))
        for i, e in enumerate(similar):
            sev   = e["predicted_severity"]
            badge = SEVERITY_DISPLAY.get(sev, {"emoji": "⚪"})["emoji"]
            sim_pct = e.get("similarity_score", 0)
            is_best = (i == best_idx)
            card_class = "gx-mem-card gx-mem-card-best" if is_best else "gx-mem-card"
            best_tag = '<span style="font-size:0.68rem;font-weight:800;color:#22C55E;letter-spacing:.04em;">⭐ BEST MATCH</span>' if is_best else ""

            st.markdown(f"""
            <div class="{card_class}">
              <div class="gx-mem-header">
                <span class="gx-mem-title">{badge} {e['event_cause']} — {e['corridor']}</span>
                {best_tag}
              </div>
              <div class="gx-kpi-label">Similarity Score: {sim_pct:.0f}%</div>
              <div class="gx-sim-track"><div class="gx-sim-fill" style="width:{min(sim_pct,100)}%;"></div></div>
              <div style="display:grid; grid-template-columns:1fr 1fr; gap:6px 18px; font-size:0.84rem; color:#CBD5E1;">
                <div><b>Zone:</b> {e['zone']}</div>
                <div><b>Predicted Severity:</b> {sev}</div>
                <div><b>Predicted Delay:</b> {e.get('predicted_delay_mins','N/A')} min</div>
                <div><b>Plan Used:</b> {e.get('plan_used','N/A')}</div>
                <div><b>Delay Reduced:</b> {e.get('delay_reduced_pct','N/A')}%</div>
                <div><b>Outcome:</b> {e['outcome_badge']}</div>
              </div>
              <div style="font-size:0.8rem; color:#64748B; margin-top:8px;">Notes: {e.get('notes','—')}</div>
            </div>
            """, unsafe_allow_html=True)

st.divider()

# ---------- LIVE OPERATIONS FEED ----------
st.markdown("#### 📡 Live Operations Feed")
st.caption("Most recent incidents logged into the system, real-time command center style")

try:
    feed_res = requests.get(f"{API}/live-feed", params={"limit": 8}, timeout=10)
    if feed_res.status_code == 200:
        feed = feed_res.json().get("feed", [])
        if not feed:
            st.info("No incidents logged yet. Predict an event to populate the feed.")
        else:
            row_parts = ['<div class="gx-feed-head"><div class="gx-feed-row" style="border:none;padding:0;"><span>STATUS</span><span>EVENT</span><span>ZONE</span><span>DELAY</span><span>SEVERITY</span></div></div>']
            for item in feed:
                sev_disp = SEVERITY_DISPLAY.get(item["severity"], {"emoji": "⚪", "hex": "#94A3B8"})
                status_dot = "#22C55E" if item["status"] == "Resolved" else "#EF4444"
                status_label = "✅ Resolved" if item["status"] == "Resolved" else "🔴 Active"
                delay_txt = f"{item['delay_minutes']:.0f} min" if item['delay_minutes'] else "—"
                row_parts.append(
                    '<div class="gx-feed-row">'
                    f'<span><span class="gx-dot" style="background:{status_dot};"></span> {status_label}</span>'
                    f'<span><b>{item["event_cause"]}</b> — {item["corridor"]}</span>'
                    f'<span>{item["zone"]}</span>'
                    f'<span>{delay_txt}</span>'
                    f'<span style="color:{sev_disp["hex"]};font-weight:600;">{sev_disp["emoji"]} {item["severity"]}</span>'
                    '</div>'
                )
            rows_html = "".join(row_parts)
            st.markdown(f'<div class="gx-card gx-card-tight">{rows_html}</div>', unsafe_allow_html=True)
    else:
        st.info("Live feed unavailable.")
except Exception:
    st.info("Start API to see live operations feed.")

st.divider()

# ---------- CORRIDOR RISK RANKING (leaderboard) ----------
st.markdown("#### 🛣️ Corridor Risk Ranking")
st.caption("Derived from historical Astram incident density — no extra data required")

try:
    cr_res = requests.get(f"{API}/corridor-risk", timeout=10)
    if cr_res.status_code == 200:
        corridors = cr_res.json()["corridors"]
        rank_parts = []
        for i, c in enumerate(corridors):
            color = "#EF4444" if c["risk_score"] > 75 else "#F59E0B" if c["risk_score"] > 50 else "#22C55E"
            level = "High" if c["risk_score"] > 75 else "Moderate" if c["risk_score"] > 50 else "Low"
            rank_parts.append(
                '<div class="gx-rank-row">'
                f'<div class="gx-rank-num">#{i+1}</div>'
                f'<div style="flex:1; font-weight:600; font-size:0.88rem;">{c["corridor"]}</div>'
                '<div style="flex:2;">'
                f'<div class="gx-risk-track"><div class="gx-risk-fill" style="width:{c["risk_score"]}%; background:{color};"></div></div>'
                '</div>'
                f'<div style="width:90px; text-align:right; font-family:\'JetBrains Mono\',monospace; font-weight:700; color:{color};">{c["risk_score"]}/100</div>'
                f'<div style="width:80px; text-align:right; font-size:0.78rem; color:{color};">{level}</div>'
                '</div>'
            )
        rank_html = "".join(rank_parts)
        st.markdown(f'<div class="gx-card gx-card-tight">{rank_html}</div>', unsafe_allow_html=True)
except Exception:
    st.info("Start API to see corridor risk data.")

st.divider()

# ---------- ZONE HEALTH DASHBOARD ----------
st.markdown("#### 🗺️ Zone Health Dashboard")
st.caption("Generated from historical incident density — no extra data required")

try:
    zh_res = requests.get(f"{API}/zone-health", timeout=10)
    if zh_res.status_code == 200:
        zones = zh_res.json()["zones"]
        z1, z2 = st.columns(2)
        for i, z in enumerate(zones):
            col   = z1 if i % 2 == 0 else z2
            color = "#EF4444" if z["risk_score"] > 70 else "#F59E0B" if z["risk_score"] > 50 else "#22C55E"
            level = "High" if z["risk_score"] > 70 else "Moderate" if z["risk_score"] > 50 else "Low"
            trend = "▲" if z["risk_score"] > 60 else "▼" if z["risk_score"] < 40 else "▬"
            with col:
                st.markdown(f"""
                <div class="gx-zone-card">
                  <div class="gx-zone-row">
                    <span class="gx-zone-name">{z['zone']}</span>
                    <span style="color:{color}; font-weight:700; font-size:0.8rem;">{trend} {level}</span>
                  </div>
                  <div class="gx-risk-track"><div class="gx-risk-fill" style="width:{z['risk_score']}%; background:{color};"></div></div>
                  <div style="text-align:right; margin-top:4px; font-size:0.76rem; color:#94A3B8; font-family:'JetBrains Mono',monospace;">{z['risk_score']}/100</div>
                </div>
                """, unsafe_allow_html=True)
except Exception:
    st.info("Start API to see zone health data.")

st.divider()

# ---------- INCIDENT WORKFLOW TIMELINE ----------
st.markdown("#### 📋 Incident Workflow")
wf_cols = st.columns(5)

if "last_prediction" in st.session_state:
    level = st.session_state["last_prediction"]["severity"]
    wf_steps = [
        ("📥 Reported", "#22C55E"),
        (f"🔮 Predicted {level}", "#F59E0B"),
        ("📋 Resources Suggested", "#3B82F6"),
        ("✅ Response Selected", "#F59E0B"),
        ("📝 Outcome Pending", "#EF4444"),
    ]
else:
    wf_steps = [(l, "#374151") for l in ["📥 Reported", "🔮 Predicted", "📋 Resources", "✅ Response", "📝 Outcome"]]

for col, (label, color) in zip(wf_cols, wf_steps):
    col.markdown(f'<div class="gx-wf" style="border-color:{color}55; color:{color};">{label}</div>', unsafe_allow_html=True)

st.divider()

# ══════════════════════════════════════════════
# OUTCOME LOGGING SECTION (placed above AI Assistant)
# ══════════════════════════════════════════════
st.markdown('<div class="gx-section-title"><span class="dot"></span>📝 OUTCOME LOGGING</div>', unsafe_allow_html=True)
st.caption("Self-learning — outcomes improve future memory engine recommendations")

if "last_prediction" in st.session_state:
    event_id = st.session_state["last_prediction"].get("event_id")
    with st.form("outcome_form"):
        st.markdown("**Incident Outcome**")
        oc1, oc2 = st.columns(2)
        actual_severity   = oc1.selectbox("Actual Severity", ["Quick", "Moderate", "Severe"])
        actual_delay_mins = oc2.number_input("Actual Delay (minutes)", min_value=0.0, value=30.0, step=1.0)

        st.markdown("**Response Used**")
        rc1, rc2 = st.columns(2)
        plan_used         = rc1.text_input("Plan Used", value="Plan A")
        delay_reduced     = rc2.slider("Delay Reduced (%)", 0, 100, 30)

        st.markdown("**Resources Deployed**")
        dc1, dc2 = st.columns(2)
        officers          = dc1.number_input("Officers Deployed",  min_value=0, value=4)
        barricades        = dc2.number_input("Barricades Used",    min_value=0, value=2)

        st.markdown("**Notes**")
        notes             = st.text_area("Notes", label_visibility="collapsed")

        if st.form_submit_button("💾 Save Outcome", type="primary"):
            outcome_payload = {
                "event_id"          : event_id,
                "actual_severity"   : actual_severity,
                "actual_delay_mins" : float(actual_delay_mins),
                "officers_deployed" : officers,
                "barricades_used"   : barricades,
                "delay_reduced_pct" : float(delay_reduced),
                "plan_used"         : plan_used,
                "notes"             : notes,
            }
            try:
                r = requests.post(f"{API}/log-outcome", json=outcome_payload, timeout=15)
            except requests.exceptions.RequestException as ex:
                st.error(f"Could not reach API: {ex}")
                r = None

            if r is not None:
                if r.status_code == 200:
                    st.success(f"✅ Outcome saved! {r.json()['message']}")
                else:
                    st.error(f"API error {r.status_code}: {r.text}")
else:
    st.info("Run a prediction first to log its outcome.")

st.divider()

# ══════════════════════════════════════════════
# AI OPERATIONS ASSISTANT (bottom of dashboard)
# ══════════════════════════════════════════════
st.markdown('<div class="gx-section-title"><span class="dot"></span>🤖 AI OPERATIONS ASSISTANT</div>', unsafe_allow_html=True)
st.caption("Ask about this prediction, response strategy, or general traffic management guidance")

st.markdown('<div class="gx-card gx-chat-wrap">', unsafe_allow_html=True)

if not CHAT_AVAILABLE:
    st.warning(
        "AI Assistant unavailable — make sure `chat_utils.py` is in the same folder as "
        "`app.py`, and run `pip install groq`."
    )
else:
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    _chat_height = 420 if st.session_state["chat_history"] else 140
    chat_container = st.container(height=_chat_height)
    with chat_container:
        if not st.session_state["chat_history"]:
            st.markdown(
                "<div style='text-align:center; color:#94A3B8; padding:30px 0; font-size:0.95rem;'>"
                "💬 Ask the AI Operations Assistant about this prediction or general traffic guidance."
                "</div>",
                unsafe_allow_html=True
            )
        for msg in st.session_state["chat_history"]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # In-card input row (instead of st.chat_input, which Streamlit always
    # docks to the bottom of the browser viewport — that's what was causing
    # the input to look detached from the conversation above it).
    with st.form("ai_assistant_form", clear_on_submit=True, border=False):
        ic1, ic2 = st.columns([6, 1])
        user_question = ic1.text_input(
            "Ask a question",
            placeholder="Type your question here...",
            label_visibility="collapsed",
        )
        send_clicked = ic2.form_submit_button("Send", use_container_width=True)

    if send_clicked and user_question:
        st.session_state["chat_history"].append({"role": "user", "content": user_question})

        outgoing_message = user_question
        if "last_prediction" in st.session_state:
            context = format_prediction_for_chat(st.session_state["last_prediction"])
            outgoing_message = f"{context}\n\nOperator question: {user_question}"

        with st.spinner("Thinking..."):
            reply = get_chat_response(
                outgoing_message,
                st.session_state["chat_history"][:-1],
            )
        st.session_state["chat_history"].append({"role": "assistant", "content": reply})
        st.rerun()

st.markdown('</div>', unsafe_allow_html=True)
