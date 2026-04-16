# Milwaukee Bucks Player Stats Analyzer
# Requires: shiny, hoopR, dplyr
# Install:  install.packages(c("shiny","dplyr"))
#           remotes::install_github("sportsdataverse/hoopR")

suppressPackageStartupMessages({
  library(shiny)
  library(hoopR)
  library(dplyr)
})

# ── Constants ──────────────────────────────────────────────────────────────────
BUCKS_ID <- "1610612749"
SEASON   <- "2024-25"
MIN_GP   <- 10   # minimum games played to be included in percentile pool

STAT_DEFS <- list(
  list(col = "PTS",  label = "Points"),
  list(col = "REB",  label = "Rebounds"),
  list(col = "AST",  label = "Assists"),
  list(col = "TOV",  label = "Turnovers"),
  list(col = "STL",  label = "Steals"),
  list(col = "BLK",  label = "Blocks"),
  list(col = "OREB", label = "Off. Rebounds"),
  list(col = "FGA",  label = "FG Attempted"),
  list(col = "FG3A", label = "3P Attempted"),
  list(col = "FTA",  label = "FT Attempted")
)

STAT_COLS <- sapply(STAT_DEFS, `[[`, "col")

# ── Helpers ────────────────────────────────────────────────────────────────────
calc_pct <- function(val, pool) {
  pool <- suppressWarnings(as.numeric(pool[!is.na(pool)]))
  v    <- suppressWarnings(as.numeric(val))
  if (!length(pool) || is.na(v)) return(NA_integer_)
  as.integer(round(mean(pool <= v) * 100))
}

pct_col <- function(p) {
  if (is.na(p)) return("#4b5563")
  p <- max(1L, min(100L, as.integer(p)))
  stops <- list(c(220, 38, 38), c(245, 158, 11), c(16, 185, 129))
  if (p <= 50) {
    t <- (p - 1) / 49; a <- stops[[1]]; b <- stops[[2]]
  } else {
    t <- (p - 50) / 50; a <- stops[[2]]; b <- stops[[3]]
  }
  sprintf("#%02X%02X%02X",
    round(a[1] + t * (b[1] - a[1])),
    round(a[2] + t * (b[2] - a[2])),
    round(a[3] + t * (b[3] - a[3])))
}

ordinal <- function(n) {
  if (is.na(n)) return("\u2014")
  n    <- as.integer(n)
  m100 <- n %% 100
  m10  <- n %% 10
  sfx  <- if (m100 %in% 11:13) "th"
           else if (m10 == 1)  "st"
           else if (m10 == 2)  "nd"
           else if (m10 == 3)  "rd"
           else                "th"
  paste0(n, sfx)
}

photo_url <- function(pid) {
  sprintf("https://cdn.nba.com/headshots/nba/latest/1040x760/%s.png", pid)
}

safe_pct <- function(p) if (is.na(p)) 1L else max(1L, min(100L, as.integer(p)))

# ── Load data at startup ───────────────────────────────────────────────────────
message("[bucks-app] Fetching NBA stats for ", SEASON, " ...")

nba_pool <- tryCatch({
  nba_leaguedashplayerstats(
    season               = SEASON,
    per_mode_simple      = "Per100Possessions",
    season_type_all_star = "Regular Season"
  )$LeagueDashPlayerStats |>
    mutate(
      GP        = as.integer(GP),
      PLAYER_ID = as.character(PLAYER_ID)
    ) |>
    filter(GP >= MIN_GP) |>
    mutate(across(all_of(STAT_COLS), as.numeric))
}, error = function(e) {
  message("[bucks-app] Stats API error: ", e$message)
  NULL
})

bucks_roster <- tryCatch({
  nba_commonteamroster(
    team_id = BUCKS_ID,
    season  = SEASON
  )$CommonTeamRoster |>
    transmute(
      PLAYER_NAME = PLAYER,
      PLAYER_ID   = as.character(PLAYER_ID),
      NUM         = NUM,
      POSITION    = POSITION
    )
}, error = function(e) {
  message("[bucks-app] Roster API error: ", e$message)
  NULL
})

message("[bucks-app] NBA pool: ", nrow(nba_pool), " | Bucks roster: ", nrow(bucks_roster))

# Choices: Bucks players who appear in the stats pool
if (!is.null(bucks_roster) && !is.null(nba_pool)) {
  avail   <- bucks_roster |> semi_join(nba_pool, by = "PLAYER_ID") |> arrange(PLAYER_NAME)
  choices <- setNames(avail$PLAYER_ID, avail$PLAYER_NAME)
} else if (!is.null(bucks_roster)) {
  avail   <- bucks_roster |> arrange(PLAYER_NAME)
  choices <- setNames(avail$PLAYER_ID, avail$PLAYER_NAME)
} else {
  avail   <- data.frame()
  choices <- c("Data unavailable" = "")
}

# ── CSS ────────────────────────────────────────────────────────────────────────
APP_CSS <- "
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html, body, .container-fluid {
  background: #0a0e1a;
  color: #e6edf3;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  min-height: 100vh;
  padding: 0 !important;
}

/* ── Header ─────────────────────────────────────────────────── */
.app-header {
  background: linear-gradient(135deg, #003D17 0%, #00471B 40%, #00893B 100%);
  padding: 20px 36px;
  display: flex;
  align-items: center;
  gap: 20px;
  border-bottom: 3px solid #EEE1C6;
  box-shadow: 0 6px 30px rgba(0,0,0,0.6);
}

.app-header .bucks-logo {
  height: 58px;
  width: auto;
  filter: drop-shadow(0 2px 8px rgba(0,0,0,0.4));
}

.app-header-text h1 {
  font-size: 1.85rem;
  font-weight: 900;
  letter-spacing: -0.5px;
  color: #ffffff;
  line-height: 1;
}

.app-header-text p {
  font-size: 0.72rem;
  color: #b8d4c0;
  font-weight: 600;
  margin-top: 4px;
  letter-spacing: 1.5px;
  text-transform: uppercase;
}

/* ── Selector bar ───────────────────────────────────────────── */
.selector-bar {
  background: #0f1623;
  border-bottom: 1px solid #1a2234;
  padding: 18px 36px;
  display: flex;
  align-items: center;
  gap: 16px;
}

.selector-bar .select-label {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 1.2px;
  color: #6b7280;
  font-weight: 700;
  white-space: nowrap;
}

.selector-bar .form-group { margin: 0; }

.selector-bar select {
  background: #1a2234;
  border: 1px solid #2d3748;
  color: #e6edf3;
  padding: 10px 16px;
  border-radius: 8px;
  font-size: 0.95rem;
  font-family: inherit;
  font-weight: 600;
  min-width: 340px;
  cursor: pointer;
  outline: none;
  appearance: none;
  -webkit-appearance: none;
  background-image: url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8'%3E%3Cpath d='M1 1l5 5 5-5' stroke='%236b7280' stroke-width='1.5' fill='none' stroke-linecap='round'/%3E%3C/svg%3E\");
  background-repeat: no-repeat;
  background-position: right 14px center;
  padding-right: 36px;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.selector-bar select:focus {
  border-color: #00893B;
  box-shadow: 0 0 0 3px rgba(0,137,59,0.15);
}

.selector-bar select option { background: #1a2234; }

/* ── Main layout ────────────────────────────────────────────── */
.main-content {
  display: flex;
  gap: 28px;
  padding: 28px 36px 40px;
  align-items: flex-start;
}

/* ── Player card ────────────────────────────────────────────── */
.player-card {
  width: 240px;
  flex-shrink: 0;
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
  width: 180px;
  height: 135px;
  object-fit: contain;
  object-position: top center;
  display: block;
  margin: 0 auto;
  position: relative;
  z-index: 1;
}

.player-details {
  padding: 18px 20px 24px;
}

.player-full-name {
  font-size: 1.05rem;
  font-weight: 800;
  color: #ffffff;
  line-height: 1.25;
  margin-bottom: 12px;
}

.player-chips {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 18px;
}

.chip {
  background: #1a2234;
  border: 1px solid #2d3748;
  border-radius: 6px;
  padding: 5px 11px;
  font-size: 0.78rem;
  color: #9ca3af;
}

.chip strong {
  color: #e6edf3;
  font-weight: 700;
}

.detail-block {
  margin-bottom: 14px;
}

.detail-block-label {
  font-size: 0.65rem;
  text-transform: uppercase;
  letter-spacing: 1.2px;
  color: #4b5563;
  font-weight: 700;
  margin-bottom: 2px;
}

.detail-block-value {
  font-size: 1rem;
  font-weight: 700;
  color: #e6edf3;
}

.bucks-green { color: #00893B !important; }

.gp-big {
  font-size: 2rem;
  font-weight: 900;
  color: #ffffff;
  line-height: 1;
}

/* ── Stats panel ────────────────────────────────────────────── */
.stats-panel {
  flex: 1;
  background: #111827;
  border: 1px solid #1a2234;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 4px 24px rgba(0,0,0,0.4);
  min-width: 0;
}

.stats-panel-header {
  padding: 22px 28px 18px;
  border-bottom: 1px solid #1a2234;
  background: linear-gradient(180deg, #141f2e 0%, #111827 100%);
}

.stats-panel-header h2 {
  font-size: 1.05rem;
  font-weight: 800;
  color: #ffffff;
  letter-spacing: -0.2px;
}

.stats-panel-header p {
  font-size: 0.73rem;
  color: #6b7280;
  margin-top: 4px;
  font-weight: 500;
}

/* Column headers */
.stats-col-headers {
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

/* Stat rows */
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
.stat-row:hover { background: #141f2e; }

.stat-name {
  font-size: 0.88rem;
  font-weight: 600;
  color: #d1d5db;
}

.stat-val {
  font-size: 1.35rem;
  font-weight: 800;
  color: #ffffff;
  text-align: center;
  letter-spacing: -0.5px;
}

.pct-bar-wrap {
  display: flex;
  align-items: center;
  gap: 0;
}

.pct-track {
  flex: 1;
  height: 8px;
  background: #1a2234;
  border-radius: 4px;
  overflow: hidden;
}

.pct-fill {
  height: 100%;
  border-radius: 4px;
}

.pct-pill {
  text-align: right;
  padding-left: 0;
}

.pct-badge {
  display: inline-block;
  font-size: 0.78rem;
  font-weight: 800;
  color: #fff;
  padding: 4px 10px;
  border-radius: 20px;
  min-width: 52px;
  text-align: center;
  letter-spacing: 0.3px;
}

/* No data / error states */
.no-data-msg {
  padding: 60px 24px;
  text-align: center;
  color: #4b5563;
  font-size: 0.95rem;
}

.error-card {
  padding: 40px 24px;
  text-align: center;
  color: #6b7280;
}
"

# ── UI ─────────────────────────────────────────────────────────────────────────
ui <- tagList(
  tags$head(
    tags$style(HTML(APP_CSS))
  ),

  # ── Header
  div(class = "app-header",
    tags$img(
      class = "bucks-logo",
      src   = "https://cdn.nba.com/logos/nba/1610612749/global/L/logo.svg",
      alt   = "Milwaukee Bucks"
    ),
    div(class = "app-header-text",
      tags$h1("Milwaukee Bucks"),
      tags$p("2024-25 Player Statistics")
    )
  ),

  # ── Selector bar
  div(class = "selector-bar",
    span(class = "select-label", "Player"),
    selectInput("player_id", label = NULL,
                choices  = choices,
                selected = if (length(choices) > 0) choices[[1]] else NULL,
                width    = "360px")
  ),

  # ── Main layout
  div(class = "main-content",
    uiOutput("player_card"),
    uiOutput("stats_panel")
  )
)

# ── Server ─────────────────────────────────────────────────────────────────────
server <- function(input, output, session) {

  player_row <- reactive({
    req(input$player_id)
    if (is.null(nba_pool)) return(data.frame())
    nba_pool |> filter(PLAYER_ID == input$player_id)
  })

  roster_row <- reactive({
    req(input$player_id)
    if (is.null(bucks_roster)) return(data.frame())
    bucks_roster |> filter(PLAYER_ID == input$player_id)
  })

  # ── Player card
  output$player_card <- renderUI({
    info  <- roster_row()
    stats <- player_row()

    if (nrow(info) == 0) {
      return(div(class = "player-card",
                 div(class = "error-card", "Player information unavailable.")))
    }

    pid  <- info$PLAYER_ID[1]
    name <- info$PLAYER_NAME[1]
    num  <- {
      n <- info$NUM[1]
      if (!is.na(n) && nchar(trimws(n)) > 0) paste0("#", trimws(n)) else "\u2014"
    }
    pos  <- if (!is.na(info$POSITION[1]) && nchar(trimws(info$POSITION[1])) > 0)
              trimws(info$POSITION[1]) else "\u2014"
    gp   <- if (nrow(stats) > 0 && !is.na(stats$GP[1])) as.integer(stats$GP[1]) else NA_integer_

    div(class = "player-card",
      div(class = "player-photo-bg",
        tags$img(
          src     = photo_url(pid),
          alt     = name,
          onerror = paste0(
            "this.onerror=null;",
            "this.src='https://via.placeholder.com/180x135/1a2234/6b7280?text=No+Photo';"
          )
        )
      ),
      div(class = "player-details",
        div(class = "player-full-name", name),
        div(class = "player-chips",
          div(class = "chip", "No. ", tags$strong(num)),
          div(class = "chip", tags$strong(pos))
        ),
        div(class = "detail-block",
          div(class = "detail-block-label", "Team"),
          div(class = "detail-block-value bucks-green", "Milwaukee Bucks")
        ),
        if (!is.na(gp))
          div(class = "detail-block",
            div(class = "detail-block-label", "Games Played"),
            div(class = "gp-big", gp)
          )
      )
    )
  })

  # ── Stats panel
  output$stats_panel <- renderUI({
    stats <- player_row()

    if (nrow(stats) == 0) {
      return(
        div(class = "stats-panel",
          div(class = "no-data-msg",
            "No statistics available for this player (minimum ",
            MIN_GP, " games required)."
          )
        )
      )
    }

    rows <- lapply(STAT_DEFS, function(def) {
      col    <- def$col
      label  <- def$label
      v100   <- as.numeric(stats[[col]][1])
      v75    <- if (!is.na(v100)) round(v100 * 0.75, 1) else NA_real_
      pool   <- as.numeric(nba_pool[[col]])
      pct    <- calc_pct(v100, pool)
      color  <- pct_col(pct)
      pct_s  <- safe_pct(pct)
      ord    <- ordinal(pct)
      val_s  <- if (!is.na(v75)) format(v75, nsmall = 1) else "\u2014"

      div(class = "stat-row",
        div(class = "stat-name", label),
        div(class = "stat-val", val_s),
        div(class = "pct-bar-wrap",
          div(class = "pct-track",
            div(class = "pct-fill",
              style = sprintf("width:%d%%;background:%s", pct_s, color)
            )
          )
        ),
        div(class = "pct-pill",
          div(class  = "pct-badge",
              style  = sprintf("background:%s", color),
              ord)
        )
      )
    })

    div(class = "stats-panel",
      div(class = "stats-panel-header",
        tags$h2("Per 75 Possessions"),
        tags$p(
          sprintf(
            "Percentile vs. all NBA players (%d+ GP) \u2022 2024-25 Regular Season",
            MIN_GP
          )
        )
      ),
      div(class = "stats-col-headers",
        div(class = "chdr",   "Stat"),
        div(class = "chdr c", "Per 75"),
        div(class = "chdr",   "Percentile"),
        div(class = "chdr r", "Rank")
      ),
      div(rows)
    )
  })
}

shinyApp(ui, server)
