"""
Milwaukee Bucks Player Stats Analyzer
--------------------------------------
Install:  pip install streamlit pandas numpy requests
Run:      streamlit run app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import requests
import time

# ── Page config (must be first Streamlit call) ─────────────────────────────────
st.set_page_config(
    page_title="Milwaukee Bucks Stats",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Constants ──────────────────────────────────────────────────────────────────
BUCKS_ID = 1610612749
SEASON   = "2024-25"
MIN_GP   = 10

STATS = [
    ("PTS",  "Points"),
    ("REB",  "Rebounds"),
    ("AST",  "Assists"),
    ("TOV",  "Turnovers"),
    ("STL",  "Steals"),
    ("BLK",  "Blocks"),
    ("OREB", "Off. Rebounds"),
    ("FGA",  "FG Attempted"),
    ("FG3A", "3P Attempted"),
    ("FTA",  "FT Attempted"),
]

STAT_COLS = [s[0] for s in STATS]

# ── Helpers ────────────────────────────────────────────────────────────────────
def pct_color(pct):
    """Map 1-100 percentile to a red → amber → green hex color."""
    if pct is None or (isinstance(pct, float) and np.isnan(pct)):
        return "#4b5563"
    pct = max(1, min(100, int(pct)))
    stops = [(220, 38, 38), (245, 158, 11), (16, 185, 129)]
    if pct <= 50:
        t, a, b = (pct - 1) / 49, stops[0], stops[1]
    else:
        t, a, b = (pct - 50) / 50, stops[1], stops[2]
    r = round(a[0] + t * (b[0] - a[0]))
    g = round(a[1] + t * (b[1] - a[1]))
    b_ = round(a[2] + t * (b[2] - a[2]))
    return f"#{r:02X}{g:02X}{b_:02X}"


def calc_pct(value, pool: pd.Series):
    pool = pool.dropna().astype(float)
    if pool.empty or pd.isna(value):
        return None
    return int(round((pool <= float(value)).mean() * 100))


def ordinal(n):
    if n is None:
        return "\u2014"
    n = int(n)
    m100, m10 = n % 100, n % 10
    if 11 <= m100 <= 13:
        sfx = "th"
    elif m10 == 1:
        sfx = "st"
    elif m10 == 2:
        sfx = "nd"
    elif m10 == 3:
        sfx = "rd"
    else:
        sfx = "th"
    return f"{n}{sfx}"


def photo_url(pid):
    return f"https://cdn.nba.com/headshots/nba/latest/1040x760/{pid}.png"


# ── NBA API helpers ────────────────────────────────────────────────────────────
NBA_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.nba.com",
    "Referer": "https://www.nba.com/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
}

def nba_fetch(endpoint, params, result_index=0):
    url  = f"https://stats.nba.com/stats/{endpoint}"
    resp = requests.get(url, params=params, headers=NBA_HEADERS, timeout=30)
    resp.raise_for_status()
    rs   = resp.json()["resultSets"][result_index]
    return pd.DataFrame(rs["rowSet"], columns=rs["headers"])


# ── Data loading ───────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def load_data():
    pool = nba_fetch("leaguedashplayerstats", {
        "PerMode":    "Per100Possessions",
        "Season":     SEASON,
        "SeasonType": "Regular Season",
        "LeagueID":   "00",
    })
    pool["GP"]        = pool["GP"].astype(int)
    pool              = pool[pool["GP"] >= MIN_GP].copy()
    pool["PLAYER_ID"] = pool["PLAYER_ID"].astype(str)
    for col in STAT_COLS:
        pool[col] = pd.to_numeric(pool[col], errors="coerce")

    time.sleep(0.6)  # be polite between requests

    roster = nba_fetch("commonteamroster", {
        "TeamID": BUCKS_ID,
        "Season": SEASON,
    })
    roster["PLAYER_ID"] = roster["PLAYER_ID"].astype(str)
    return pool, roster


# ── CSS injection ──────────────────────────────────────────────────────────────
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

/* ── Reset Streamlit chrome ── */
#MainMenu, footer { display: none !important; }
header[data-testid="stHeader"] { display: none !important; }
section[data-testid="stSidebar"] { display: none !important; }

html, body, [data-testid="stAppViewContainer"],
[data-testid="stAppViewBlockContainer"],
.stApp {
    background: #0a0e1a !important;
    font-family: 'Inter', -apple-system, sans-serif !important;
    color: #e6edf3 !important;
}

/* Remove all default block container padding */
.block-container,
[data-testid="stAppViewBlockContainer"],
div[data-testid="stVerticalBlock"] {
    padding: 0 !important;
    gap: 0 !important;
    max-width: 100% !important;
}

/* Tighten column gaps */
[data-testid="stColumns"] {
    gap: 20px !important;
    padding: 0 28px 40px !important;
    background: #0a0e1a !important;
    align-items: flex-start !important;
}

[data-testid="column"] {
    padding: 0 !important;
    gap: 0 !important;
}

/* Selectbox styling */
[data-testid="stSelectbox"] label {
    font-size: 0.7rem !important;
    text-transform: uppercase !important;
    letter-spacing: 1.2px !important;
    color: #6b7280 !important;
    font-weight: 700 !important;
    margin-bottom: 6px !important;
}

[data-testid="stSelectbox"] [data-baseweb="select"] {
    background-color: #1a2234 !important;
    border: 1px solid #2d3748 !important;
    border-radius: 8px !important;
}

[data-testid="stSelectbox"] [data-baseweb="select"]:focus-within {
    border-color: #00893B !important;
    box-shadow: 0 0 0 3px rgba(0,137,59,0.2) !important;
}

[data-testid="stSelectbox"] [data-baseweb="select"] * {
    color: #e6edf3 !important;
    background-color: #1a2234 !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.95rem !important;
}

/* Spinner */
[data-testid="stSpinner"] { color: #00893B !important; }

/* ── App header ── */
.app-header {
    background: linear-gradient(135deg, #003D17 0%, #00471B 40%, #00893B 100%);
    padding: 20px 36px;
    display: flex;
    align-items: center;
    gap: 20px;
    border-bottom: 3px solid #EEE1C6;
    box-shadow: 0 6px 30px rgba(0,0,0,0.6);
    margin-bottom: 0;
}

.app-header img { height: 58px; width: auto; filter: drop-shadow(0 2px 8px rgba(0,0,0,0.4)); }
.app-header h1  { font-size: 1.85rem; font-weight: 900; letter-spacing: -0.5px; color: #fff; margin: 0; line-height: 1; }
.app-header p   { font-size: 0.72rem; color: #b8d4c0; font-weight: 600; margin: 4px 0 0; letter-spacing: 1.5px; text-transform: uppercase; }

/* ── Selector bar ── */
.selector-bar {
    background: #0f1623;
    border-bottom: 1px solid #1a2234;
    padding: 18px 36px;
}

/* ── Player card ── */
.player-card {
    background: #111827;
    border: 1px solid #1a2234;
    border-radius: 16px;
    overflow: hidden;
    box-shadow: 0 4px 24px rgba(0,0,0,0.4);
}

.player-photo-bg {
    background: radial-gradient(ellipse at top, #1a2d3a 0%, #111827 70%);
    padding: 24px 20px 0;
    text-align: center;
    position: relative;
}

.player-photo-bg::after {
    content: '';
    position: absolute;
    bottom: 0; left: 0; right: 0;
    height: 30px;
    background: linear-gradient(transparent, #111827);
}

.player-photo-bg img {
    width: 200px;
    height: 150px;
    object-fit: contain;
    object-position: top center;
    display: block;
    margin: 0 auto;
    position: relative;
    z-index: 1;
}

.player-details { padding: 18px 20px 24px; }

.player-full-name {
    font-size: 1.1rem;
    font-weight: 800;
    color: #ffffff;
    line-height: 1.25;
    margin-bottom: 12px;
}

.player-chips { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 18px; }

.chip {
    background: #1a2234;
    border: 1px solid #2d3748;
    border-radius: 6px;
    padding: 5px 11px;
    font-size: 0.78rem;
    color: #9ca3af;
}

.chip strong { color: #e6edf3; font-weight: 700; }

.detail-block { margin-bottom: 14px; }

.detail-label {
    font-size: 0.65rem;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    color: #4b5563;
    font-weight: 700;
    margin-bottom: 2px;
}

.detail-value { font-size: 1rem; font-weight: 700; color: #e6edf3; }
.bucks-green  { color: #00893B !important; }
.gp-big       { font-size: 2.2rem; font-weight: 900; color: #ffffff; line-height: 1; }

/* ── Stats panel ── */
.stats-panel {
    background: #111827;
    border: 1px solid #1a2234;
    border-radius: 16px;
    overflow: hidden;
    box-shadow: 0 4px 24px rgba(0,0,0,0.4);
}

.stats-panel-hdr {
    padding: 22px 28px 18px;
    border-bottom: 1px solid #1a2234;
    background: linear-gradient(180deg, #141f2e 0%, #111827 100%);
}

.stats-panel-hdr h2 { font-size: 1.05rem; font-weight: 800; color: #fff; margin: 0; }
.stats-panel-hdr p  { font-size: 0.73rem; color: #6b7280; margin: 4px 0 0; font-weight: 500; }

.col-headers {
    display: grid;
    grid-template-columns: 155px 90px 1fr 90px;
    padding: 10px 28px;
    background: #0f1623;
    border-bottom: 1px solid #1a2234;
    gap: 12px;
}

.chdr {
    font-size: 0.62rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1.1px;
    color: #4b5563;
}

.chdr.c { text-align: center; }
.chdr.r { text-align: right; }

.stat-row {
    display: grid;
    grid-template-columns: 155px 90px 1fr 90px;
    align-items: center;
    padding: 15px 28px;
    border-bottom: 1px solid #131c2b;
    gap: 12px;
    transition: background 0.12s;
}

.stat-row:last-child { border-bottom: none; }
.stat-row:hover      { background: #141f2e; }

.stat-name { font-size: 0.88rem; font-weight: 600; color: #d1d5db; }
.stat-val  { font-size: 1.35rem; font-weight: 800; color: #fff; text-align: center; letter-spacing: -0.5px; }

.pct-bar-wrap { display: flex; align-items: center; }

.pct-track {
    flex: 1;
    height: 8px;
    background: #1a2234;
    border-radius: 4px;
    overflow: hidden;
}

.pct-fill { height: 100%; border-radius: 4px; }

.pct-pill { text-align: right; }

.pct-badge {
    display: inline-block;
    font-size: 0.78rem;
    font-weight: 800;
    color: #fff;
    padding: 4px 10px;
    border-radius: 20px;
    min-width: 52px;
    text-align: center;
}

.no-data {
    padding: 60px 24px;
    text-align: center;
    color: #4b5563;
    font-size: 0.95rem;
}
</style>
"""

st.markdown(CSS, unsafe_allow_html=True)

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="app-header">
  <img src="https://cdn.nba.com/logos/nba/1610612749/global/L/logo.svg" alt="Bucks">
  <div>
    <h1>Milwaukee Bucks</h1>
    <p>2024-25 Player Statistics</p>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Load data ──────────────────────────────────────────────────────────────────
with st.spinner("Loading 2024-25 NBA data..."):
    try:
        nba_pool, bucks_roster = load_data()
        data_ok = True
    except Exception as exc:
        st.error(f"Failed to load NBA data: {exc}")
        data_ok = False
        nba_pool, bucks_roster = pd.DataFrame(), pd.DataFrame()

# ── Build player list ──────────────────────────────────────────────────────────
if data_ok and not bucks_roster.empty and not nba_pool.empty:
    avail = (
        bucks_roster[bucks_roster["PLAYER_ID"].isin(nba_pool["PLAYER_ID"])]
        .sort_values("PLAYER")
        .reset_index(drop=True)
    )
    player_names = avail["PLAYER"].tolist()
    player_ids   = avail["PLAYER_ID"].tolist()
else:
    player_names, player_ids = [], []

# ── Selector ───────────────────────────────────────────────────────────────────
st.markdown('<div class="selector-bar">', unsafe_allow_html=True)
selected_name = st.selectbox("Player", options=player_names, index=0 if player_names else None)
st.markdown("</div>", unsafe_allow_html=True)

# ── Resolve selected player ────────────────────────────────────────────────────
if selected_name and data_ok:
    idx       = player_names.index(selected_name)
    pid       = player_ids[idx]
    info_row  = bucks_roster[bucks_roster["PLAYER_ID"] == pid].iloc[0]
    stats_row = nba_pool[nba_pool["PLAYER_ID"] == pid]
else:
    pid = info_row = stats_row = None

# ── Build player card HTML ─────────────────────────────────────────────────────
def build_player_card(info, stats):
    name = info["PLAYER"]
    num  = info.get("NUM", "")
    num  = f"#{num.strip()}" if pd.notna(num) and str(num).strip() else "\u2014"
    pos  = info.get("POSITION", "\u2014")
    pos  = pos if pd.notna(pos) and str(pos).strip() else "\u2014"
    gp   = int(stats["GP"].iloc[0]) if not stats.empty else None
    img  = photo_url(info["PLAYER_ID"])

    gp_html = ""
    if gp is not None:
        gp_html = f"""
        <div class="detail-block">
          <div class="detail-label">Games Played</div>
          <div class="gp-big">{gp}</div>
        </div>"""

    return f"""
<div class="player-card">
  <div class="player-photo-bg">
    <img src="{img}" alt="{name}"
         onerror="this.onerror=null;this.style.opacity='0.3';">
  </div>
  <div class="player-details">
    <div class="player-full-name">{name}</div>
    <div class="player-chips">
      <div class="chip">No.&nbsp;<strong>{num}</strong></div>
      <div class="chip"><strong>{pos}</strong></div>
    </div>
    <div class="detail-block">
      <div class="detail-label">Team</div>
      <div class="detail-value bucks-green">Milwaukee Bucks</div>
    </div>
    {gp_html}
  </div>
</div>"""


# ── Build stats panel HTML ─────────────────────────────────────────────────────
def build_stats_panel(stats):
    if stats.empty:
        return '<div class="stats-panel"><div class="no-data">No stats available.</div></div>'

    row = stats.iloc[0]
    rows_html = ""
    for col, label in STATS:
        v100  = row[col]
        v75   = round(float(v100) * 0.75, 1) if pd.notna(v100) else None
        pct   = calc_pct(v100, nba_pool[col])
        color = pct_color(pct)
        ord_s = ordinal(pct)
        pct_w = max(1, pct or 1)
        val_s = f"{v75:.1f}" if v75 is not None else "\u2014"

        rows_html += f"""
<div class="stat-row">
  <div class="stat-name">{label}</div>
  <div class="stat-val">{val_s}</div>
  <div class="pct-bar-wrap">
    <div class="pct-track">
      <div class="pct-fill" style="width:{pct_w}%;background:{color}"></div>
    </div>
  </div>
  <div class="pct-pill">
    <span class="pct-badge" style="background:{color}">{ord_s}</span>
  </div>
</div>"""

    return f"""
<div class="stats-panel">
  <div class="stats-panel-hdr">
    <h2>Per 75 Possessions</h2>
    <p>Percentile vs. all NBA players ({MIN_GP}+ GP) &bull; 2024-25 Regular Season</p>
  </div>
  <div class="col-headers">
    <div class="chdr">Stat</div>
    <div class="chdr c">Per 75</div>
    <div class="chdr">Percentile</div>
    <div class="chdr r">Rank</div>
  </div>
  {rows_html}
</div>"""


# ── Render columns ─────────────────────────────────────────────────────────────
if pid and info_row is not None and not isinstance(stats_row, type(None)):
    left, right = st.columns([1, 2.5], gap="medium")
    with left:
        st.markdown(build_player_card(info_row, stats_row), unsafe_allow_html=True)
    with right:
        st.markdown(build_stats_panel(stats_row), unsafe_allow_html=True)
elif not data_ok:
    st.warning("Could not load NBA data. Check your internet connection and try again.")
else:
    st.info("Select a player from the dropdown above.")
