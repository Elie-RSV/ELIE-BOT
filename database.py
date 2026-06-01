"""
Gestion de la base de données SQLite
Stockage : utilisateurs, trades, sessions journalières
"""
import sqlite3
import json
from datetime import datetime, date
from typing import Optional, List, Dict

DB_PATH = "rsv_bot.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """Initialise toutes les tables au démarrage"""
    conn = get_connection()
    c = conn.cursor()

    # Table utilisateurs
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id     INTEGER PRIMARY KEY,
            username    TEXT,
            role        TEXT DEFAULT 'subscriber',  -- 'admin' ou 'subscriber'
            capital     REAL DEFAULT 0,
            is_active   INTEGER DEFAULT 1,
            added_at    TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Table trades
    c.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            date        TEXT,
            pair        TEXT,
            direction   TEXT,
            entry       REAL,
            tp          REAL,
            sl          REAL,
            lot         REAL,
            rr          REAL,
            score       INTEGER,
            timeframe   TEXT,
            status      TEXT DEFAULT 'open',  -- 'open', 'win', 'loss', 'be'
            pnl         REAL DEFAULT 0,
            opened_at   TEXT DEFAULT CURRENT_TIMESTAMP,
            closed_at   TEXT
        )
    """)

    # Table sessions journalières
    c.execute("""
        CREATE TABLE IF NOT EXISTS daily_sessions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            date            TEXT UNIQUE,
            trades_count    INTEGER DEFAULT 0,
            losses_count    INTEGER DEFAULT 0,
            wins_count      INTEGER DEFAULT 0,
            total_pnl       REAL DEFAULT 0,
            is_active       INTEGER DEFAULT 1,
            notes           TEXT DEFAULT ''
        )
    """)

    # Table capital par utilisateur
    c.execute("""
        CREATE TABLE IF NOT EXISTS user_capital (
            user_id         INTEGER PRIMARY KEY,
            capital         REAL DEFAULT 0,
            profit_pct      REAL DEFAULT 0,
            updated_at      TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    print("✅ Base de données initialisée")


# ============================================================
# GESTION UTILISATEURS
# ============================================================

def add_user(user_id: int, username: str, role: str = "subscriber"):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT OR IGNORE INTO users (user_id, username, role)
        VALUES (?, ?, ?)
    """, (user_id, username, role))
    conn.commit()
    conn.close()


def remove_user(user_id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def get_all_users() -> List[Dict]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE is_active = 1")
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_user(user_id: int) -> Optional[Dict]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def user_exists(user_id: int) -> bool:
    return get_user(user_id) is not None


# ============================================================
# GESTION CAPITAL
# ============================================================

def set_user_capital(user_id: int, capital: float):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO user_capital (user_id, capital, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
    """, (user_id, capital))
    conn.commit()
    conn.close()


def get_user_capital(user_id: int) -> float:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT capital FROM user_capital WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row["capital"] if row else 0.0


def get_user_profit_pct(user_id: int) -> float:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT profit_pct FROM user_capital WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row["profit_pct"] if row else 0.0


def update_user_profit(user_id: int, pnl: float):
    capital = get_user_capital(user_id)
    if capital > 0:
        profit_pct = (pnl / capital) * 100
        conn = get_connection()
        c = conn.cursor()
        c.execute("""
            UPDATE user_capital
            SET profit_pct = profit_pct + ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (profit_pct, user_id))
        conn.commit()
        conn.close()


# ============================================================
# GESTION TRADES
# ============================================================

def save_trade(trade_data: Dict) -> int:
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO trades (date, pair, direction, entry, tp, sl, lot, rr, score, timeframe)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        trade_data["date"],
        trade_data["pair"],
        trade_data["direction"],
        trade_data["entry"],
        trade_data["tp"],
        trade_data["sl"],
        trade_data["lot"],
        trade_data["rr"],
        trade_data["score"],
        trade_data["timeframe"]
    ))
    trade_id = c.lastrowid
    conn.commit()
    conn.close()
    return trade_id


def update_trade_status(trade_id: int, status: str, pnl: float = 0):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        UPDATE trades
        SET status = ?, pnl = ?, closed_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (status, pnl, trade_id))
    conn.commit()
    conn.close()


def get_trade(trade_id: int) -> Optional[Dict]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM trades WHERE id = ?", (trade_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def get_open_trades() -> List[Dict]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM trades WHERE status = 'open'")
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_today_trades() -> List[Dict]:
    today = date.today().isoformat()
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM trades WHERE date = ?", (today,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_week_trades() -> List[Dict]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT * FROM trades
        WHERE date >= date('now', '-7 days')
        ORDER BY opened_at DESC
    """)
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ============================================================
# GESTION SESSION JOURNALIÈRE
# ============================================================

def get_today_session() -> Dict:
    today = date.today().isoformat()
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM daily_sessions WHERE date = ?", (today,))
    row = c.fetchone()
    if not row:
        c.execute("""
            INSERT INTO daily_sessions (date) VALUES (?)
        """, (today,))
        conn.commit()
        c.execute("SELECT * FROM daily_sessions WHERE date = ?", (today,))
        row = c.fetchone()
    conn.close()
    return dict(row)


def update_session(trades_count: int = None, losses_count: int = None,
                   wins_count: int = None, total_pnl: float = None,
                   is_active: bool = None, notes: str = None):
    today = date.today().isoformat()
    session = get_today_session()
    conn = get_connection()
    c = conn.cursor()

    updates = []
    values = []

    if trades_count is not None:
        updates.append("trades_count = ?")
        values.append(trades_count)
    if losses_count is not None:
        updates.append("losses_count = ?")
        values.append(losses_count)
    if wins_count is not None:
        updates.append("wins_count = ?")
        values.append(wins_count)
    if total_pnl is not None:
        updates.append("total_pnl = total_pnl + ?")
        values.append(total_pnl)
    if is_active is not None:
        updates.append("is_active = ?")
        values.append(1 if is_active else 0)
    if notes is not None:
        updates.append("notes = ?")
        values.append(notes)

    if updates:
        values.append(today)
        c.execute(f"""
            UPDATE daily_sessions SET {', '.join(updates)} WHERE date = ?
        """, values)
        conn.commit()
    conn.close()


def is_session_active() -> bool:
    session = get_today_session()
    return bool(session["is_active"])
