import mysql.connector
from flask import current_app


def get_connection():
    """
    Vytvoří připojení k MySQL podle Flask configu (config.py)
    Očekává klíče: DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, (volitelně DB_PORT)
    """
    cfg = current_app.config
    return mysql.connector.connect(
        host=cfg["DB_HOST"],
        user=cfg["DB_USER"],
        password=cfg["DB_PASSWORD"],
        database=cfg["DB_NAME"],
        port=cfg.get("DB_PORT", 3306),
    )


def fetch_one(sql: str, params: tuple = ()):
    # Vrátí jeden řádek jako dict (nebo None)
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(sql, params)
        return cur.fetchone()
    finally:
        cur.close()
        conn.close()


def fetch_all(sql: str, params: tuple = ()):
    # Vrátí všechny řádky jako list[dict]
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


def execute(sql: str, params: tuple = ()):
    # Pro INSERT/UPDATE/DELETE. Vrátí počet ovlivněných řádků 
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
        conn.commit()
        return cur.rowcount
    finally:
        cur.close()
        conn.close()


# -------------------------
# Konkretni funkce pro projekt
# -------------------------

def get_leaderboard(limit: int = 20):
    """
    Vrátí leaderboard: username, category, difficulty, score, total_questions, played_at
    """
    sql = """
    SELECT
        u.username,
        c.name AS category,
        d.name AS difficulty,
        r.score,
        r.total_questions,
        r.played_at
    FROM results r
    JOIN users u ON u.user_id = r.user_id
    JOIN categories c ON c.category_id = r.category_id
    JOIN difficulties d ON d.difficulty_id = r.difficulty_id
    ORDER BY r.score DESC, r.played_at DESC
    LIMIT %s;
    """
    return fetch_all(sql, (limit,))
