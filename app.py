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

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Milwaukee Bucks Stats",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Constants ──────────────────────────────────────────────────────────────────
BUCKS_ESPN_ID  = "15"
SEASON         = "2025"   # ESPN uses end year: 2024-25 → 2025
MIN_GP         = 10

ESPN_STATS_URL = "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/statistics/byathlete"

ESPN_HDRS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer":         "https://www.espn.com/nba/stats/",
    "Origin":          "https://www.espn.com",
}

# Multiple candidate ESPN stat names for each internal key (API uses different
# names depending on the category context returned)
STAT_CANDIDATES = {
    "pts":  ["avgPoints"],
    "reb":  ["avgRebounds", "avgTotalRebounds"],
    "ast":  ["avgAssists"],
    "tov":  ["avgTurnovers"],
    "stl":  ["avgSteals"],
    "blk":  ["avgBlocksPerGame", "avgBlocks"],
    "oreb": ["avgOffensiveRebounds"],
    "fga":  ["avgFieldGoalAttempts"],
    "fg3a": ["avgThreePointFieldGoalAttempts", "avgThreePointerAttempts"],
    "fta":  ["avgFreeThrowAttempts"],
    "min":  ["avgMinutes"],
    "gp":   ["gamesPlayed"],
}

STATS = [
    ("pts",  "Points"),
    ("reb",  "Rebounds"),
    ("ast",  "Assists"),
    ("tov",  "Turnovers"),
    ("stl",  "Steals"),
    ("blk",  "Blocks"),
    ("oreb", "Off. Rebounds"),
    ("fga",  "FG Attempted"),
    ("fg3a", "3P Attempted"),
    ("fta",  "FT Attempted"),
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


def safe_float(val):
    try:
        return float(val)
    except (TypeError, ValueError):
        return np.nan


# ── Data loading ───────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def load_data():
    # ── 1. All NBA player stats (single request) ───────────────────────────────
    s = requests.get(
        ESPN_STATS_URL,
        params={
            "region": "us", "lang": "en", "contentorigin": "espn",
            "limit": "500", "season": SEASON, "seasontype": "2",
        },
        headers=ESPN_HDRS,
        timeout=20,
    )
    s.raise_for_status()
    sdata = s.json()

    # ── 2. Build flat header list from top-level categories ───────────────────
    # ESPN uses a parallel-array format: statistics[] lines up with the
    # flattened list of stats across all categories
    flat_headers = []
    for cat in sdata.get("categories", []):
        for stat in cat.get("stats", []):
            flat_headers.append(stat.get("name", ""))

    # ── 3. Parse each athlete entry ────────────────────────────────────────────
    records = []
    for entry in sdata.get("athletes", []):
        ath   = entry.get("athlete", {})
        stats = entry.get("statistics", [])

        stat_dict = {}
        if isinstance(stats, list) and flat_headers:
            # Flat parallel array (most common ESPN format)
            for i, val in enumerate(stats):
                if i < len(flat_headers) and flat_headers[i]:
                    stat_dict[flat_headers[i]] = safe_float(val)
        elif isinstance(stats, dict):
            # Nested splits.categories format (fallback)
            for cat in stats.get("splits", {}).get("categories", []):
                for st in cat.get("stats", []):
                    stat_dict[st["name"]] = safe_float(st.get("value"))

        espn_id  = str(ath.get("id", ""))
        headshot = ath.get("headshot", {})
        hs_url   = (
            headshot.get("href")
            if isinstance(headshot, dict)
            else f"https://a.espncdn.com/i/headshots/nba/players/full/{espn_id}.png"
        )

        records.append({
            "espn_id":  espn_id,
            "name":     ath.get("displayName", ""),
            "jersey":   ath.get("jersey", ""),
            "position": ath.get("position", {}).get("abbreviation", ""),
            "team_id":  str(ath.get("team", {}).get("id", "")),
            "headshot": hs_url,
            **stat_dict,
        })

    pool = pd.DataFrame(records)
    if pool.empty:
        raise RuntimeError("ESPN stats endpoint returned no athlete data")

    # ── 4. Map ESPN stat names → internal keys ─────────────────────────────────
    available = set(pool.columns)
    for key, candidates in STAT_CANDIDATES.items():
        src = next((c for c in candidates if c in available), None)
        pool[key] = pd.to_numeric(pool[src], errors="coerce") if src else np.nan

    pool["gp"]  = pool["gp"].fillna(0).astype(int)
    pool["min"] = pd.to_numeric(pool["min"], errors="coerce")
    pool        = pool[pool["gp"] >= MIN_GP].copy()

    for col in STAT_COLS:
        pool[f"{col}_p36"] = (pool[col] / pool["min"].replace(0, np.nan) * 36).round(1)

    # ── 5. Bucks subset — filter by team_id already present in stats data ──────
    # The stats response includes team_id per player; no separate roster call needed.
    bucks_pool = (
        pool[pool["team_id"] == BUCKS_ESPN_ID]
        .sort_values("name")
        .reset_index(drop=True)
    )

    return pool, bucks_pool
        .reset_index(drop=True)
    )

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
    padding: 0 !important; gap: 0 !important; max-width: 100% !important;
}

[data-testid="stColumns"] {
    gap: 20px !important;
    padding: 0 28px 40px !important;
    background: #0a0e1a !important;
    align-items: flex-start !important;
}

[data-testid="column"] { padding: 0 !important; gap: 0 !important; }

[data-testid="stSelectbox"] label {
    font-size: 0.7rem !important; text-transform: uppercase !important;
    letter-spacing: 1.2px !important; color: #6b7280 !important; font-weight: 700 !important;
}
[data-testid="stSelectbox"] [data-baseweb="select"] {
    background-color: #1a2234 !important; border: 1px solid #2d3748 !important; border-radius: 8px !important;
}
[data-testid="stSelectbox"] [data-baseweb="select"]:focus-within {
    border-color: #00893B !important; box-shadow: 0 0 0 3px rgba(0,137,59,0.2) !important;
}
[data-testid="stSelectbox"] [data-baseweb="select"] * {
    color: #e6edf3 !important; background-color: #1a2234 !important;
    font-family: 'Inter', sans-serif !important; font-weight: 600 !important; font-size: 0.95rem !important;
}

/* ── Header ── */
.app-header {
    background: linear-gradient(135deg, #003D17 0%, #00471B 40%, #00893B 100%);
    padding: 20px 36px; display: flex; align-items: center; gap: 20px;
    border-bottom: 3px solid #EEE1C6; box-shadow: 0 6px 30px rgba(0,0,0,0.6);
}
.app-header img { height: 58px; filter: drop-shadow(0 2px 8px rgba(0,0,0,0.4)); }
.app-header h1  { font-size: 1.85rem; font-weight: 900; letter-spacing: -0.5px; color: #fff; margin: 0; }
.app-header p   { font-size: 0.72rem; color: #b8d4c0; font-weight: 600; margin: 4px 0 0; letter-spacing: 1.5px; text-transform: uppercase; }

/* ── Selector bar ── */
.selector-bar { background: #0f1623; border-bottom: 1px solid #1a2234; padding: 18px 36px; }

/* ── Player card ── */
.player-card {
    background: #111827; border: 1px solid #1a2234;
    border-radius: 16px; overflow: hidden; box-shadow: 0 4px 24px rgba(0,0,0,0.4);
}

.player-photo-bg {
    background: radial-gradient(ellipse at top, #1a2d3a 0%, #111827 70%);
    padding: 24px 20px 0; text-align: center; position: relative;
}
.player-photo-bg::after {
    content: ''; position: absolute; bottom: 0; left: 0; right: 0;
    height: 30px; background: linear-gradient(transparent, #111827);
}
.player-photo-bg img {
    width: 200px; height: 150px; object-fit: contain; object-position: top center;
    display: block; margin: 0 auto; position: relative; z-index: 1;
}

.player-avatar {
    background: linear-gradient(135deg, #003D17 0%, #00471B 50%, #005C24 100%);
    height: 160px; display: flex; align-items: center; justify-content: center;
    border-bottom: 1px solid rgba(238,225,198,0.15);
}
.player-initials {
    font-size: 4.5rem; font-weight: 900; color: rgba(255,255,255,0.75);
    letter-spacing: -3px; text-shadow: 0 3px 12px rgba(0,0,0,0.4);
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
    background: #111827; border: 1px solid #1a2234;
    border-radius: 16px; overflow: hidden; box-shadow: 0 4px 24px rgba(0,0,0,0.4);
}
.stats-panel-hdr {
    padding: 22px 28px 18px; border-bottom: 1px solid #1a2234;
    background: linear-gradient(180deg, #141f2e 0%, #111827 100%);
}
.stats-panel-hdr h2 { font-size: 1.05rem; font-weight: 800; color: #fff; margin: 0; }
.stats-panel-hdr p  { font-size: 0.73rem; color: #6b7280; margin: 4px 0 0; }

.col-headers {
    display: grid; grid-template-columns: 155px 90px 1fr 90px;
    padding: 10px 28px; background: #0f1623; border-bottom: 1px solid #1a2234; gap: 12px;
}
.chdr { font-size: 0.62rem; font-weight: 700; text-transform: uppercase; letter-spacing: 1.1px; color: #4b5563; }
.chdr.c { text-align: center; }
.chdr.r { text-align: right; }

.stat-row {
    display: grid; grid-template-columns: 155px 90px 1fr 90px;
    align-items: center; padding: 15px 28px; border-bottom: 1px solid #131c2b;
    gap: 12px; transition: background 0.12s;
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

# ── Load data ──────────────────────────────────────────────────────────────────
with st.spinner("Loading 2024-25 NBA data..."):
    try:
        nba_pool, bucks_pool = load_data()
        data_ok = True
    except Exception as exc:
        st.error(f"Failed to load NBA data: {exc}")
        data_ok = False
        nba_pool = bucks_pool = pd.DataFrame()

# ── Player selector ────────────────────────────────────────────────────────────
st.markdown('<div class="selector-bar">', unsafe_allow_html=True)

player_names = bucks_pool["name"].tolist() if data_ok and not bucks_pool.empty else []
selected     = st.selectbox("Player", options=player_names,
                            index=0 if player_names else None)

st.markdown("</div>", unsafe_allow_html=True)

# ── Resolve selected player ────────────────────────────────────────────────────
if selected and data_ok:
    row = bucks_pool[bucks_pool["name"] == selected].iloc[0]
else:
    row = None


# ── Build player card ──────────────────────────────────────────────────────────
def build_player_card(r):
    name     = r["name"]
    num      = str(r.get("jersey", "")).strip()
    num      = f"#{num}" if num else "—"
    pos      = str(r.get("position", "")).strip() or "—"
    gp       = int(r["gp"]) if pd.notna(r["gp"]) else "—"
    hs_url   = r.get("headshot", "")
    inits    = initials(name)

    # Show ESPN headshot; fall back to initials avatar on load error
    if hs_url:
        photo = f"""
  <div class="player-photo-bg">
    <img src="{hs_url}" alt="{name}"
         onerror="this.parentElement.outerHTML='<div class=player-avatar><span class=player-initials>{inits}</span></div>'">
  </div>"""
    else:
        photo = f"""
  <div class="player-avatar">
    <span class="player-initials">{inits}</span>
  </div>"""

    return f"""
<div class="player-card">
  {photo}
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
    st.warning("Could not load NBA data. Check your internet connection and try again.")
else:
    st.info("Select a player from the dropdown above.")
