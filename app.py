"""
Milwaukee Bucks Player Stats Analyzer
--------------------------------------
Install:  pip install streamlit pandas numpy requests
Run:      streamlit run app.py

Streamlit Cloud: add your free balldontlie key under Settings → Secrets:
  BALLDONTLIE_KEY = "your_key_here"
Get a free key at https://www.balldontlie.io/
"""

import streamlit as st
import pandas as pd
import numpy as np
import requests
import time

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Milwaukee Bucks Stats",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Constants ──────────────────────────────────────────────────────────────────
BUCKS_NAME  = "Milwaukee Bucks"
SEASON_YEAR = 2024          # balldontlie uses the start year: 2024-25 → 2024
MIN_GP      = 10
BDL_BASE    = "https://api.balldontlie.io/v1"

# balldontlie field names map to what we display
STATS = [
    ("pts",      "Points"),
    ("reb",      "Rebounds"),
    ("ast",      "Assists"),
    ("turnover", "Turnovers"),
    ("stl",      "Steals"),
    ("blk",      "Blocks"),
    ("oreb",     "Off. Rebounds"),
    ("fga",      "FG Attempted"),
    ("fg3a",     "3P Attempted"),
    ("fta",      "FT Attempted"),
]
STAT_COLS = [s[0] for s in STATS]

# ── Helpers ────────────────────────────────────────────────────────────────────
def pct_color(pct):
    if pct is None or (isinstance(pct, float) and np.isnan(pct)):
        return "#4b5563"
    pct = max(1, min(100, int(pct)))
    stops = [(220, 38, 38), (245, 158, 11), (16, 185, 129)]
    if pct <= 50:
        t, a, b = (pct - 1) / 49, stops[0], stops[1]
    else:
        t, a, b = (pct - 50) / 50, stops[1], stops[2]
    r  = round(a[0] + t * (b[0] - a[0]))
    g  = round(a[1] + t * (b[1] - a[1]))
    b_ = round(a[2] + t * (b[2] - a[2]))
    return f"#{r:02X}{g:02X}{b_:02X}"


def calc_pct(value, pool: pd.Series):
    pool = pool.dropna().astype(float)
    if pool.empty or pd.isna(value):
        return None
    return int(round((pool <= float(value)).mean() * 100))


def ordinal(n):
    if n is None:
        return "—"
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


def initials(name: str) -> str:
    parts = name.split()
    return "".join(p[0].upper() for p in parts if p)[:2]


# ── balldontlie API helpers ────────────────────────────────────────────────────
def bdl_get(path, params, api_key):
    resp = requests.get(
        f"{BDL_BASE}{path}",
        headers={"Authorization": api_key},
        params=params,
        timeout=25,
    )
    resp.raise_for_status()
    return resp.json()


def bdl_paginate(path, params, api_key):
    """Collect every page from a cursor-paginated endpoint."""
    items, cursor = [], None
    while True:
        p = {"per_page": 100, **params}
        if cursor:
            p["cursor"] = cursor
        data = bdl_get(path, p, api_key)
        items.extend(data["data"])
        cursor = data.get("meta", {}).get("next_cursor")
        if not cursor:
            break
        time.sleep(0.2)
    return items


# ── Data loading ───────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def load_data(api_key: str):
    # 1. Find Milwaukee Bucks team ID
    teams   = bdl_get("/teams", {"per_page": 30}, api_key)["data"]
    bucks   = next(t for t in teams if BUCKS_NAME in t["full_name"])
    bucks_id = bucks["id"]

    # 2. Bucks roster
    bucks_players = bdl_paginate("/players", {"team_ids[]": bucks_id}, api_key)
    bucks_ids     = {str(p["id"]) for p in bucks_players}

    # 3. All NBA players (needed for league-wide percentile pool)
    all_players = bdl_paginate("/players", {}, api_key)
    all_ids     = [str(p["id"]) for p in all_players]

    # 4. Season averages — fetch in batches of 50 to stay within URL limits
    all_avgs = []
    for i in range(0, len(all_ids), 50):
        batch  = all_ids[i : i + 50]
        params = [("season", SEASON_YEAR)] + [("player_ids[]", pid) for pid in batch]
        resp   = requests.get(
            f"{BDL_BASE}/season_averages",
            headers={"Authorization": api_key},
            params=params,
            timeout=25,
        )
        if resp.ok:
            all_avgs.extend(resp.json()["data"])
        time.sleep(0.25)

    if not all_avgs:
        raise RuntimeError("No season averages returned from balldontlie")

    # 5. Build pool DataFrame
    pool = pd.DataFrame(all_avgs)
    pool["player_id"]    = pool["player_id"].astype(str)
    pool["min"]          = pd.to_numeric(pool["min"],          errors="coerce")
    pool["games_played"] = pd.to_numeric(pool["games_played"], errors="coerce").fillna(0).astype(int)

    for col in STAT_COLS:
        if col not in pool.columns:
            pool[col] = np.nan
        pool[col] = pd.to_numeric(pool[col], errors="coerce")
        # Per-36 min ≈ per-75 possessions at NBA average pace (~100 poss / 48 min)
        pool[f"{col}_p36"] = (pool[col] / pool["min"].replace(0, np.nan) * 36).round(1)

    pool = pool[pool["games_played"] >= MIN_GP].copy()

    # 6. Merge player info (name, position, jersey number)
    pinfo = pd.DataFrame(all_players)
    pinfo["id"] = pinfo["id"].astype(str)
    keep  = ["id", "first_name", "last_name", "position"]
    if "jersey_number" in pinfo.columns:
        keep.append("jersey_number")

    pool = pool.merge(
        pinfo[keep].rename(columns={"id": "player_id"}),
        on="player_id", how="left",
    )
    pool["full_name"] = (
        pool["first_name"].fillna("") + " " + pool["last_name"].fillna("")
    ).str.strip()

    bucks_pool = pool[pool["player_id"].isin(bucks_ids)].sort_values("full_name")
    return pool, bucks_pool


# ── CSS ────────────────────────────────────────────────────────────────────────
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

#MainMenu, footer { display: none !important; }
header[data-testid="stHeader"] { display: none !important; }
section[data-testid="stSidebar"] { display: none !important; }

html, body, [data-testid="stAppViewContainer"],
[data-testid="stAppViewBlockContainer"], .stApp {
    background: #0a0e1a !important;
    font-family: 'Inter', -apple-system, sans-serif !important;
    color: #e6edf3 !important;
}

.block-container,
[data-testid="stAppViewBlockContainer"],
div[data-testid="stVerticalBlock"] {
    padding: 0 !important;
    gap: 0 !important;
    max-width: 100% !important;
}

[data-testid="stColumns"] {
    gap: 20px !important;
    padding: 0 28px 40px !important;
    background: #0a0e1a !important;
    align-items: flex-start !important;
}

[data-testid="column"] { padding: 0 !important; gap: 0 !important; }

/* Selectbox */
[data-testid="stSelectbox"] label {
    font-size: 0.7rem !important;
    text-transform: uppercase !important;
    letter-spacing: 1.2px !important;
    color: #6b7280 !important;
    font-weight: 700 !important;
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

/* ── Header ── */
.app-header {
    background: linear-gradient(135deg, #003D17 0%, #00471B 40%, #00893B 100%);
    padding: 20px 36px;
    display: flex;
    align-items: center;
    gap: 20px;
    border-bottom: 3px solid #EEE1C6;
    box-shadow: 0 6px 30px rgba(0,0,0,0.6);
}
.app-header img { height: 58px; filter: drop-shadow(0 2px 8px rgba(0,0,0,0.4)); }
.app-header h1  { font-size: 1.85rem; font-weight: 900; letter-spacing: -0.5px; color: #fff; margin: 0; }
.app-header p   { font-size: 0.72rem; color: #b8d4c0; font-weight: 600; margin: 4px 0 0; letter-spacing: 1.5px; text-transform: uppercase; }

/* ── Selector bar ── */
.selector-bar { background: #0f1623; border-bottom: 1px solid #1a2234; padding: 18px 36px; }

/* ── Player card ── */
.player-card {
    background: #111827;
    border: 1px solid #1a2234;
    border-radius: 16px;
    overflow: hidden;
    box-shadow: 0 4px 24px rgba(0,0,0,0.4);
}

.player-avatar {
    background: linear-gradient(135deg, #003D17 0%, #00471B 50%, #005C24 100%);
    height: 160px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-bottom: 1px solid rgba(238,225,198,0.15);
}

.player-initials {
    font-size: 4.5rem;
    font-weight: 900;
    color: rgba(255,255,255,0.75);
    letter-spacing: -3px;
    text-shadow: 0 3px 12px rgba(0,0,0,0.4);
    font-family: 'Inter', sans-serif;
}

.player-details { padding: 18px 20px 24px; }
.player-full-name { font-size: 1.1rem; font-weight: 800; color: #fff; line-height: 1.25; margin-bottom: 12px; }

.player-chips { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 18px; }
.chip { background: #1a2234; border: 1px solid #2d3748; border-radius: 6px; padding: 5px 11px; font-size: 0.78rem; color: #9ca3af; }
.chip strong { color: #e6edf3; font-weight: 700; }

.detail-block { margin-bottom: 14px; }
.detail-label { font-size: 0.65rem; text-transform: uppercase; letter-spacing: 1.2px; color: #4b5563; font-weight: 700; margin-bottom: 2px; }
.detail-value { font-size: 1rem; font-weight: 700; color: #e6edf3; }
.bucks-green  { color: #00893B !important; }
.gp-big       { font-size: 2.2rem; font-weight: 900; color: #fff; line-height: 1; }

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
.stats-panel-hdr p  { font-size: 0.73rem; color: #6b7280; margin: 4px 0 0; }

.col-headers {
    display: grid;
    grid-template-columns: 155px 90px 1fr 90px;
    padding: 10px 28px;
    background: #0f1623;
    border-bottom: 1px solid #1a2234;
    gap: 12px;
}
.chdr { font-size: 0.62rem; font-weight: 700; text-transform: uppercase; letter-spacing: 1.1px; color: #4b5563; }
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
.pct-track { flex: 1; height: 8px; background: #1a2234; border-radius: 4px; overflow: hidden; }
.pct-fill  { height: 100%; border-radius: 4px; }
.pct-pill  { text-align: right; }
.pct-badge { display: inline-block; font-size: 0.78rem; font-weight: 800; color: #fff; padding: 4px 10px; border-radius: 20px; min-width: 52px; text-align: center; }

.no-data { padding: 60px 24px; text-align: center; color: #4b5563; font-size: 0.95rem; }
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

# ── API key ─────────────────────────────────────────────────────────────────────
try:
    api_key = st.secrets["BALLDONTLIE_KEY"]
except KeyError:
    st.error(
        "**API key not found.** "
        "Go to your Streamlit Cloud app → Settings → Secrets and add:\n\n"
        "```\nBALLDONTLIE_KEY = \"your_key_here\"\n```\n\n"
        "Get a free key at https://www.balldontlie.io/"
    )
    st.stop()

# ── Load data ──────────────────────────────────────────────────────────────────
with st.spinner("Loading 2024-25 NBA data..."):
    try:
        nba_pool, bucks_pool = load_data(api_key)
        data_ok = True
    except Exception as exc:
        st.error(f"Failed to load NBA data: {exc}")
        data_ok = False
        nba_pool = bucks_pool = pd.DataFrame()

# ── Player selector ────────────────────────────────────────────────────────────
st.markdown('<div class="selector-bar">', unsafe_allow_html=True)

player_names = bucks_pool["full_name"].tolist() if data_ok and not bucks_pool.empty else []
selected     = st.selectbox("Player", options=player_names,
                            index=0 if player_names else None)

st.markdown("</div>", unsafe_allow_html=True)

# ── Resolve selected row ────────────────────────────────────────────────────────
if selected and data_ok:
    row = bucks_pool[bucks_pool["full_name"] == selected].iloc[0]
else:
    row = None


# ── Build player card ──────────────────────────────────────────────────────────
def build_player_card(r):
    name = r["full_name"]
    num  = r.get("jersey_number", None)
    num  = f"#{num}" if pd.notna(num) and str(num).strip() else "—"
    pos  = r.get("position", "—")
    pos  = pos if pd.notna(pos) and str(pos).strip() else "—"
    gp   = int(r["games_played"]) if pd.notna(r["games_played"]) else "—"
    inits = initials(name)

    return f"""
<div class="player-card">
  <div class="player-avatar">
    <span class="player-initials">{inits}</span>
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
    <div class="detail-block">
      <div class="detail-label">Games Played</div>
      <div class="gp-big">{gp}</div>
    </div>
  </div>
</div>"""


# ── Build stats panel ──────────────────────────────────────────────────────────
def build_stats_panel(r):
    rows_html = ""
    for col, label in STATS:
        p36_col = f"{col}_p36"
        val     = r[p36_col] if p36_col in r.index and pd.notna(r[p36_col]) else None
        pct     = calc_pct(r[col], nba_pool[col]) if col in nba_pool.columns else None
        color   = pct_color(pct)
        ord_s   = ordinal(pct)
        pct_w   = max(1, pct or 1)
        val_s   = f"{val:.1f}" if val is not None else "—"

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
    <h2>Per 36 Minutes</h2>
    <p>Equivalent to per-75 possessions at NBA average pace &bull;
       Percentile vs. all NBA players ({MIN_GP}+ GP) &bull; 2024-25 Regular Season</p>
  </div>
  <div class="col-headers">
    <div class="chdr">Stat</div>
    <div class="chdr c">Per 36</div>
    <div class="chdr">Percentile</div>
    <div class="chdr r">Rank</div>
  </div>
  {rows_html}
</div>"""


# ── Render ─────────────────────────────────────────────────────────────────────
if row is not None:
    left, right = st.columns([1, 2.5], gap="medium")
    with left:
        st.markdown(build_player_card(row), unsafe_allow_html=True)
    with right:
        st.markdown(build_stats_panel(row), unsafe_allow_html=True)
elif not data_ok:
    st.warning("Could not load NBA data. Check your API key and try again.")
else:
    st.info("Select a player from the dropdown above.")
