import hashlib
import secrets

import mysql.connector

from config import Config

_duration_column_checked = False


# ---------------------------------------------------------------------------
# Obecná DB vrstva pro desktop část
# ---------------------------------------------------------------------------

def get_connection():
    """Vytvoří připojení k MySQL podle hodnot v config.py."""
    return mysql.connector.connect(
        host=Config.DB_HOST,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME,
        port=getattr(Config, "DB_PORT", 3306),
    )


def fetch_all(sql, params=()):
    """Provede SELECT a vrátí všechny řádky jako list slovníků."""
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


def fetch_one(sql, params=()):
    """Provede SELECT a vrátí jeden řádek nebo None."""
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(sql, params)
        return cur.fetchone()
    finally:
        cur.close()
        conn.close()


def execute(sql, params=()):
    """Provede INSERT/UPDATE/DELETE a vrátí počet ovlivněných řádků."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
        conn.commit()
        return cur.rowcount
    finally:
        cur.close()
        conn.close()


def ensure_results_duration_column():
    """Zajistí existenci sloupce duration_seconds v tabulce results."""
    global _duration_column_checked
    if _duration_column_checked:
        return

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SHOW COLUMNS FROM results LIKE 'duration_seconds';")
        exists = cur.fetchone()
        if not exists:
            cur.execute("ALTER TABLE results ADD COLUMN duration_seconds INT NULL AFTER total_questions;")
            conn.commit()
        _duration_column_checked = True
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------------------------
# Registrace / login
# ---------------------------------------------------------------------------

def _hash_password(password: str) -> str:
    """Vytvoří hash hesla ve formátu salt$sha256(salt+password)."""
    salt = secrets.token_hex(16)
    digest = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return f"{salt}${digest}"


def _check_password(stored: str, password: str) -> bool:
    """Ověří heslo proti uloženému hash řetězci."""
    if not stored or "$" not in stored:
        return False
    salt, digest = stored.split("$", 1)
    check = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return secrets.compare_digest(digest, check)


def get_user_by_username(username: str):
    """Vrátí uživatele podle uživatelského jména."""
    sql = "SELECT user_id, username, password_hash, role FROM users WHERE username = %s;"
    return fetch_one(sql, (username,))


def create_user(username: str, password: str, role: str = "user"):
    """Vytvoří nového uživatele. Username je v DB unikátní."""
    pwd_hash = _hash_password(password)
    sql = "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s);"
    execute(sql, (username, pwd_hash, role))


def verify_login(username: str, password: str):
    """Vrátí user dict při úspěchu, jinak None."""
    user = get_user_by_username(username)
    if not user:
        return None
    if not _check_password(user["password_hash"], password):
        return None
    return {"user_id": user["user_id"], "username": user["username"], "role": user["role"]}


# ---------------------------------------------------------------------------
# Kvízové funkce
# ---------------------------------------------------------------------------

def get_categories():
    """Vrátí všechny kategorie seřazené podle názvu."""
    return fetch_all("SELECT category_id, name FROM categories ORDER BY name;")


def get_difficulties():
    """Vrátí všechny obtížnosti."""
    return fetch_all("SELECT difficulty_id, name FROM difficulties ORDER BY difficulty_id;")


def get_questions(category_id, difficulty_id, limit=10):
    """Načte náhodný výběr otázek pro zvolenou kategorii a obtížnost."""
    sql = """
    SELECT
        q.question_id,
        q.question_text,
        q.answer_a,
        q.answer_b,
        q.answer_c,
        q.answer_d,
        q.correct_answer
    FROM questions q
    JOIN questions_categories qc ON qc.question_id = q.question_id
    WHERE qc.category_id = %s
      AND q.difficulty_id = %s
    ORDER BY RAND()
    LIMIT %s;
    """
    return fetch_all(sql, (category_id, difficulty_id, limit))


def save_result(user_id, category_id, difficulty_id, score, total_questions, duration_seconds=None):
    """Uloží výsledek odehraného kvízu do tabulky results včetně času."""
    ensure_results_duration_column()
    sql = """
    INSERT INTO results (user_id, category_id, difficulty_id, score, total_questions, duration_seconds)
    VALUES (%s, %s, %s, %s, %s, %s);
    """
    execute(sql, (user_id, category_id, difficulty_id, score, total_questions, duration_seconds))
