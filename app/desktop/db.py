import hashlib
import secrets
import mysql.connector
from config import Config


def get_connection():
    """
    Vytvoří a vrátí připojení k MySQL databázi
    podle údajů uložených v config.py.
    """
    return mysql.connector.connect(
        host=Config.DB_HOST,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME,
        port=getattr(Config, "DB_PORT", 3306),
    )


def fetch_all(sql, params=()):
    """
    Provede SELECT dotaz a vrátí všechny řádky
    jako seznam slovníků (sloupec -> hodnota).
    """
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        # Uzavření kurzoru a spojení s databází
        cur.close()
        conn.close()


def fetch_one(sql, params=()):
    """
    Provede SELECT dotaz a vrátí právě jeden řádek
    (nebo None, pokud dotaz nic nevrátí).
    """
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(sql, params)
        return cur.fetchone()
    finally:
        cur.close()
        conn.close()


def execute(sql, params=()):
    """
    Provede INSERT / UPDATE / DELETE dotaz.
    Vrací počet ovlivněných řádků.
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
        conn.commit()  # potvrzení změn v databázi
        return cur.rowcount
    finally:
        cur.close()
        conn.close()



# -------------------------
# AUTH (registrace / login)
# -------------------------

def _hash_password(password: str) -> str:
    """
    Vrací řetězec ve formátu: salt$hash
    """
    salt = secrets.token_hex(16)  # 32 hex chars
    digest = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return f"{salt}${digest}"


def _check_password(stored: str, password: str) -> bool:
    """
    stored: salt$hash
    """
    if not stored or "$" not in stored:
        return False
    salt, digest = stored.split("$", 1)
    check = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return secrets.compare_digest(digest, check)


def get_user_by_username(username: str):
    sql = "SELECT user_id, username, password_hash, role FROM users WHERE username = %s;"
    return fetch_one(sql, (username,))


def create_user(username: str, password: str, role: str = "user"):
    """
    Vytvoří uživatele. Username je UNIQUE -> pokud existuje, MySQL vyhodí chybu.
    """
    pwd_hash = _hash_password(password)
    sql = "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s);"
    execute(sql, (username, pwd_hash, role))


def verify_login(username: str, password: str):
    """
    Vrátí user dict (user_id, username, role) pokud login OK, jinak None.
    """
    user = get_user_by_username(username)
    if not user:
        return None
    if not _check_password(user["password_hash"], password):
        return None
    return {"user_id": user["user_id"], "username": user["username"], "role": user["role"]}


# -------------------------
# KVÍZ funkce
# -------------------------

def get_categories():
    return fetch_all("SELECT category_id, name FROM categories ORDER BY name;")


def get_difficulties():
    return fetch_all("SELECT difficulty_id, name FROM difficulties ORDER BY difficulty_id;")


def get_questions(category_id, difficulty_id, limit=10):
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


def save_result(user_id, category_id, difficulty_id, score, total_questions):
    sql = """
    INSERT INTO results (user_id, category_id, difficulty_id, score, total_questions)
    VALUES (%s, %s, %s, %s, %s);
    """
    execute(sql, (user_id, category_id, difficulty_id, score, total_questions))
