import hashlib
import secrets

import mysql.connector

from config import Config

_duration_column_checked = False
_question_attempts_table_checked = False
_question_reports_table_checked = False


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


def ensure_question_attempts_table():
    """Zajistí existenci tabulky question_attempts."""
    global _question_attempts_table_checked
    if _question_attempts_table_checked:
        return

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SHOW TABLES LIKE 'question_attempts';")
        exists = cur.fetchone()
        if not exists:
            cur.execute(
                """
                CREATE TABLE question_attempts (
                    attempt_id INT PRIMARY KEY AUTO_INCREMENT,
                    user_id INT NOT NULL,
                    question_id INT NOT NULL,
                    category_id INT NOT NULL,
                    difficulty_id INT NOT NULL,
                    is_correct TINYINT(1) NOT NULL,
                    mode VARCHAR(20) NOT NULL DEFAULT 'normal',
                    answered_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_attempts_user_question (user_id, question_id),
                    INDEX idx_attempts_user_time (user_id, answered_at),
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                    FOREIGN KEY (question_id) REFERENCES questions(question_id) ON DELETE CASCADE,
                    FOREIGN KEY (category_id) REFERENCES categories(category_id),
                    FOREIGN KEY (difficulty_id) REFERENCES difficulties(difficulty_id)
                );
                """
            )
            conn.commit()
        _question_attempts_table_checked = True
    finally:
        cur.close()
        conn.close()


def ensure_question_reports_table():
    """Zajistí existenci tabulky question_reports."""
    global _question_reports_table_checked
    if _question_reports_table_checked:
        return

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SHOW TABLES LIKE 'question_reports';")
        exists = cur.fetchone()
        if not exists:
            cur.execute(
                """
                CREATE TABLE question_reports (
                    report_id INT PRIMARY KEY AUTO_INCREMENT,
                    question_id INT NOT NULL,
                    user_id INT NOT NULL,
                    reason VARCHAR(60) NOT NULL,
                    note VARCHAR(500),
                    status VARCHAR(20) NOT NULL DEFAULT 'new',
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    resolved_by INT NULL,
                    INDEX idx_reports_status (status),
                    INDEX idx_reports_question (question_id),
                    INDEX idx_reports_user_time (user_id, created_at),
                    FOREIGN KEY (question_id) REFERENCES questions(question_id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                    FOREIGN KEY (resolved_by) REFERENCES users(user_id) ON DELETE SET NULL
                );
                """
            )
            conn.commit()
        _question_reports_table_checked = True
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
    return fetch_all("SELECT category_id, name, description FROM categories ORDER BY name;")


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


def save_question_attempt(user_id, question_id, category_id, difficulty_id, is_correct, mode="normal"):
    """Uloží jednotlivý pokus na otázce (pro trénink chyb i analytiku)."""
    ensure_question_attempts_table()
    sql = """
    INSERT INTO question_attempts (
        user_id, question_id, category_id, difficulty_id, is_correct, mode
    )
    VALUES (%s, %s, %s, %s, %s, %s);
    """
    execute(
        sql,
        (
            user_id,
            question_id,
            category_id,
            difficulty_id,
            1 if is_correct else 0,
            (mode or "normal")[:20],
        ),
    )


def get_training_questions(user_id, category_id, difficulty_id, limit=10):
    """
    Načte otázky pro režim Trénink chyb.

    Vybírá otázky, kde poslední odpověď daného uživatele byla špatně.
    """
    ensure_question_attempts_table()
    sql = """
    SELECT
        q.question_id,
        q.question_text,
        q.answer_a,
        q.answer_b,
        q.answer_c,
        q.answer_d,
        q.correct_answer
    FROM question_attempts qa
    JOIN questions q ON q.question_id = qa.question_id
    JOIN questions_categories qc ON qc.question_id = q.question_id
    WHERE qa.user_id = %s
      AND qa.category_id = %s
      AND qa.difficulty_id = %s
      AND qc.category_id = %s
      AND qa.attempt_id = (
          SELECT qa2.attempt_id
          FROM question_attempts qa2
          WHERE qa2.user_id = qa.user_id
            AND qa2.question_id = qa.question_id
          ORDER BY qa2.answered_at DESC, qa2.attempt_id DESC
          LIMIT 1
      )
      AND qa.is_correct = 0
    ORDER BY qa.answered_at DESC
    LIMIT %s;
    """
    return fetch_all(sql, (user_id, category_id, difficulty_id, category_id, limit))


def create_question_report(question_id, user_id, reason, note=""):
    """Vytvoří hlášení otázky z desktop aplikace."""
    ensure_question_reports_table()
    sql = """
    INSERT INTO question_reports (question_id, user_id, reason, note)
    VALUES (%s, %s, %s, %s);
    """
    clean_reason = (reason or "").strip()[:60]
    clean_note = (note or "").strip()[:500]
    execute(sql, (question_id, user_id, clean_reason, clean_note or None))
