import sqlite3
import os
from pathlib import Path
from urllib.parse import quote, unquote
import re
import hashlib
import base64
import html
import json
import time
import hmac
import uuid
import requests
import psycopg2
from psycopg2 import pool as pg_pool
from datetime import datetime

import pandas as pd
import altair as alt
import streamlit as st
import streamlit.components.v1 as components

# ============================================================
# LAST DEMONS ESPORTS — COMMAND CENTER V2
# ============================================================

st.set_page_config(
    page_title="LAST DEMONS ESPORTS",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# CLOUD CONFIGURATION
# I valori reali vanno inseriti nei Secrets di Streamlit Cloud.
# Non inserire password o chiavi direttamente nel repository GitHub.
# ============================================================
try:
    DATABASE_URL = st.secrets["DATABASE_URL"]
    SUPABASE_URL = st.secrets["SUPABASE_URL"].rstrip("/")
    SUPABASE_SERVICE_KEY = str(st.secrets["SUPABASE_SERVICE_KEY"]).strip()
    SUPABASE_BUCKET = str(st.secrets.get("SUPABASE_BUCKET", "proof-screenshots")).strip()
    FOUNDER_PASSWORD = st.secrets["FOUNDER_PASSWORD"]
except KeyError as exc:
    st.error(
        "⚠️ Configurazione cloud mancante. Apri Streamlit Cloud → App → Settings "
        "→ Secrets e inserisci DATABASE_URL, SUPABASE_URL, SUPABASE_SERVICE_KEY "
        "e FOUNDER_PASSWORD."
    )
    st.stop()

# Persistent Player login (30 days)
# AUTH_SECRET is optional: if absent, FOUNDER_PASSWORD is used as signing secret.
AUTH_SECRET = str(st.secrets.get("AUTH_SECRET", FOUNDER_PASSWORD)).strip()
REMEMBER_DAYS = 30
REMEMBER_COOKIE = "ld_player_device"

def validate_storage_config():
    missing = []
    if not str(SUPABASE_URL or "").strip():
        missing.append("SUPABASE_URL")
    if not str(SUPABASE_SERVICE_KEY or "").strip():
        missing.append("SUPABASE_SERVICE_KEY")
    if not str(SUPABASE_BUCKET or "").strip():
        missing.append("SUPABASE_BUCKET")
    return missing

FOUNDER_REMEMBER_COOKIE = "ld_founder_device"

@st.cache_resource(show_spinner=False)
def load_logo_b64():
    logo_path = Path(__file__).with_name("last_demons_logo.png")
    return base64.b64encode(logo_path.read_bytes()).decode("ascii")

LOGO_B64 = load_logo_b64()

def display_selection(value):
    return "LD Player" if str(value or "").strip().casefold() == "academy" else (value or "Non Assegnato")


def auto_close_mobile_sidebar(nav_key: str, current_value: str):
    """Close the Streamlit sidebar immediately on mobile after navigation changes."""
    state_key = f"_last_nav_{nav_key}"
    previous = st.session_state.get(state_key)
    st.session_state[state_key] = current_value
    if previous is None or previous == current_value:
        return

    # The script runs inside a Streamlit component iframe. We target the parent
    # document and support both current and older Streamlit sidebar controls.
    components.html(
        """
        <script>
        (() => {
          const closeSidebar = () => {
            try {
              const w = window.parent;
              if (!w || w.innerWidth > 900) return;

              const d = w.document;
              const selectors = [
                '[data-testid="stSidebarCollapseButton"] button',
                '[data-testid="stSidebarCollapseButton"]',
                '[data-testid="collapsedControl"] button',
                'button[aria-label="Close sidebar"]',
                'button[aria-label="Collapse sidebar"]',
                'button[title="Close sidebar"]',
                'button[title="Collapse sidebar"]'
              ];

              for (const selector of selectors) {
                const el = d.querySelector(selector);
                if (el) {
                  el.dispatchEvent(new MouseEvent("click", {
                    view: w, bubbles: true, cancelable: true
                  }));
                  return true;
                }
              }

              // Fallback: locate the visible sidebar and its collapse/chevron button.
              const sidebar = d.querySelector('[data-testid="stSidebar"]');
              if (sidebar) {
                const buttons = [...sidebar.querySelectorAll("button")];
                const btn = buttons.find(b => {
                  const txt = ((b.getAttribute("aria-label") || "") + " " +
                               (b.getAttribute("title") || "") + " " +
                               (b.textContent || "")).toLowerCase();
                  return txt.includes("close") || txt.includes("collapse") ||
                         txt.includes("chiudi") || txt.includes("comprimi") ||
                         txt.includes("«") || txt.includes("‹");
                });
                if (btn) {
                  btn.dispatchEvent(new MouseEvent("click", {
                    view: w, bubbles: true, cancelable: true
                  }));
                  return true;
                }
              }
            } catch (e) {}
            return false;
          };

          // Streamlit may finish the rerender a fraction later on mobile.
          if (!closeSidebar()) {
            setTimeout(closeSidebar, 60);
            setTimeout(closeSidebar, 180);
          }
        })();
        </script>
        """,
        height=0,
    )


def active_season_v241():
    rows = db_query(
        "SELECT id, name, started_at FROM seasons WHERE is_active=TRUE ORDER BY id DESC LIMIT 1",
        fetchall=True,
    ) or []
    return rows[0] if rows else None


# ============================================================
# THEME
# ============================================================

st.markdown(
    """
    <style>
    :root {
        --ld-red: #ef1828;
        --ld-red-dark: #8d0711;
        --ld-bg: #050608;
        --ld-panel: rgba(15,17,22,.90);
        --ld-border: rgba(255,255,255,.09);
        --ld-muted: #9ca3af;
    }

    html, body, [class*="css"] {
        font-family: Inter, Arial, sans-serif;
    }

    .stApp {
        background:
          radial-gradient(circle at 85% 5%, rgba(239,24,40,.12), transparent 28%),
          radial-gradient(circle at 10% 35%, rgba(130,0,15,.10), transparent 25%),
          linear-gradient(135deg, #030405 0%, #090b0f 52%, #050608 100%);
        color: #f5f7fa;
    }

    .block-container {
        max-width: 1600px;
        padding: 1.15rem 2.1rem 3rem;
    }

    [data-testid="stSidebar"] {
        background:
          linear-gradient(180deg, rgba(6,7,10,.98), rgba(15,17,23,.98));
        border-right: 1px solid rgba(239,24,40,.18);
    }

    [data-testid="stSidebar"] .block-container {
        padding-top: 1rem;
    }

    .ld-hero {
        min-height: 220px;
        width: 100%;
        border: 1px solid rgba(255,255,255,.09);
        border-radius: 24px;
        background:
          linear-gradient(105deg, rgba(4,5,7,.98) 0%, rgba(19,7,10,.94) 52%, rgba(77,3,12,.80) 100%);
        box-shadow: 0 22px 70px rgba(0,0,0,.42), inset 0 0 60px rgba(239,24,40,.04);
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 22px 34px;
        margin-bottom: 24px;
        overflow: hidden;
        position: relative;
    }

    .ld-hero:after {
        content: "";
        position: absolute;
        right: -90px;
        top: -160px;
        width: 430px;
        height: 430px;
        border: 1px solid rgba(239,24,40,.16);
        border-radius: 50%;
        box-shadow: 0 0 90px rgba(239,24,40,.12);
    }

    .ld-logo {
        width: 185px;
        height: 185px;
        object-fit: contain;
        filter: drop-shadow(0 0 18px rgba(239,24,40,.25));
        z-index: 2;
    }

    .ld-hero-copy {
        flex: 1;
        padding-left: 28px;
        z-index: 2;
    }

    .ld-kicker {
        color: #ef1828;
        font-size: .78rem;
        letter-spacing: .30em;
        font-weight: 900;
        margin-bottom: 8px;
    }

    .ld-title {
        margin: 0;
        font-size: clamp(2.1rem, 5vw, 4.8rem);
        line-height: .95;
        font-weight: 950;
        letter-spacing: .055em;
        color: #fff;
        text-shadow: 0 0 30px rgba(239,24,40,.15);
    }

    .ld-subtitle {
        color: #aab0ba;
        letter-spacing: .18em;
        font-size: .82rem;
        margin-top: 13px;
        text-transform: uppercase;
    }

    .ld-section {
        border-left: 4px solid var(--ld-red);
        padding: 12px 16px;
        margin: 7px 0 20px;
        background: linear-gradient(90deg, rgba(239,24,40,.09), rgba(255,255,255,.015));
        border-radius: 0 12px 12px 0;
        font-weight: 900;
        letter-spacing: .08em;
    }

    .ld-card {
        border: 1px solid var(--ld-border);
        border-radius: 18px;
        padding: 22px;
        background: linear-gradient(145deg, rgba(18,20,26,.92), rgba(8,9,12,.94));
        box-shadow: 0 14px 40px rgba(0,0,0,.25);
        margin-bottom: 16px;
    }

    .ld-welcome {
        font-size: 1.45rem;
        font-weight: 900;
        margin-bottom: 4px;
    }

    .ld-muted { color: #9ca3af; }

    div[data-testid="stMetric"] {
        background: linear-gradient(145deg, rgba(21,23,30,.92), rgba(10,11,15,.96));
        border: 1px solid rgba(255,255,255,.075);
        border-radius: 16px;
        padding: 16px;
        box-shadow: 0 12px 30px rgba(0,0,0,.20);
    }

    div[data-testid="stMetricValue"] {
        color: #fff;
        font-weight: 900;
    }

    div[data-testid="stDataFrame"],
    div[data-testid="stExpander"],
    div[data-testid="stFileUploader"] {
        border-radius: 16px;
        overflow: hidden;
    }

    .stButton > button,
    .stFormSubmitButton > button {
        min-height: 46px;
        border-radius: 11px;
        font-weight: 850;
        border: 1px solid rgba(255,255,255,.10);
        transition: .18s ease;
    }

    .stButton > button:hover,
    .stFormSubmitButton > button:hover {
        border-color: rgba(239,24,40,.70);
        transform: translateY(-1px);
    }

    .stButton > button[kind="primary"],
    .stFormSubmitButton > button[kind="primary"] {
        background: linear-gradient(90deg, #a90918, #ef1828);
        border: 0;
        color: white;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }

    .stTabs [data-baseweb="tab"] {
        background: rgba(255,255,255,.025);
        border-radius: 10px 10px 0 0;
        padding-left: 20px;
        padding-right: 20px;
    }

    hr { border-color: rgba(255,255,255,.07); }

    @media (max-width: 760px) {
        .block-container { padding: .8rem .8rem 2rem; }
        .ld-hero { min-height: 170px; padding: 15px; border-radius: 18px; }
        .ld-logo { width: 118px; height: 118px; }
        .ld-hero-copy { padding-left: 12px; }
        .ld-title { font-size: 2rem; }
        .ld-subtitle { font-size: .60rem; letter-spacing: .09em; }
        .ld-kicker { font-size: .62rem; letter-spacing: .18em; }
    }
    
/* ===== V2.4 LEADERBOARD ARENA ===== */
.lb-arena{
    border:1px solid rgba(239,24,40,.35);
    border-radius:24px;
    padding:22px;
    background:
      radial-gradient(circle at 50% 0%, rgba(239,24,40,.14), transparent 38%),
      linear-gradient(180deg, rgba(15,17,23,.96), rgba(5,6,8,.98));
    box-shadow:0 18px 55px rgba(0,0,0,.42);
    margin:8px 0 22px 0;
}
.lb-kicker{font-size:.78rem;letter-spacing:.22em;color:#ef1828;font-weight:900;}
.lb-title{font-size:clamp(1.8rem,4vw,3.2rem);font-weight:1000;line-height:1;margin:.25rem 0;}
.lb-sub{color:#aeb3bd;margin-bottom:8px;}
.lb-card{
    border:1px solid rgba(255,255,255,.10);
    background:linear-gradient(180deg,rgba(25,27,34,.98),rgba(10,11,15,.98));
    border-radius:20px;padding:18px;text-align:center;min-height:255px;
    box-shadow:0 12px 35px rgba(0,0,0,.32);
}
.lb-card.first{border-color:rgba(255,215,0,.6); transform:translateY(-8px);}
.lb-card.second{border-color:rgba(192,192,192,.5);}
.lb-card.third{border-color:rgba(205,127,50,.55);}
.lb-rank{font-size:2rem;font-weight:1000;}
.lb-name{font-size:1.12rem;font-weight:900;word-break:break-word;margin-top:7px;}
.lb-meta{font-size:.78rem;color:#9ca3af;text-transform:uppercase;letter-spacing:.08em;}
.lb-score{font-size:1.65rem;font-weight:1000;margin-top:12px;}
.lb-label{font-size:.7rem;color:#ef1828;font-weight:900;letter-spacing:.14em;}
.lb-me{border:1px solid rgba(239,24,40,.75)!important;box-shadow:0 0 0 1px rgba(239,24,40,.25),0 8px 30px rgba(239,24,40,.12);}
.lb-row{
    display:grid;grid-template-columns:55px minmax(140px,1.7fr) 1fr 1fr 1fr;
    gap:12px;align-items:center;padding:13px 16px;margin:8px 0;
    border-radius:14px;background:rgba(255,255,255,.035);
    border:1px solid rgba(255,255,255,.07);
}
.lb-row strong{font-size:1rem;}
.lb-muted{color:#9ca3af;font-size:.82rem;}
@media(max-width:720px){
  .lb-arena{padding:15px}
  .lb-card{min-height:0;margin-bottom:8px}
  .lb-card.first{transform:none}
  .lb-row{grid-template-columns:42px 1fr;gap:5px 10px}
  .lb-row .lb-mobile-stat{grid-column:2}
}


/* V2.5 PERFORMANCE */
[data-testid="stSidebar"] [role="radiogroup"] label {
    padding-top: .45rem !important;
    padding-bottom: .45rem !important;
}
[data-testid="stSidebar"] img { transition: none !important; }


.role-pill,.division-pill{display:inline-block;padding:4px 9px;margin:3px 4px 0 0;border-radius:999px;
font-family:"Arial Narrow","Roboto Condensed","Trebuchet MS",sans-serif;font-size:.72rem;font-weight:900;
letter-spacing:.10em;text-transform:uppercase;line-height:1.2}
.role-pill{background:rgba(239,24,40,.14);border:1px solid rgba(239,24,40,.45);color:#ff4b58}
.division-pill{background:rgba(255,255,255,.055);border:1px solid rgba(255,255,255,.14);color:#d8dbe2}


    /* Founder Top 5 — dark esports table rows */
    .ld-top5-wrap { display:flex; flex-direction:column; gap:10px; margin:10px 0 20px; }
    .ld-top5-row {
        display:grid !important; grid-template-columns:minmax(145px,1.3fr) minmax(260px,2fr) !important;
        align-items:center; gap:16px; padding:13px 16px;
        border:1px solid rgba(239,24,40,.34) !important; border-left:4px solid #ef1828 !important;
        border-radius:12px; background:#08090c !important; color:#f3f4f6 !important;
        box-shadow:0 6px 18px rgba(0,0,0,.24);
    }
    .ld-top5-player { display:flex; align-items:center; gap:12px; min-width:0; }
    .ld-top5-rank { min-width:34px; color:#ef1828; font-weight:900; font-size:1.05rem; }
    .ld-top5-name { color:#f3f4f6; font-weight:900; letter-spacing:.035em; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
    .ld-top5-stats { display:grid; grid-template-columns:repeat(3,1fr); gap:8px; }
    .ld-top5-stat { text-align:center; padding:5px 8px; border-left:1px solid rgba(239,24,40,.22); }
    .ld-top5-stat b { display:block; color:#ef1828; font-weight:900; }
    .ld-top5-stat span { display:block; margin-top:4px; color:#8f949d; font-size:.60rem; letter-spacing:.10em; }
    @media (max-width:700px) {
        .ld-top5-row { grid-template-columns:1fr !important; gap:9px; padding:11px 12px; }
        .ld-top5-stats { grid-template-columns:repeat(3,1fr); }
        .ld-top5-stat:first-child { border-left:0; }
    }
</style>
    """,
    unsafe_allow_html=True,
)


def hero():
    st.markdown(
        f"""
        <div class="ld-hero">
            <img class="ld-logo" src="data:image/png;base64,{LOGO_B64}">
            <div class="ld-hero-copy">
                <div class="ld-kicker">OFFICIAL ESPORTS COMMAND CENTER</div>
                <div class="ld-title">LAST DEMONS</div>
                <div class="ld-subtitle">Discipline · Progress · Victory</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# DATABASE CLOUD — SUPABASE POSTGRESQL
# ============================================================

@st.cache_resource(show_spinner=False)
def db_pool():
    return pg_pool.ThreadedConnectionPool(
        minconn=1, maxconn=8, dsn=DATABASE_URL, sslmode="require",
        connect_timeout=8, application_name="last_demons_streamlit",
    )

def get_conn():
    conn = db_pool().getconn()
    if conn.closed:
        db_pool().putconn(conn, close=True)
        conn = db_pool().getconn()
    return conn

def release_conn(conn):
    try:
        if conn.closed:
            db_pool().putconn(conn, close=True)
        else:
            db_pool().putconn(conn)
    except Exception:
        try: conn.close()
        except Exception: pass


def _sql(query: str) -> str:
    """Converte i placeholder SQLite ? nei placeholder PostgreSQL %s."""
    return query.replace("?", "%s")


@st.cache_resource(show_spinner=False)
def init_db():
    conn = get_conn()
    try:
        cur = conn.cursor()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS players (
                id BIGSERIAL PRIMARY KEY,
                activision_id TEXT UNIQUE NOT NULL,
                platform TEXT NOT NULL,
                selection TEXT DEFAULT 'Non Assegnato',
                status TEXT DEFAULT 'Pending',
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                password_hash TEXT
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS submissions (
                id BIGSERIAL PRIMARY KEY,
                activision_id TEXT NOT NULL,
                kills INTEGER NOT NULL,
                wins INTEGER NOT NULL,
                rating_gained DOUBLE PRECISION NOT NULL,
                photo_path TEXT NOT NULL,
                month_year TEXT NOT NULL,
                status TEXT DEFAULT 'Pending',
                timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                matches_played INTEGER
            )
            """
        )

        # Migrazioni non distruttive per tabelle eventualmente già create.
        cur.execute("ALTER TABLE players ADD COLUMN IF NOT EXISTS password_hash TEXT")
        cur.execute("ALTER TABLE players ADD COLUMN IF NOT EXISTS profile_image_url TEXT")
        cur.execute("ALTER TABLE players ADD COLUMN IF NOT EXISTS banner_url TEXT")
        cur.execute("ALTER TABLE players ADD COLUMN IF NOT EXISTS org_role TEXT DEFAULT 'Player'")
        cur.execute("ALTER TABLE submissions ADD COLUMN IF NOT EXISTS matches_played INTEGER")
        cur.execute("ALTER TABLE submissions ADD COLUMN IF NOT EXISTS season_id BIGINT")
        cur.execute("ALTER TABLE submissions ADD COLUMN IF NOT EXISTS placement INTEGER")
        cur.execute("ALTER TABLE submissions ADD COLUMN IF NOT EXISTS placement_score DOUBLE PRECISION")

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS announcements (
                id BIGSERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS notifications (
                id BIGSERIAL PRIMARY KEY,
                activision_id TEXT NOT NULL,
                message TEXT NOT NULL,
                is_read BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS seasons (
                id BIGSERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                started_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMPTZ,
                is_active BOOLEAN DEFAULT TRUE
            )
            """
        )
        cur.execute("SELECT COUNT(*) FROM seasons")
        if cur.fetchone()[0] == 0:
            cur.execute("INSERT INTO seasons (name, is_active) VALUES ('Season 1', TRUE)")

        # Conserva i dati già presenti nelle versioni precedenti:
        # le prove senza season_id vengono assegnate alla stagione attiva.
        cur.execute("SELECT id FROM seasons WHERE is_active=TRUE ORDER BY id DESC LIMIT 1")
        active_row = cur.fetchone()
        if active_row:
            cur.execute(
                "UPDATE submissions SET season_id=%s WHERE season_id IS NULL",
                (active_row[0],),
            )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS founder_notifications (
                id BIGSERIAL PRIMARY KEY,
                event_type TEXT NOT NULL DEFAULT 'system',
                activision_id TEXT,
                message TEXT NOT NULL,
                is_read BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_founder_notifications_read_created "
            "ON founder_notifications(is_read, created_at DESC)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_submissions_selection_leaderboard "
            "ON submissions(season_id, month_year, status, activision_id)"
        )

        cur.execute("CREATE INDEX IF NOT EXISTS idx_players_status ON players(status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_players_selection_status ON players(selection, status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_submissions_player ON submissions(activision_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_submissions_status ON submissions(status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_submissions_season_month_status ON submissions(season_id, month_year, status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_submissions_timestamp ON submissions(timestamp DESC)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_notifications_player_read ON notifications(activision_id, is_read)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_players_activision_status ON players(activision_id, status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_submissions_player_status_time ON submissions(activision_id, status, timestamp DESC)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_announcements_active_created ON announcements(is_active, created_at DESC)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_submissions_status_time ON submissions(status, timestamp DESC)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_submissions_player_status_id ON submissions(activision_id, status, id DESC)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_players_status_selection ON players(status, selection, activision_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_submissions_approved_player ON submissions(activision_id, timestamp DESC) WHERE status='Approved'")

        conn.commit()
    finally:
        release_conn(conn)


@st.cache_data(ttl=300, show_spinner=False)
def _db_read_cached(query: str, params_tuple: tuple):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(_sql(query), params_tuple)
            return cur.fetchall()
    finally:
        release_conn(conn)


def db_query(query, params=(), fetchall=False, commit=False):
    """Compatibile con il vecchio helper: SELECT cache breve, write immediati."""
    params = tuple(params or ())
    normalized = query.lstrip().upper()
    is_select = normalized.startswith("SELECT") and not commit

    if is_select:
        rows = _db_read_cached(query, params)
        return rows if fetchall else None

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(_sql(query), params)
            data = cur.fetchall() if fetchall and cur.description else None
        if commit:
            conn.commit()
            _db_read_cached.clear()
        return data
    except Exception:
        conn.rollback()
        raise
    finally:
        release_conn(conn)



init_db()


@st.cache_resource(show_spinner=False)
def normalize_rating_formula():
    """Rating: (1 per kill + 20 per victory) multiplied by placement tier."""
    db_query(
        """
        UPDATE submissions
        SET rating_gained =
            (COALESCE(kills, 0) + (COALESCE(wins, 0) * 20)) *
            CASE
                WHEN placement = 1 THEN 1.6
                WHEN placement BETWEEN 2 AND 5 THEN 1.4
                WHEN placement BETWEEN 6 AND 10 THEN 1.2
                ELSE 1.0
            END
        WHERE rating_gained IS DISTINCT FROM
            (COALESCE(kills, 0) + (COALESCE(wins, 0) * 20)) *
            CASE
                WHEN placement = 1 THEN 1.6
                WHEN placement BETWEEN 2 AND 5 THEN 1.4
                WHEN placement BETWEEN 6 AND 10 THEN 1.2
                ELSE 1.0
            END
        """,
        commit=True,
    )

normalize_rating_formula()

# ============================================================
# SECURITY / HELPERS
# ============================================================


def _token_b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _token_b64d(value: str) -> bytes:
    return base64.urlsafe_b64decode((value + "=" * (-len(value) % 4)).encode("ascii"))


def make_remember_token(activision_id: str) -> str:
    payload = json.dumps({
        "sub": activision_id,
        "exp": int(time.time()) + REMEMBER_DAYS * 86400,
        "v": 1,
    }, separators=(",", ":")).encode("utf-8")
    body = _token_b64e(payload)
    signature = hmac.new(
        AUTH_SECRET.encode("utf-8"), body.encode("ascii"), hashlib.sha256
    ).digest()
    return body + "." + _token_b64e(signature)


def verify_remember_token(token: str):
    try:
        body, signature = token.split(".", 1)
        expected = hmac.new(
            AUTH_SECRET.encode("utf-8"), body.encode("ascii"), hashlib.sha256
        ).digest()
        if not hmac.compare_digest(_token_b64d(signature), expected):
            return None
        payload = json.loads(_token_b64d(body).decode("utf-8"))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return str(payload.get("sub", "")).strip() or None
    except Exception:
        return None


def remember_device_script(token: str):
    # Persist server-visible token before rerun; mirror to localStorage as a durable fallback.
    st.query_params["device_token"] = token
    components.html(
        f"""<script>
        try {{
          localStorage.setItem({json.dumps(REMEMBER_COOKIE)}, {json.dumps(token)});
        }} catch(e) {{}}
        </script>""",
        height=0,
    )


def forget_device_script():
    try:
        if "device_token" in st.query_params:
            del st.query_params["device_token"]
    except Exception:
        pass
    components.html(
        f"""<script>
        try {{
          localStorage.removeItem({json.dumps(REMEMBER_COOKIE)});
        }} catch(e) {{}}
        </script>""",
        height=0,
    )


def restore_device_script():
    # Read localStorage in the browser and pass token once to Streamlit via query params.
    components.html(
        f"""<script>
        try {{
          const key = {json.dumps(REMEMBER_COOKIE)};
          const token = localStorage.getItem(key);
          const u = new URL(window.parent.location.href);
          if (token && !u.searchParams.get("device_token")) {{
            u.searchParams.set("device_token", token);
            window.parent.location.replace(u.toString());
          }}
        }} catch(e) {{}}
        </script>""",
        height=0,
    )


def try_restore_player_session():
    if st.session_state.get("player_logged_in"):
        return

    token = st.query_params.get("device_token")
    if token:
        player_id = verify_remember_token(token)
        if player_id:
            candidate = get_player(player_id)
            # Remembered devices are still revoked automatically if player loses approval.
            if candidate and candidate[4] == "Approved":
                st.session_state.player_logged_in = True
                st.session_state.player_id = candidate[1]
                return
        forget_device_script()
    else:
        restore_device_script()




def make_founder_remember_token() -> str:
    payload = json.dumps({
        "role": "founder",
        "exp": int(time.time()) + REMEMBER_DAYS * 86400,
        "v": 1,
    }, separators=(",", ":")).encode("utf-8")
    body = _token_b64e(payload)
    signature = hmac.new(
        AUTH_SECRET.encode("utf-8"), body.encode("ascii"), hashlib.sha256
    ).digest()
    return body + "." + _token_b64e(signature)


def verify_founder_remember_token(token: str) -> bool:
    try:
        body, signature = token.split(".", 1)
        expected = hmac.new(
            AUTH_SECRET.encode("utf-8"), body.encode("ascii"), hashlib.sha256
        ).digest()
        if not hmac.compare_digest(_token_b64d(signature), expected):
            return False
        payload = json.loads(_token_b64d(body).decode("utf-8"))
        return (
            payload.get("role") == "founder"
            and int(payload.get("exp", 0)) >= int(time.time())
        )
    except Exception:
        return False


def remember_founder_script(token: str):
    st.query_params["founder_token"] = token
    components.html(
        f"""<script>
        try {{
          localStorage.setItem({json.dumps(FOUNDER_REMEMBER_COOKIE)}, {json.dumps(token)});
        }} catch(e) {{}}
        </script>""",
        height=0,
    )


def forget_founder_script():
    try:
        if "founder_token" in st.query_params:
            del st.query_params["founder_token"]
    except Exception:
        pass
    components.html(
        f"""<script>
        try {{
          localStorage.removeItem({json.dumps(FOUNDER_REMEMBER_COOKIE)});
        }} catch(e) {{}}
        </script>""",
        height=0,
    )


def restore_founder_script():
    components.html(
        f"""<script>
        try {{
          const key = {json.dumps(FOUNDER_REMEMBER_COOKIE)};
          const token = localStorage.getItem(key);
          const u = new URL(window.parent.location.href);
          const isFounderRoute = ["1","true","yes"].includes(
            (u.searchParams.get("founder") || "").toLowerCase()
          );
          if (isFounderRoute && token && !u.searchParams.get("founder_token")) {{
            u.searchParams.set("founder_token", token);
            window.parent.location.replace(u.toString());
          }}
        }} catch(e) {{}}
        </script>""",
        height=0,
    )


def try_restore_founder_session():
    if st.session_state.get("founder_logged_in"):
        return

    founder_route = str(st.query_params.get("founder", "")).lower() in {"1", "true", "yes"}
    if not founder_route:
        return

    token = st.query_params.get("founder_token")
    if token:
        valid = verify_founder_remember_token(token)
        if valid:
            st.session_state.founder_logged_in = True
            return
        forget_founder_script()
    else:
        restore_founder_script()



def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return f"{salt.hex()}:{digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    if not stored or ":" not in stored:
        return False
    try:
        salt_hex, digest_hex = stored.split(":", 1)
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), 200_000
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def placement_rating_multiplier(placement: int) -> float:
    placement = int(placement)
    if placement == 1:
        return 1.6
    if 2 <= placement <= 5:
        return 1.4
    if 6 <= placement <= 10:
        return 1.2
    return 1.0


def calculate_rating(kills: int, wins: int, placement: int = 16) -> float:
    base_rating = int(kills) + (int(wins) * 20)
    return round(base_rating * placement_rating_multiplier(placement), 1)



PLACEMENT_POINTS = {
    1: 100.0, 2: 90.0, 3: 83.0, 4: 77.0,
    5: 70.0, 6: 64.0, 7: 58.0, 8: 51.0,
    9: 45.0, 10: 39.0, 11: 32.0, 12: 26.0,
    13: 19.0, 14: 13.0, 15: 6.0, 16: 0.0,
}

def calculate_placement_score(placement: int) -> float:
    return float(PLACEMENT_POINTS.get(int(placement), 0.0))


def safe_id(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", value)




@st.cache_resource(show_spinner=False)
def storage_http_session():
    session = requests.Session()
    session.headers.update({
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    })
    return session


@st.cache_data(ttl=300, show_spinner=False)
def resolve_storage_bucket():
    """Resolve configured bucket name to the real Supabase Storage bucket id."""
    configured = str(SUPABASE_BUCKET or "").strip()
    if not configured:
        raise RuntimeError("SUPABASE_BUCKET non configurato.")

    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    }

    # Supabase Storage service endpoint for listing buckets.
    url = f"{SUPABASE_URL.rstrip('/')}/storage/v1/bucket"
    try:
        response = storage_http_session().get(url, timeout=20)
    except requests.RequestException as exc:
        raise RuntimeError("Impossibile verificare i bucket Supabase Storage.") from exc

    if response.status_code in (401, 403):
        raise RuntimeError(
            "La Secret key non è autorizzata a leggere Supabase Storage. "
            "Controlla SUPABASE_SERVICE_KEY."
        )
    if not response.ok:
        raise RuntimeError(
            f"Verifica bucket Supabase fallita (HTTP {response.status_code})."
        )

    try:
        buckets = response.json() or []
    except Exception as exc:
        raise RuntimeError("Risposta bucket Supabase non valida.") from exc

    wanted = configured.casefold()
    # Match both real id and display name, case-insensitively.
    for bucket in buckets:
        bid = str(bucket.get("id") or "").strip()
        name = str(bucket.get("name") or "").strip()
        if wanted in {bid.casefold(), name.casefold()}:
            return {
                "id": bid or name,
                "name": name or bid,
                "public": bool(bucket.get("public", False)),
            }

    visible = [str(b.get("name") or b.get("id") or "").strip() for b in buckets]
    visible = [x for x in visible if x]
    hint = ", ".join(visible[:8]) if visible else "nessun bucket visibile"
    raise RuntimeError(
        f"Bucket configurato '{configured}' non trovato nel progetto Supabase. "
        f"Bucket visibili: {hint}"
    )


def storage_bucket_id() -> str:
    return resolve_storage_bucket()["id"]


def storage_bucket_segment() -> str:
    return quote(storage_bucket_id(), safe="")


def storage_object_path(object_path: str) -> str:
    return quote(str(object_path).lstrip("/"), safe="/")


def storage_upload_url(object_path: str) -> str:
    return (
        f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/"
        f"{storage_bucket_segment()}/{storage_object_path(object_path)}"
    )


def storage_public_url(object_path: str) -> str:
    return (
        f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/public/"
        f"{storage_bucket_segment()}/{storage_object_path(object_path)}"
    )



def safe_name(value: str) -> str:
    value = str(value or "").strip()
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value)
    return value.strip("._") or "player"



MAX_PLAYER_IMAGE_BYTES = 50 * 1024 * 1024

def save_proof(uploaded_file, activision_id):
    """Upload proof to Supabase Storage with useful error handling."""
    missing = validate_storage_config()
    if missing:
        raise RuntimeError("Configurazione Storage mancante: " + ", ".join(missing))
    safe_player = safe_name(activision_id)
    original_name = getattr(uploaded_file, "name", "proof.jpg")
    ext = Path(original_name).suffix.lower() or ".jpg"
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        ext = ".jpg"

    object_path = (
        f"proofs/{safe_player}/"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:10]}{ext}"
    )
    upload_url = storage_upload_url(object_path)

    file_bytes = uploaded_file.getvalue()
    if len(file_bytes) > MAX_PLAYER_IMAGE_BYTES:
        raise ValueError("L'immagine supera il limite massimo di 50 MB.")
    mime = getattr(uploaded_file, "type", None) or "image/jpeg"
    headers = {
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "apikey": SUPABASE_SERVICE_KEY,
        "Content-Type": mime,
        "x-upsert": "false",
    }

    try:
        response = storage_http_session().post(upload_url, headers=headers, data=file_bytes, timeout=45)
    except requests.RequestException as exc:
        raise RuntimeError(
            "Connessione a Supabase Storage non riuscita. Riprova tra poco."
        ) from exc

    if not response.ok:
        # Never expose service keys; return only status and safe server message.
        try:
            payload = response.json()
            detail = payload.get("message") or payload.get("error") or ""
        except Exception:
            detail = ""
        detail = str(detail)[:180]
        if response.status_code in (401, 403):
            raise RuntimeError(
                "Supabase Storage ha rifiutato l'upload (permessi/Service Role). "
                "Controlla SUPABASE_SERVICE_KEY nei Secrets."
            )
        if response.status_code == 404:
            resolve_storage_bucket.clear()
            raise RuntimeError(
                "Supabase Storage non trova il bucket risolto. "
                "Riprova: la cache bucket è stata aggiornata."
            )
        if response.status_code == 400 and "bucket" in detail.lower() and "not found" in detail.lower():
            resolve_storage_bucket.clear()
            raise RuntimeError(
                "Supabase ha restituito 'Bucket not found' dopo la risoluzione automatica. "
                "Controlla che SUPABASE_URL e SUPABASE_SERVICE_KEY appartengano allo stesso progetto."
            )
        if response.status_code == 409:
            raise RuntimeError("File già esistente. Riprova l'upload.")
        raise RuntimeError(
            f"Upload Storage fallito (HTTP {response.status_code})"
            + (f": {detail}" if detail else ".")
        )

    return storage_public_url(object_path)



def save_profile_media(uploaded_file, activision_id: str, media_type: str) -> str:
    """Carica avatar/banner nello stesso bucket Supabase Storage."""
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    if ext not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise ValueError("Formato immagine non supportato.")

    object_name = (
        f"profiles/{safe_id(activision_id)}/{media_type}_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex}{ext}"
    )
    upload_url = storage_upload_url(object_name)
    headers = {
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "apikey": SUPABASE_SERVICE_KEY,
        "Content-Type": uploaded_file.type or "application/octet-stream",
        "x-upsert": "false",
    }
    response = requests.post(upload_url, headers=headers, data=uploaded_file.getvalue(), timeout=45)
    response.raise_for_status()
    return storage_public_url(object_name)


def delete_storage_url(public_url):
    if not public_url:
        return
    try:
        prefix = f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/public/{storage_bucket_segment()}/"
        if not str(public_url).startswith(prefix):
            return
        object_path = unquote(str(public_url)[len(prefix):])
        headers = {
            "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
            "apikey": SUPABASE_SERVICE_KEY,
        }
        response = requests.delete(storage_upload_url(object_path), headers=headers, timeout=30)
        if response.status_code not in (200, 204, 404):
            response.raise_for_status()
    except Exception:
        pass


def medal(i):
    return ["🥇", "🥈", "🥉"][i] if i < 3 else str(i + 1)


def badge(status):
    return {
        "Approved": "✅ Approvato",
        "Pending": "⏳ In attesa",
        "Rejected": "❌ Rifiutato",
    }.get(status, status)



def notify_player(activision_id: str, message: str):
    db_query(
        "INSERT INTO notifications (activision_id, message) VALUES (?, ?)",
        (activision_id, message),
        commit=True,
    )



def notify_founder(event_type: str, message: str, activision_id: str = None):
    db_query(
        "INSERT INTO founder_notifications (event_type, activision_id, message) VALUES (?, ?, ?)",
        (event_type, activision_id, message),
        commit=True,
    )

def public_player_card(activision_id: str):
    rows = db_query(
        """
        SELECT activision_id, platform, selection, profile_image_url, banner_url, org_role
        FROM players
        WHERE activision_id=? AND status='Approved'
        """,
        (activision_id,),
        fetchall=True,
    ) or []
    if not rows:
        st.error("Player non trovato o non disponibile pubblicamente.")
        return

    act, platform, selection, avatar, banner, org_role = rows[0]
    stats_rows = db_query(
        """
        SELECT COALESCE(SUM(kills),0),
               COALESCE(SUM(wins),0),
               COALESCE(SUM(matches_played),0),
               COALESCE(SUM(rating_gained),0),
               COALESCE(AVG(COALESCE(placement_score,
                   CASE WHEN matches_played > 0 THEN wins * 100.0 / matches_played ELSE 0 END)),0)
        FROM submissions
        WHERE activision_id=? AND status='Approved'
        """,
        (act,),
        fetchall=True,
    ) or [(0, 0, 0, 0)]
    kills, wins, matches, rating, win_rate = stats_rows[0]

    st.markdown('<div class="ld-section">OFFICIAL PLAYER CARD</div>', unsafe_allow_html=True)
    if banner:
        st.image(banner, use_container_width=True)

    left, right = st.columns([1, 3], gap="large")
    with left:
        if avatar:
            st.image(avatar, width=220)
        else:
            st.markdown("## 👤")
    with right:
        st.markdown(f"## 🎮 {act}")
        st.caption(f"{org_role or 'Player'} · {selection or 'Non Assegnato'} · {platform}")
        a, b, c, d = st.columns(4)
        a.metric("💀 Kill", int(kills or 0))
        b.metric("🏆 Win", int(wins or 0))
        c.metric("⚡ Win Rate", f"{win_rate:.1f}%")
        d.metric("🔥 Rating", f"{float(rating or 0):.0f}")



def get_player(activision_id):
    rows = db_query(
        """
        SELECT id, activision_id, platform, selection, status, created_at, password_hash, profile_image_url, banner_url, org_role
        FROM players WHERE activision_id=?
        """,
        (activision_id,),
        fetchall=True,
    ) or []
    return rows[0] if rows else None


# ============================================================
# SESSION
# ============================================================

defaults = {
    "player_logged_in": False,
    "player_id": None,
    "founder_logged_in": False,
}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


def player_logout():
    st.session_state.player_logged_in = False
    st.session_state.player_id = None
    st.rerun()


def founder_logout():
    st.session_state.founder_logged_in = False
    st.rerun()


# ============================================================
# PUBLIC AREA — ONLY REGISTER / LOGIN
# ============================================================

try_restore_player_session()
try_restore_founder_session()

if not st.session_state.player_logged_in and not st.session_state.founder_logged_in:
    hero()

    st.markdown(
        '<div class="ld-section">ACCESSO ORGANIZZAZIONE</div>',
        unsafe_allow_html=True,
    )

    founder_route = str(st.query_params.get("founder", "")).lower() in {"1", "true", "yes"}

    if founder_route:
        st.markdown('<div class="ld-section">FOUNDER CONTROL ROOM</div>', unsafe_allow_html=True)
        st.subheader("🛡️ Accesso Founder")
        st.caption("Area amministrativa riservata.")
        with st.form("founder_login_hidden"):
            founder_password = st.text_input("Password Founder", type="password")
            remember_founder = st.checkbox(
                "Ricorda questo dispositivo per 30 giorni",
                value=True,
                help="La password Founder non viene salvata sul dispositivo.",
            )
            founder_btn = st.form_submit_button(
                "ENTRA NEL CONTROL ROOM",
                type="primary",
                use_container_width=True,
            )
            if founder_btn:
                if hmac.compare_digest(founder_password, FOUNDER_PASSWORD):
                    st.session_state.founder_logged_in = True
                    if remember_founder:
                        remember_founder_script(make_founder_remember_token())
                    st.rerun()
                else:
                    st.error("Password Founder errata.")
        st.stop()

    st.markdown('<div class="ld-section">JOIN LAST DEMONS</div>', unsafe_allow_html=True)

    portal_mode = st.radio(
        "PORTALE",
        ["🔥 REGISTRATI", "🎮 ACCESSO PLAYER"],
        horizontal=True,
        key="public_portal_mode_v28",
    )
    left, right = st.columns([1.25, 1], gap="large")

    with left:
        if portal_mode == "🔥 REGISTRATI":
            st.subheader("🔥 Candidatura")
            with st.form("register_v28", clear_on_submit=True):
                act_id = st.text_input("Activision ID", placeholder="DemonKing#1234567")
                platform = st.selectbox("Piattaforma", ["PlayStation 5 / PS4","Xbox Series X/S / One","PC (Steam / Battle.net)"])
                password = st.text_input("Password", type="password")
                confirm = st.text_input("Conferma password", type="password")
                submit = st.form_submit_button("🔥 INVIA CANDIDATURA", type="primary", use_container_width=True)
                if submit:
                    clean_id=act_id.strip()
                    if not clean_id or "#" not in clean_id:
                        st.error("Inserisci un Activision ID valido con #.")
                    elif len(clean_id) > 64 or not re.fullmatch(r"[A-Za-z0-9_. -]{1,48}#[A-Za-z0-9]{1,12}", clean_id):
                        st.error("Activision ID non valido. Usa solo lettere, numeri, spazio, _, -, . e il codice dopo #.")
                    elif len(password)<6:
                        st.error("La password deve avere almeno 6 caratteri.")
                    elif password!=confirm:
                        st.error("Le password non coincidono.")
                    else:
                        try:
                            db_query("""INSERT INTO players
                                (activision_id,platform,status,password_hash,org_role)
                                VALUES (?,?,'Pending',?,'Player')""",
                                (clean_id,platform,hash_password(password)),commit=True)
                            st.session_state["checked_candidate"]=clean_id
                            notify_founder("application", "Nuova candidatura ricevuta.", clean_id)
                            st.success("Candidatura inviata. Attendi l'approvazione Founder.")
                        except psycopg2.IntegrityError:
                            st.error("Questo Activision ID è già registrato.")

            st.divider()
            st.subheader("🔎 Stato candidatura")
            check_id=st.text_input("Activision ID già registrato",
                value=st.session_state.get("checked_candidate",""),key="candidate_check_v28")
            if st.button("VERIFICA STATO",use_container_width=True):
                _db_read_cached.clear()
                candidate=get_player(check_id.strip())
                if not candidate: st.warning("Nessuna candidatura trovata.")
                elif candidate[4]=="Pending": st.info("⏳ In attesa di approvazione.")
                elif candidate[4]=="Rejected": st.error("❌ Candidatura non approvata.")
                elif candidate[4]=="Approved":
                    st.session_state["checked_candidate"]=candidate[1]
                    st.success("✅ Approvato. Apri ACCESSO PLAYER.")

        else:
            st.subheader("🎮 Accesso Player")
            st.caption("L'accesso funziona solo per gli account Approved.")
            with st.form("player_login_v28"):
                login_id=st.text_input("Activision ID",
                    value=st.session_state.get("checked_candidate",""),
                    placeholder="DemonKing#1234567")
                login_password=st.text_input("Password",type="password")
                remember_device = st.checkbox(
                    "Ricorda questo dispositivo per 30 giorni",
                    value=True,
                    help="La password non viene salvata sul dispositivo.",
                )
                login_btn=st.form_submit_button("🎮 ACCEDI AL COMMAND CENTER",type="primary",use_container_width=True)
                if login_btn:
                    _db_read_cached.clear()
                    candidate=get_player(login_id.strip())
                    if not candidate: st.error("Activision ID non registrato.")
                    elif candidate[4]=="Pending": st.warning("⏳ Candidatura ancora in attesa.")
                    elif candidate[4]=="Rejected": st.error("❌ Candidatura non approvata.")
                    elif candidate[4]!="Approved": st.error("Account non abilitato.")
                    elif not candidate[6]: st.error("Password non configurata. Contatta il Founder.")
                    elif verify_password(login_password,candidate[6]):
                        st.session_state.player_logged_in=True
                        st.session_state.player_id=candidate[1]
                        if remember_device:
                            remember_device_script(make_remember_token(candidate[1]))
                        st.rerun()
                    else: st.error("Password errata.")

    with right:
        st.markdown("""<div class="ld-card">
            <div class="ld-welcome">LAST DEMONS PORTAL</div>
            <div class="ld-muted"><b>01</b> · Registrati.<br><br>
            <b>02</b> · Attendi l'approvazione.<br><br>
            <b>03</b> · Entra da <b>ACCESSO PLAYER</b>.<br><br>
            <b>04</b> · Accedi al Command Center.</div></div>""",unsafe_allow_html=True)
        st.markdown("### 👥 Roster ufficiale")
        roster=db_query("""SELECT activision_id,selection,org_role,profile_image_url
            FROM players WHERE status='Approved'
            ORDER BY selection,LOWER(activision_id) LIMIT 12""",fetchall=True) or []
        if not roster: st.caption("Il roster apparirà qui dopo le prime approvazioni.")
        else:
            for act,sel,role,avatar in roster:
                with st.container(border=True):
                    c1,c2=st.columns([1,4])
                    with c1:
                        if avatar: st.image(avatar,width=52)
                        else: st.write("👤")
                    with c2:
                        st.markdown(f"**{act}**")
                        st.markdown(f'<span class="role-pill">{role or "Player"}</span> '
                                    f'<span class="division-pill">{sel or "Non Assegnato"}</span>',
                                    unsafe_allow_html=True)


    st.stop()


# ============================================================
# FOUNDER AREA
# ============================================================

if st.session_state.founder_logged_in:
    st.sidebar.markdown(
        f'<div style="text-align:center"><img src="data:image/png;base64,{LOGO_B64}" '
        'style="width:150px;max-width:90%;"></div>',
        unsafe_allow_html=True,
    )
    st.sidebar.markdown("### 🛡️ FOUNDER")
    founder_page = st.sidebar.radio(
        "CONTROL ROOM",
        ["📊 Dashboard", "🔔 Notifiche", "📢 Comunicazioni", "👥 Candidature", "📸 Prove Player", "🎮 Gestione Player", "🗓️ Stagioni"],
        key="founder_navigation_v241",
    )
    auto_close_mobile_sidebar("founder_navigation_v241", founder_page)
    if st.sidebar.button("🚪 Logout Founder", use_container_width=True):
        forget_founder_script()
        founder_logout()

    hero()

    if founder_page == "📊 Dashboard":
        st.markdown('<div class="ld-section">FOUNDER DASHBOARD</div>', unsafe_allow_html=True)

        approved, pending, proofs, total_proofs, founder_unread = db_query(
            """
            SELECT
              (SELECT COUNT(*) FROM players WHERE status='Approved'),
              (SELECT COUNT(*) FROM players WHERE status='Pending'),
              (SELECT COUNT(*) FROM submissions WHERE status='Pending'),
              (SELECT COUNT(*) FROM submissions),
              (SELECT COUNT(*) FROM founder_notifications WHERE is_read=FALSE)
            """,
            fetchall=True,
        )[0]

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Player ufficiali", approved)
        c2.metric("Candidature", pending)
        c3.metric("Prove da valutare", proofs)
        c4.metric("Prove totali", total_proofs)
        if founder_unread:
            st.info(f"🔔 Hai {founder_unread} notifiche Founder non lette.")

        st.markdown("### 🏆 TOP 5 ORGANIZZAZIONE")
        perf = db_query(
            """
            SELECT p.activision_id,
                   COALESCE(SUM(s.kills),0),
                   COALESCE(SUM(s.wins),0),
                   COALESCE(SUM(s.matches_played),0),
                   COALESCE(SUM(s.rating_gained),0),
                   COALESCE(AVG(COALESCE(s.placement_score,
                       CASE WHEN s.matches_played > 0 THEN s.wins * 100.0 / s.matches_played ELSE 0 END)),0)
            FROM players p
            LEFT JOIN submissions s ON s.activision_id=p.activision_id AND s.status='Approved'
            WHERE p.status='Approved'
            GROUP BY p.activision_id
            ORDER BY COALESCE(SUM(s.rating_gained),0) DESC
            LIMIT 5
            """,
            fetchall=True,
        ) or []
        if perf:
            st.markdown('<div class="ld-top5-wrap">', unsafe_allow_html=True)
            for rank, row in enumerate(perf, start=1):
                act, kills_v, wins_v, matches_v, rating_v, win_rate_v = row
                safe_act = html.escape(str(act))
                st.markdown(
                    f"""<div class="ld-top5-row">
                        <div class="ld-top5-player">
                            <div class="ld-top5-rank">#{rank}</div>
                            <div class="ld-top5-name">{safe_act}</div>
                        </div>
                        <div class="ld-top5-stats">
                            <div class="ld-top5-stat"><b>{float(rating_v or 0):.1f}</b><span>RATING</span></div>
                            <div class="ld-top5-stat"><b>{int(kills_v or 0)}</b><span>KILL</span></div>
                            <div class="ld-top5-stat"><b>{float(win_rate_v or 0):.1f}%</b><span>WIN RATE</span></div>
                        </div>
                    </div>""",
                    unsafe_allow_html=True,
                )
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.caption("Le performance compariranno dopo le prime prove approvate.")

        season = active_season_v241()
        if season:
            st.info(f"🗓️ Stagione attiva: **{season[1]}**")

        recent_news = db_query(
            "SELECT title, body, created_at FROM announcements WHERE is_active=TRUE ORDER BY created_at DESC LIMIT 3",
            fetchall=True,
        ) or []
        if recent_news:
            st.markdown("### 📢 Ultime comunicazioni")
            for title, body, created in recent_news:
                with st.container(border=True):
                    st.markdown(f"**{title}**")
                    st.write(body)
                    st.caption(str(created)[:16])

    elif founder_page == "🔔 Notifiche":
        st.markdown('<div class="ld-section">NOTIFICHE FOUNDER</div>', unsafe_allow_html=True)
        unread_founder = db_query("SELECT COUNT(*) FROM founder_notifications WHERE is_read=FALSE", fetchall=True)[0][0]
        c1, c2 = st.columns([1, 2])
        c1.metric("Da leggere", unread_founder)
        with c2:
            if unread_founder and st.button("✓ Segna tutte come lette", use_container_width=True):
                db_query("UPDATE founder_notifications SET is_read=TRUE WHERE is_read=FALSE", commit=True)
                st.rerun()
        founder_notes = db_query(
            "SELECT id,event_type,activision_id,message,is_read,created_at FROM founder_notifications ORDER BY created_at DESC LIMIT 150",
            fetchall=True,
        ) or []
        if not founder_notes:
            st.info("Nessuna notifica Founder.")
        else:
            icons = {"application":"👥", "proof":"📸", "system":"🔔"}
            for nid, event_type, act_id, message, is_read, created in founder_notes:
                with st.container(border=True):
                    left, right = st.columns([5,1])
                    with left:
                        nuova = " · NUOVA" if not is_read else ""
                        st.markdown(f"**{icons.get(event_type,'🔔')} {message}{nuova}**")
                        meta = f"Activision ID: {act_id} · " if act_id else ""
                        st.caption(f"{meta}{str(created)[:16]}")
                    with right:
                        if not is_read and st.button("✓ Letta", key=f"founder_note_{nid}", use_container_width=True):
                            db_query("UPDATE founder_notifications SET is_read=TRUE WHERE id=?", (nid,), commit=True)
                            st.rerun()

    elif founder_page == "📢 Comunicazioni":
        st.markdown('<div class="ld-section">COMUNICAZIONI ORG</div>', unsafe_allow_html=True)
        with st.form("new_announcement", clear_on_submit=True):
            news_title = st.text_input("Titolo")
            news_body = st.text_area("Messaggio")
            publish = st.form_submit_button("📢 PUBBLICA", type="primary", use_container_width=True)
            if publish:
                if not news_title.strip() or not news_body.strip():
                    st.error("Inserisci titolo e messaggio.")
                else:
                    db_query(
                        "INSERT INTO announcements (title, body, is_active) VALUES (?, ?, TRUE)",
                        (news_title.strip(), news_body.strip()),
                        commit=True,
                    )
                    st.success("Comunicazione pubblicata.")
                    st.rerun()

        news_rows = db_query(
            "SELECT id, title, body, created_at, is_active FROM announcements ORDER BY created_at DESC",
            fetchall=True,
        ) or []
        for nid, title, body, created, active in news_rows:
            with st.container(border=True):
                st.markdown(f"### {title}")
                st.write(body)
                st.caption(f"{str(created)[:16]} · {'Attiva' if active else 'Archiviata'}")
                if active and st.button("Archivia", key=f"archive_news_{nid}"):
                    db_query("UPDATE announcements SET is_active=FALSE WHERE id=?", (nid,), commit=True)
                    st.rerun()

    elif founder_page == "👥 Candidature":
        st.markdown('<div class="ld-section">CANDIDATURE IN ATTESA</div>', unsafe_allow_html=True)

        rows = db_query(
            """
            SELECT id, activision_id, platform, created_at
            FROM players
            WHERE status='Pending'
            ORDER BY created_at ASC
            """,
            fetchall=True,
        ) or []

        if not rows:
            st.info("Nessuna candidatura in attesa.")
        else:
            for pid, act, platform, created in rows:
                with st.container(border=True):
                    a, b, c, d = st.columns([3, 2, 1.2, 1.2])
                    with a:
                        st.markdown(f"### 🎮 {act}")
                        st.caption(f"{platform} · {str(created)[:16]}")
                    with b:
                        role_label = st.selectbox(
                            "Selezione",
                            ["Élite", "LD Player"],
                            key=f"role_{pid}",
                        )
                        role = "Academy" if role_label == "LD Player" else role_label
                    with c:
                        st.write("")
                        if st.button("✅ Accetta", key=f"acc_{pid}", use_container_width=True):
                            db_query(
                                "UPDATE players SET selection=?, status='Approved' WHERE id=?",
                                (role, pid),
                                commit=True,
                            )
                            notify_player(act, f"✅ Candidatura approvata. Sei stato assegnato a {role}.")
                            st.rerun()
                    with d:
                        st.write("")
                        if st.button("❌ Rifiuta", key=f"rej_{pid}", use_container_width=True):
                            db_query(
                                "UPDATE players SET status='Rejected' WHERE id=?",
                                (pid,),
                                commit=True,
                            )
                            notify_player(act, "❌ La candidatura non è stata approvata.")
                            st.rerun()

    elif founder_page == "📸 Prove Player":
        st.markdown('<div class="ld-section">ARCHIVIO PROVE PER ACTIVISION ID</div>', unsafe_allow_html=True)

        ids = [
            r[0]
            for r in db_query(
                """
                SELECT activision_id
                FROM submissions
                GROUP BY activision_id
                ORDER BY LOWER(activision_id)
                """,
                fetchall=True,
            ) or []
        ]

        if not ids:
            st.info("Nessuna prova caricata.")
        else:
            f1, f2 = st.columns([2, 1])
            with f1:
                selected = st.selectbox("🎮 Activision ID", ids)
            with f2:
                proof_filter = st.selectbox(
                    "Stato",
                    ["Pending", "Approved", "Rejected", "Tutte"],
                )

            if proof_filter == "Tutte":
                rows = db_query(
                    """
                    SELECT id,kills,wins,matches_played,rating_gained,
                           photo_path,month_year,status,timestamp,placement,placement_score
                    FROM submissions
                    WHERE activision_id=?
                    ORDER BY
                      CASE status WHEN 'Pending' THEN 0 WHEN 'Approved' THEN 1 ELSE 2 END,
                      timestamp DESC
                    """,
                    (selected,),
                    fetchall=True,
                ) or []
            else:
                rows = db_query(
                    """
                    SELECT id,kills,wins,matches_played,rating_gained,
                           photo_path,month_year,status,timestamp,placement,placement_score
                    FROM submissions
                    WHERE activision_id=? AND status=?
                    ORDER BY timestamp DESC
                    """,
                    (selected, proof_filter),
                    fetchall=True,
                ) or []

            st.subheader(f"📂 {selected}")
            st.caption(f"{len(rows)} prove visualizzate")

            if not rows:
                st.info("Nessuna prova con questo filtro.")

            for row in rows:
                sid, kills, wins, matches, rating, path, month, status, ts, placement, placement_score = row
                with st.expander(
                    f"{badge(status)} · {ts} · {kills} Kill · {wins} Win",
                    expanded=status == "Pending",
                ):
                    img, info = st.columns([2.3, 1], gap="large")
                    with img:
                        if path:
                            st.image(path, caption=f"Prova #{sid}", use_container_width=True)
                        else:
                            st.error("Immagine non disponibile.")
                    with info:
                        st.markdown(f"### 🎮 {selected}")
                        st.write(f"**Kill:** {kills}")
                        st.write(f"**Vittorie:** {wins}")
                        st.write(f"**Partite:** {matches if matches else 'N/D'}")
                        if placement:
                            st.write(f"**Posizionamento:** {int(placement)}° su 16")
                        if placement_score is not None:
                            st.write(f"**Win Rate:** {float(placement_score):.1f}%")
                        elif matches:
                            st.write(f"**Win Rate:** {wins / matches * 100:.1f}%")
                        if placement:
                            st.write(f"**Moltiplicatore Rating:** ×{placement_rating_multiplier(placement):.1f}")
                        st.write(f"**Rating:** +{rating:.1f}".rstrip("0").rstrip("."))
                        st.write(f"**Mese:** {month}")

                        if status == "Pending":
                            if st.button(
                                "✅ APPROVA",
                                key=f"approve_{sid}",
                                type="primary",
                                use_container_width=True,
                            ):
                                db_query(
                                    "UPDATE submissions SET status='Approved' WHERE id=?",
                                    (sid,),
                                    commit=True,
                                )
                                notify_player(selected, f"✅ Prova #{sid} approvata: +{rating:.0f} rating.")
                                st.rerun()

                            if st.button(
                                "❌ RIFIUTA",
                                key=f"reject_{sid}",
                                use_container_width=True,
                            ):
                                db_query(
                                    "UPDATE submissions SET status='Rejected' WHERE id=?",
                                    (sid,),
                                    commit=True,
                                )
                                notify_player(selected, f"❌ Prova #{sid} rifiutata.")
                                st.rerun()

    elif founder_page == "🎮 Gestione Player":
        st.markdown('<div class="ld-section">GESTIONE PLAYER</div>', unsafe_allow_html=True)

        all_players = db_query(
            """
            SELECT id, activision_id, platform, selection, status, created_at, profile_image_url, banner_url, org_role
            FROM players
            ORDER BY LOWER(activision_id)
            """,
            fetchall=True,
        ) or []

        if not all_players:
            st.info("Nessun player registrato.")
        else:
            search_player = st.text_input(
                "🔎 Cerca player",
                placeholder="Scrivi Activision ID...",
                key="founder_player_search_v28",
            ).strip().lower()
            filtered_players = [
                p for p in all_players
                if not search_player or search_player in str(p[1]).lower()
            ]
            st.caption(f"{len(filtered_players)} visualizzati · {len(all_players)} player totali")

            if not filtered_players:
                st.info("Nessun player trovato.")
                st.stop()

            player_names = [p[1] for p in filtered_players]
            chosen = st.selectbox(
                "Gestisci player",
                player_names,
                key="founder_compact_player_selector_v28",
            )
            chosen_row = next(p for p in filtered_players if p[1] == chosen)

            # Anteprima profilo del player selezionato
            if chosen_row[7]:
                st.image(chosen_row[7], width=280)
            preview_cols = st.columns([1, 3])
            with preview_cols[0]:
                if chosen_row[6]:
                    st.image(chosen_row[6], width=90)
            with preview_cols[1]:
                st.markdown(f"### {chosen}")
                st.markdown(
                    f'<span class="role-pill">{chosen_row[8] or "Player"}</span> '
                    f'<span class="division-pill">{chosen_row[3] or "Non Assegnato"}</span>',
                    unsafe_allow_html=True,
                )
                st.caption(f"{chosen_row[2]} · {badge(chosen_row[4])}")

            c1, c2 = st.columns(2)
            with c1:
                selection_options = ["Élite", "LD Player", "Non Assegnato"]
                current_selection_label = "LD Player" if chosen_row[3] == "Academy" else chosen_row[3]
                new_selection_label = st.selectbox(
                    "Selezione",
                    selection_options,
                    index=selection_options.index(current_selection_label)
                    if current_selection_label in selection_options else 2,
                )
                new_selection = "Academy" if new_selection_label == "LD Player" else new_selection_label
                if st.button("💾 Salva selezione", use_container_width=True):
                    db_query(
                        "UPDATE players SET selection=? WHERE activision_id=?",
                        (new_selection, chosen),
                        commit=True,
                    )
                    st.success("Selezione aggiornata.")
                    st.rerun()

            with c2:
                new_password = st.text_input(
                    "Imposta/reset password player",
                    type="password",
                    help="Utile anche per account creati con la V1.",
                )
                if st.button("🔐 Salva nuova password", use_container_width=True):
                    if len(new_password) < 6:
                        st.error("Minimo 6 caratteri.")
                    else:
                        db_query(
                            "UPDATE players SET password_hash=? WHERE activision_id=?",
                            (hash_password(new_password), chosen),
                            commit=True,
                        )
                        st.success("Password player aggiornata.")

            st.divider()
            st.markdown("### 🛡️ Ruolo organizzazione")
            role_options = ["Player", "Coach", "Manager"]
            current_role = chosen_row[8] if chosen_row[8] in role_options else "Player"
            new_org_role = st.selectbox(
                "Ruolo",
                role_options,
                index=role_options.index(current_role),
                key=f"org_role_{chosen}",
            )
            if st.button("💾 Salva ruolo", use_container_width=True):
                db_query(
                    "UPDATE players SET org_role=? WHERE activision_id=?",
                    (new_org_role, chosen),
                    commit=True,
                )
                notify_player(chosen, f"🛡️ Il tuo ruolo nell'organizzazione è ora: {new_org_role}.")
                st.success("Ruolo aggiornato.")
                st.rerun()

            st.divider()
            st.markdown("### ⚠️ Rimozione player")
            st.caption(
                "Rimuove il player dal roster, tutte le sue prove dal database e i file "
                "associati dallo Storage. Questa operazione non è reversibile."
            )
            confirm_remove = st.checkbox(
                f"Confermo di voler rimuovere {chosen}",
                key=f"confirm_remove_{chosen}",
            )
            if st.button(
                "🗑️ RIMUOVI DEFINITIVAMENTE PLAYER",
                type="primary",
                use_container_width=True,
                disabled=not confirm_remove,
            ):
                media_rows = db_query(
                    "SELECT photo_path FROM submissions WHERE activision_id=?",
                    (chosen,),
                    fetchall=True,
                ) or []
                for media in media_rows:
                    delete_storage_url(media[0])
                delete_storage_url(chosen_row[6])
                delete_storage_url(chosen_row[7])

                db_query(
                    "DELETE FROM submissions WHERE activision_id=?",
                    (chosen,),
                    commit=True,
                )
                db_query(
                    "DELETE FROM players WHERE activision_id=?",
                    (chosen,),
                    commit=True,
                )
                st.success(f"{chosen} è stato rimosso dal roster.")
                st.rerun()

    elif founder_page == "🗓️ Stagioni":
        st.markdown('<div class="ld-section">GESTIONE STAGIONI</div>', unsafe_allow_html=True)
        current = active_season_v241()
        if current:
            st.success(f"Stagione attiva: {current[1]}")
        seasons = db_query(
            "SELECT id, name, started_at, ended_at, is_active FROM seasons ORDER BY id DESC",
            fetchall=True,
        ) or []
        st.dataframe(
            pd.DataFrame(seasons, columns=["ID", "Nome", "Inizio", "Fine", "Attiva"]),
            hide_index=True,
            use_container_width=True,
        )

        st.warning(
            "Avviare una nuova stagione NON cancella lo storico. "
            "Chiude quella corrente e crea una nuova classifica separata."
        )
        with st.form("new_season"):
            season_name = st.text_input("Nome nuova stagione", placeholder="Season 2")
            confirm_season = st.checkbox("Confermo il cambio stagione")
            new_season_btn = st.form_submit_button("🚀 AVVIA NUOVA STAGIONE", type="primary")
            if new_season_btn:
                if not season_name.strip() or not confirm_season:
                    st.error("Inserisci un nome e conferma.")
                else:
                    db_query(
                        "UPDATE seasons SET is_active=FALSE, ended_at=CURRENT_TIMESTAMP WHERE is_active=TRUE",
                        commit=True,
                    )
                    db_query(
                        "INSERT INTO seasons (name, is_active) VALUES (?, TRUE)",
                        (season_name.strip(),),
                        commit=True,
                    )
                    st.success("Nuova stagione avviata. Lo storico precedente resta disponibile.")
                    st.rerun()

    st.stop()



# ============================================================
# V2.4 — ESPORTS LEADERBOARD RENDERER
# ============================================================
def render_esports_leaderboard(rows, metric: str, logged_player: str = ""):
    """Renderizza podio Top 3 + classifica completa."""
    if not rows:
        st.info("Nessun risultato approvato per questo periodo.")
        return

    def score(row):
        if metric == "kills":
            return int(row.get("kills") or 0)
        return float(row.get("win_rate") or 0.0)

    ordered = sorted(
        rows,
        key=lambda row: (score(row), float(row.get("rating") or 0)),
        reverse=True,
    )
    label = "KILL" if metric == "kills" else "WIN RATE"
    title = "TOP FRAGGER" if metric == "kills" else "WIN RATE"

    st.markdown(
        f"""
        <div class="lb-arena">
            <div class="lb-kicker">LAST DEMONS · COMPETITIVE RANKING</div>
            <div class="lb-title">{title}</div>
            <div class="lb-sub">
                Classifica basata esclusivamente sulle prove approvate.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    podium = ordered[:3]
    # Con 3 player: argento a sinistra, oro al centro, bronzo a destra.
    visual_order = [1, 0, 2] if len(podium) == 3 else list(range(len(podium)))
    podium_cols = st.columns(len(visual_order), gap="medium")

    medals = {0: "🥇", 1: "🥈", 2: "🥉"}
    card_classes = {0: "first", 1: "second", 2: "third"}

    for column, podium_index in zip(podium_cols, visual_order):
        row = podium[podium_index]
        value = score(row)
        shown_value = f"{value:.1f}%" if metric == "win_rate" else str(int(value))
        is_me = row["activision_id"] == logged_player
        me_class = " lb-me" if is_me else ""

        with column:
            if row.get("avatar"):
                st.image(row["avatar"], width=105)
            st.markdown(
                f"""
                <div class="lb-card {card_classes.get(podium_index, '')}{me_class}">
                    <div class="lb-rank">{medals[podium_index]}</div>
                    <div class="lb-name">{row['activision_id']}</div>
                    <div class="lb-meta">{row['selection']}</div>
                    <div class="lb-score">{shown_value}</div>
                    <div class="lb-label">{label}</div>
                    <div class="lb-muted">
                        {int(row.get('wins') or 0)} WIN ·
                        {int(row.get('matches') or 0)} MATCH ·
                        {int(row.get('rating') or 0)} RATING
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    if len(ordered) > 3:
        st.markdown("### ⚔️ CLASSIFICA COMPLETA")
        for position, row in enumerate(ordered[3:], start=4):
            value = score(row)
            shown_value = f"{value:.1f}%" if metric == "win_rate" else str(int(value))
            me_class = " lb-me" if row["activision_id"] == logged_player else ""
            st.markdown(
                f"""
                <div class="lb-row{me_class}">
                    <div><strong>#{position}</strong></div>
                    <div>
                        <strong>{row['activision_id']}</strong>
                        <div class="lb-muted">{row['selection']}</div>
                    </div>
                    <div class="lb-mobile-stat">
                        <strong>{shown_value}</strong>
                        <div class="lb-muted">{label}</div>
                    </div>
                    <div class="lb-mobile-stat">
                        <strong>{int(row.get('wins') or 0)}</strong>
                        <div class="lb-muted">WIN</div>
                    </div>
                    <div class="lb-mobile-stat">
                        <strong>{int(row.get('rating') or 0)}</strong>
                        <div class="lb-muted">RATING</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# ============================================================
# APPROVED PLAYER AREA
# ============================================================

player = get_player(st.session_state.player_id)

# Controllo ad ogni rerun: se il Founder revoca lo stato, l'accesso viene chiuso.
if not player or player[4] != "Approved":
    st.session_state.player_logged_in = False
    st.session_state.player_id = None
    st.warning("Il tuo profilo non risulta più approvato.")
    st.rerun()

player_id = player[1]
player_selection = display_selection(player[3])

st.sidebar.markdown(
    f'<div style="text-align:center"><img src="data:image/png;base64,{LOGO_B64}" '
    'style="width:145px;max-width:90%;"></div>',
    unsafe_allow_html=True,
)
st.sidebar.markdown(f"### 🎮 {player_id}")
st.sidebar.caption(f"Selezione · {player_selection}")
st.sidebar.divider()

player_page = st.sidebar.radio(
        "COMMAND CENTER",
        ["🏠 Home", "🏆 Leaderboard", "📸 Carica Prova", "🔔 Notifiche", "👤 Il mio Profilo", "🪪 Player Card"],
        key="player_navigation_v241",
    )
auto_close_mobile_sidebar("player_navigation_v241", player_page)

if st.sidebar.button("🚪 Logout", use_container_width=True):
    forget_device_script()
    player_logout()

hero()


# ============================================================
# PLAYER HOME
# ============================================================

if player_page == "🏠 Home":
    st.markdown('<div class="ld-section">PLAYER COMMAND CENTER</div>', unsafe_allow_html=True)

    stats = db_query(
        """
        SELECT
          COALESCE(SUM(kills),0),
          COALESCE(SUM(wins),0),
          COALESCE(SUM(matches_played),0),
          COALESCE(SUM(rating_gained),0),
          COALESCE(AVG(COALESCE(placement_score,
              CASE WHEN matches_played > 0 THEN wins * 100.0 / matches_played ELSE 0 END)),0)
        FROM submissions
        WHERE activision_id=? AND status='Approved'
        """,
        (player_id,),
        fetchall=True,
    )[0]

    kills, wins, matches, rating, wr = stats

    st.markdown(
        f"""
        <div class="ld-card">
          <div class="ld-welcome">BENTORNATO, {player_id}</div>
          <div class="ld-muted">Selezione {player_selection} · Profilo ufficiale LAST DEMONS</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💀 Kill", int(kills))
    c2.metric("🏆 Vittorie", int(wins))
    c3.metric("🎯 Partite", int(matches))
    c4.metric("⚡ Win Rate", f"{wr:.1f}%")

    pending_count = db_query(
        "SELECT COUNT(*) FROM submissions WHERE activision_id=? AND status='Pending'",
        (player_id,),
        fetchall=True,
    )[0][0]

    if pending_count:
        st.info(f"Hai {pending_count} prove in attesa di revisione del Founder.")

    unread = db_query(
        "SELECT COUNT(*) FROM notifications WHERE activision_id=? AND is_read=FALSE",
        (player_id,), fetchall=True,
    )[0][0]
    if unread:
        st.warning(f"🔔 Hai {unread} notifiche non lette.")

    news = db_query(
        "SELECT title, body, created_at FROM announcements WHERE is_active=TRUE ORDER BY created_at DESC LIMIT 5",
        fetchall=True,
    ) or []
    if news:
        st.markdown("### 📢 Comunicazioni LAST DEMONS")
        for title, body, created in news:
            with st.container(border=True):
                st.markdown(f"**{title}**")
                st.write(body)
                st.caption(str(created)[:16])


# ============================================================
# PLAYER LEADERBOARD
# ============================================================

elif player_page == "🏆 Leaderboard":
    st.markdown('<div class="ld-section">LEADERBOARD ARENA</div>', unsafe_allow_html=True)

    season_rows = db_query(
        "SELECT id, name, is_active FROM seasons ORDER BY id DESC",
        fetchall=True,
    ) or []
    season_labels = {
        f"{name}{' · ATTIVA' if active else ''}": sid
        for sid, name, active in season_rows
    }
    selected_season_label = st.selectbox("🗓️ Stagione", list(season_labels.keys()))
    selected_season_id = season_labels[selected_season_label]

    month_rows = db_query(
        """
        SELECT DISTINCT month_year
        FROM submissions
        WHERE status='Approved' AND season_id=?
        ORDER BY month_year DESC
        """,
        (selected_season_id,),
        fetchall=True,
    ) or []
    available_months = [m[0] for m in month_rows]
    current_month = datetime.now().strftime("%Y-%m")
    if current_month not in available_months:
        available_months.insert(0, current_month)
    selected_month = st.selectbox("📅 Mese", available_months)

    selection_label = st.radio(
        "Divisione",
        ["Élite", "LD Player"],
        horizontal=True,
        key="leaderboard_division_v24",
    )
    selection = "Academy" if selection_label == "LD Player" else selection_label

    metric_label = st.segmented_control(
        "Modalità classifica",
        ["💀 TOP FRAGGER", "🏆 WIN RATE"],
        default="💀 TOP FRAGGER",
        key="leaderboard_metric_v24",
    )
    metric = "kills" if metric_label == "💀 TOP FRAGGER" else "win_rate"
    if metric == "win_rate":
        st.caption(
            "Win Rate competitivo basato sul piazzamento: "
            "1° 100% · 2° 90% · 3° 83% · 4° 77% · 5° 70% · 6° 64% · "
            "7° 58% · 8° 51% · 9° 45% · 10° 39% · 11° 32% · 12° 26% · "
            "13° 19% · 14° 13% · 15° 6% · 16° 0%."
        )

    data = db_query(
        """
        SELECT p.activision_id,
               p.selection,
               p.profile_image_url,
               COALESCE(SUM(s.kills),0) AS kills,
               COALESCE(SUM(s.wins),0) AS wins,
               COALESCE(SUM(s.matches_played),0) AS matches,
               COALESCE(SUM(s.rating_gained),0) AS rating,
               COALESCE(AVG(COALESCE(s.placement_score,
                   CASE WHEN s.matches_played > 0 THEN s.wins * 100.0 / s.matches_played ELSE 0 END)),0) AS win_rate
        FROM players p
        LEFT JOIN submissions s
          ON s.activision_id=p.activision_id
         AND s.month_year=?
         AND s.status='Approved'
         AND s.season_id=?
        WHERE p.selection=? AND p.status='Approved'
        GROUP BY p.activision_id, p.selection, p.profile_image_url
        HAVING COUNT(s.id) > 0
        """,
        (selected_month, selected_season_id, selection),
        fetchall=True,
    ) or []

    rows = [
        {
            "activision_id": r[0],
            "selection": r[1],
            "avatar": r[2],
            "kills": r[3],
            "wins": r[4],
            "matches": r[5],
            "rating": r[6],
            "win_rate": r[7],
        }
        for r in data
    ]

    # Season leader summary independent of selected month.
    season_summary = db_query(
        """
        SELECT p.activision_id,
               COALESCE(SUM(s.kills),0),
               COALESCE(SUM(s.wins),0),
               COALESCE(SUM(s.matches_played),0),
               COALESCE(AVG(COALESCE(s.placement_score,
                   CASE WHEN s.matches_played > 0 THEN s.wins * 100.0 / s.matches_played ELSE 0 END)),0)
        FROM players p
        JOIN submissions s ON s.activision_id=p.activision_id
        WHERE p.selection=? AND p.status='Approved'
          AND s.status='Approved' AND s.season_id=?
        GROUP BY p.activision_id
        """,
        (selection, selected_season_id),
        fetchall=True,
    ) or []

    if season_summary:
        top_frag = max(season_summary, key=lambda r: r[1])
        wr_candidates = [r for r in season_summary if int(r[3] or 0) > 0]
        top_wr = max(wr_candidates, key=lambda r: float(r[4] or 0)) if wr_candidates else None
        sc1, sc2 = st.columns(2)
        sc1.metric("🔥 Season Kill Leader", top_frag[0], f"{int(top_frag[1])} kill")
        if top_wr:
            sc2.metric(
                "⚡ Season Win Rate Leader",
                top_wr[0],
                f"{float(top_wr[4]):.1f}%",
            )

    render_esports_leaderboard(rows, metric, player_id)


elif player_page == "📸 Carica Prova":
    st.markdown('<div class="ld-section">CARICA PROVA MATCH</div>', unsafe_allow_html=True)

    st.markdown(
        f"""
        <div class="ld-card">
          <div class="ld-welcome">🎮 {player_id}</div>
          <div class="ld-muted">
          La prova verrà associata automaticamente al tuo account.
          Non puoi caricare statistiche per altri player.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("player_proof_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            kills = st.number_input("💀 Kill", min_value=0, step=1, value=0)
        with c2:
            placement = st.selectbox(
                "🏁 Posizionamento team",
                list(range(1, 17)),
                format_func=lambda x: f"{x}° · {PLACEMENT_POINTS[x]:.0f}%"
            )
        matches = 1
        wins = 1 if int(placement) == 1 else 0
        placement_score = calculate_placement_score(placement)
        st.caption(
            f"Win Rate match: {placement_score:.0f}% · "
            f"{'Vittoria' if wins else 'Nessuna vittoria'}"
        )
        multiplier = placement_rating_multiplier(placement)
        preview_base = int(kills) + (int(wins) * 20)
        preview_rating = round(preview_base * multiplier, 1)
        st.caption(
            f"Rating: {preview_base} base × {multiplier:.1f} = {preview_rating:g}"
        )

        uploaded = st.file_uploader(
            "🖼️ Screenshot della prova",
            type=["png", "jpg", "jpeg", "webp"],
        )
        st.caption("📦 Dimensione massima immagine: 50 MB.")

        send = st.form_submit_button(
            "📤 INVIA AL FOUNDER",
            type="primary",
            use_container_width=True,
        )

        if send:
            if int(placement) < 1 or int(placement) > 16:
                st.error("Il posizionamento deve essere compreso tra 1 e 16.")
            elif int(kills) < 0:
                st.error("Le kill non possono essere negative.")
            elif uploaded is None:
                st.error("Carica uno screenshot.")
            elif getattr(uploaded, "size", 0) > MAX_PLAYER_IMAGE_BYTES:
                st.error("L'immagine supera il limite massimo di 50 MB.")
            else:
                try:
                    path = save_proof(uploaded, player_id)
                except Exception as exc:
                    st.error(f"❌ Impossibile caricare la prova: {exc}")
                    st.info("La prova non è stata salvata nel database. Puoi correggere il problema e riprovare.")
                    st.stop()
                rating = calculate_rating(int(kills), int(wins), int(placement))
                month = datetime.now().strftime("%Y-%m")

                db_query(
                    """
                    INSERT INTO submissions
                    (activision_id,kills,wins,rating_gained,photo_path,
                     month_year,status,matches_played,season_id,placement,placement_score)
                    VALUES (?,?,?,?,?,?,'Pending',?,?,?,?)
                    """,
                    (
                        player_id,
                        int(kills),
                        int(wins),
                        rating,
                        path,
                        month,
                        int(matches),
                        (lambda season: season[0] if season else None)(active_season_v241()),
                        int(placement),
                        float(placement_score),
                    ),
                    commit=True,
                )

                notify_founder("proof", "Nuova prova caricata e in attesa di approvazione.", player_id)
                st.success("✅ Prova caricata, in attesa di approvazione.")


# ============================================================
# PLAYER PROFILE
# ============================================================

elif player_page == "🔔 Notifiche":
    st.markdown('<div class="ld-section">NOTIFICHE</div>', unsafe_allow_html=True)
    notes = db_query(
        """
        SELECT id, message, is_read, created_at
        FROM notifications
        WHERE activision_id=?
        ORDER BY created_at DESC
        LIMIT 100
        """,
        (player_id,), fetchall=True,
    ) or []
    if not notes:
        st.info("Nessuna notifica.")
    else:
        for nid, message, is_read, created in notes:
            with st.container(border=True):
                st.markdown(("✓ " if is_read else "🔴 ") + message)
                st.caption(str(created)[:16])
        if st.button("✓ Segna tutte come lette", use_container_width=True):
            db_query(
                "UPDATE notifications SET is_read=TRUE WHERE activision_id=?",
                (player_id,), commit=True,
            )
            st.rerun()


elif player_page == "🪪 Player Card":
    st.markdown('<div class="ld-section">PLAYER CARD CONDIVISIBILE</div>', unsafe_allow_html=True)
    public_player_card(player_id)
    st.info(
        "Per condividere la card, usa il link pubblico della tua app aggiungendo "
        f"`?player={player_id}` alla fine."
    )


elif player_page == "👤 Il mio Profilo":
    st.markdown('<div class="ld-section">IL MIO PROFILO</div>', unsafe_allow_html=True)

    stats = db_query(
        """
        SELECT
          COALESCE(SUM(kills),0),
          COALESCE(SUM(wins),0),
          COALESCE(SUM(matches_played),0),
          COALESCE(SUM(rating_gained),0),
          COALESCE(AVG(COALESCE(placement_score,
              CASE WHEN matches_played > 0 THEN wins * 100.0 / matches_played ELSE 0 END)),0)
        FROM submissions
        WHERE activision_id=? AND status='Approved'
        """,
        (player_id,),
        fetchall=True,
    )[0]

    kills, wins, matches, rating, wr = stats

    # Profilo visuale
    if player[8]:
        st.image(player[8], use_container_width=True)

    identity_left, identity_right = st.columns([1, 4], gap="large")
    with identity_left:
        if player[7]:
            st.image(player[7], width=180)
        else:
            st.markdown("### 👤")
            st.caption("Nessuna foto profilo")
    with identity_right:
        st.subheader(f"🎮 {player_id}")
        st.caption(f"{player[9] or 'Player'} · {player[2]} · Selezione {player_selection}")
        st.write("Personalizza la tua scheda con una foto profilo e un banner.")

    with st.expander("🖼️ Personalizza profilo", expanded=False):
        avatar_file = st.file_uploader(
            "Foto profilo",
            type=["png", "jpg", "jpeg", "webp"],
            key="profile_avatar_upload",
        )
        banner_file = st.file_uploader(
            "Banner profilo",
            type=["png", "jpg", "jpeg", "webp"],
            key="profile_banner_upload",
        )
        st.caption("Consiglio: foto quadrata; banner orizzontale 16:9.")

        if st.button("💾 Salva immagini profilo", type="primary", use_container_width=True):
            if not avatar_file and not banner_file:
                st.warning("Seleziona almeno una nuova immagine.")
            else:
                try:
                    new_avatar = player[7]
                    new_banner = player[8]

                    if avatar_file:
                        new_avatar = save_profile_media(avatar_file, player_id, "avatar")
                    if banner_file:
                        new_banner = save_profile_media(banner_file, player_id, "banner")

                    db_query(
                        "UPDATE players SET profile_image_url=?, banner_url=? WHERE activision_id=?",
                        (new_avatar, new_banner, player_id),
                        commit=True,
                    )

                    if avatar_file and player[7] and player[7] != new_avatar:
                        delete_storage_url(player[7])
                    if banner_file and player[8] and player[8] != new_banner:
                        delete_storage_url(player[8])

                    st.success("Profilo aggiornato.")
                    st.rerun()
                except requests.RequestException:
                    st.error("Errore durante il caricamento delle immagini. Riprova.")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Kill", int(kills))
    c2.metric("Vittorie", int(wins))
    c3.metric("Win Rate", f"{wr:.1f}%")
    c4.metric("Rating", f"{rating:.0f}")

    history = db_query(
        """
        SELECT timestamp,rating_gained,kills,wins,status,placement,placement_score
        FROM submissions
        WHERE activision_id=?
        ORDER BY timestamp ASC
        """,
        (player_id,),
        fetchall=True,
    ) or []

    approved_history = [r for r in history if r[4] == "Approved"]

    if approved_history:
        df = pd.DataFrame(
            approved_history,
            columns=["Data","Rating Guadagnato","Kill","Vittorie","Stato","Piazzamento","Win Rate"],
        )
        df["Data"] = pd.to_datetime(df["Data"])
        df["Rating Guadagnato"] = pd.to_numeric(df["Rating Guadagnato"], errors="coerce").fillna(0.0)
        df["Piazzamento"] = pd.to_numeric(df["Piazzamento"], errors="coerce")
        df["Win Rate"] = pd.to_numeric(df["Win Rate"], errors="coerce")
        df["Win Rate"] = df["Win Rate"].fillna(pd.to_numeric(df["Vittorie"], errors="coerce").fillna(0) * 100.0)
        df["Moltiplicatore"] = df["Piazzamento"].apply(
            lambda p: placement_rating_multiplier(int(p)) if pd.notna(p) else 1.0
        )
        df["Rating Accumulato"] = df["Rating Guadagnato"].cumsum()
        df["Partita"] = range(1, len(df) + 1)
        df["Piazzamento Label"] = df["Piazzamento"].apply(
            lambda p: f"{int(p)}°" if pd.notna(p) else "Storico"
        )

        st.subheader("📈 Progressione Rating")
        current_rating = float(df["Rating Accumulato"].iloc[-1])
        last5 = float(df["Rating Guadagnato"].tail(5).sum())
        previous5 = float(df["Rating Guadagnato"].iloc[-10:-5].sum()) if len(df) > 5 else 0.0
        trend = (last5 - previous5) if len(df) > 5 else None

        p1, p2, p3 = st.columns(3)
        p1.metric("⭐ Rating attuale", f"{current_rating:.1f}")
        p2.metric("🔥 Rating ultime 5", f"+{last5:.1f}")
        p3.metric(
            "📊 Trend ultime 5",
            f"{trend:+.1f}" if trend is not None else "N/D",
            help="Confronto tra il Rating delle ultime 5 partite e quello delle 5 precedenti.",
        )

        progression_chart = (
            alt.Chart(df)
            .mark_line(point=alt.OverlayMarkDef(size=75), strokeWidth=3)
            .encode(
                x=alt.X("Partita:Q", title="Partita", axis=alt.Axis(tickMinStep=1)),
                y=alt.Y("Rating Accumulato:Q", title="Rating cumulativo", scale=alt.Scale(zero=True)),
                tooltip=[
                    alt.Tooltip("Data:T", title="Data", format="%d/%m/%Y %H:%M"),
                    alt.Tooltip("Partita:Q", title="Partita", format=".0f"),
                    alt.Tooltip("Kill:Q", title="Kill", format=".0f"),
                    alt.Tooltip("Piazzamento Label:N", title="Piazzamento"),
                    alt.Tooltip("Win Rate:Q", title="Win Rate %", format=".1f"),
                    alt.Tooltip("Moltiplicatore:Q", title="Moltiplicatore", format=".1f"),
                    alt.Tooltip("Rating Guadagnato:Q", title="Rating guadagnato", format=".1f"),
                    alt.Tooltip("Rating Accumulato:Q", title="Rating totale", format=".1f"),
                ],
            )
            .properties(height=360)
            .interactive()
        )
        st.altair_chart(progression_chart, use_container_width=True)
        st.caption("Ogni punto rappresenta una prova approvata. Passa sopra un punto per vedere i dettagli del match.")

    st.subheader("📋 Storico invii")
    if history:
        df_history = pd.DataFrame(
            history,
            columns=["Data","Rating","Kill","Vittorie","Stato","Piazzamento","Win Rate"],
        )
        st.dataframe(df_history.iloc[::-1], hide_index=True, use_container_width=True)
    else:
        st.info("Non hai ancora inviato prove.")
