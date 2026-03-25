import csv
import hashlib
import secrets
from datetime import datetime
from io import StringIO

import mysql.connector
from flask import current_app

_duration_column_checked = False


# ---------------------------------------------------------------------------
# Obecné DB utility
# ---------------------------------------------------------------------------

def get_connection():
    """Vrátí nové připojení k MySQL podle konfigurace Flask aplikace."""
    cfg = current_app.config
    return mysql.connector.connect(
        host=cfg["DB_HOST"],
        user=cfg["DB_USER"],
        password=cfg["DB_PASSWORD"],
        database=cfg["DB_NAME"],
        port=cfg.get("DB_PORT", 3306),
    )


def fetch_one(sql: str, params: tuple = ()):
    """Provede SELECT a vrátí jeden řádek jako dict nebo None."""
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(sql, params)
        return cur.fetchone()
    finally:
        cur.close()
        conn.close()


def fetch_all(sql: str, params: tuple = ()):
    """Provede SELECT a vrátí všechny řádky jako list[dict]."""
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


def execute(sql: str, params: tuple = ()):
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
# Auth helpery (stejný formát hash jako desktop: salt$sha256)
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """Vytvoří hash hesla ve formátu salt$hash."""
    salt = secrets.token_hex(16)
    digest = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return f"{salt}${digest}"


def check_password(stored: str, password: str) -> bool:
    """Ověří heslo proti uložené hodnotě ve formátu salt$hash."""
    if not stored or "$" not in stored:
        return False
    salt, digest = stored.split("$", 1)
    check = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return secrets.compare_digest(digest, check)


def get_user_by_username(username: str):
    """Vrátí uživatele podle username."""
    sql = "SELECT user_id, username, password_hash, role, created_at FROM users WHERE username = %s;"
    return fetch_one(sql, (username,))


def get_user_by_id(user_id: int):
    """Vrátí uživatele podle ID."""
    sql = "SELECT user_id, username, role, created_at FROM users WHERE user_id = %s;"
    return fetch_one(sql, (user_id,))


def verify_login(username: str, password: str):
    """Vrátí user dict (bez password_hash), pokud login proběhne úspěšně."""
    user = get_user_by_username(username)
    if not user:
        return None
    if not check_password(user["password_hash"], password):
        return None
    return {
        "user_id": user["user_id"],
        "username": user["username"],
        "role": user["role"],
    }


def create_user(username: str, password: str, role: str = "user"):
    """Vytvoří uživatele pro web registraci."""
    pwd_hash = hash_password(password)
    sql = "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s);"
    return execute(sql, (username, pwd_hash, role))


# ---------------------------------------------------------------------------
# Referenční data
# ---------------------------------------------------------------------------

def get_categories():
    """Vrátí seznam kategorií seřazený podle názvu."""
    return fetch_all("SELECT category_id, name FROM categories ORDER BY name;")


def get_categories_with_stats():
    """Vrátí kategorie včetně počtu navázaných otázek."""
    sql = """
    SELECT
        c.category_id,
        c.name,
        c.description,
        COUNT(qc.question_id) AS question_count
    FROM categories c
    LEFT JOIN questions_categories qc ON qc.category_id = c.category_id
    GROUP BY c.category_id, c.name, c.description
    ORDER BY c.name;
    """
    return fetch_all(sql)


def create_category(name: str, description: str = ""):
    """Vytvoří novou kategorii."""
    sql = "INSERT INTO categories (name, description) VALUES (%s, %s);"
    return execute(sql, (name, description or None))


def delete_category(category_id: int):
    """Smaže kategorii podle ID."""
    sql = "DELETE FROM categories WHERE category_id = %s;"
    return execute(sql, (category_id,))


def get_difficulties():
    """Vrátí seznam obtížností seřazený podle ID."""
    return fetch_all("SELECT difficulty_id, name FROM difficulties ORDER BY difficulty_id;")


def get_users_simple():
    """Vrátí stručný seznam uživatelů pro filtry a administraci."""
    sql = "SELECT user_id, username, role, created_at FROM users ORDER BY username;"
    return fetch_all(sql)


def update_user_username(user_id: int, new_username: str):
    """Přejmenuje uživatele podle ID."""
    sql = "UPDATE users SET username = %s WHERE user_id = %s;"
    return execute(sql, (new_username, user_id))


def update_user_password(user_id: int, new_password: str):
    """Změní heslo uživatele (uloží nový hash)."""
    new_hash = hash_password(new_password)
    sql = "UPDATE users SET password_hash = %s WHERE user_id = %s;"
    return execute(sql, (new_hash, user_id))


def delete_user_by_id(user_id: int):
    """Smaže uživatele podle ID."""
    sql = "DELETE FROM users WHERE user_id = %s;"
    return execute(sql, (user_id,))


# ---------------------------------------------------------------------------
# Otázky - CRUD pro admin web
# ---------------------------------------------------------------------------

def list_questions(search: str = "", category_id: int | None = None, difficulty_id: int | None = None):
    """Vrátí seznam otázek s napojenou kategorií a obtížností."""
    conditions = []
    params = []

    if search:
        conditions.append("q.question_text LIKE %s")
        params.append(f"%{search}%")
    if category_id:
        conditions.append("qc.category_id = %s")
        params.append(category_id)
    if difficulty_id:
        conditions.append("q.difficulty_id = %s")
        params.append(difficulty_id)

    where_sql = ""
    if conditions:
        where_sql = "WHERE " + " AND ".join(conditions)

    sql = f"""
    SELECT
        q.question_id,
        q.question_text,
        q.answer_a,
        q.answer_b,
        q.answer_c,
        q.answer_d,
        q.correct_answer,
        q.difficulty_id,
        d.name AS difficulty,
        qc.category_id,
        c.name AS category,
        q.created_at
    FROM questions q
    JOIN difficulties d ON d.difficulty_id = q.difficulty_id
    LEFT JOIN questions_categories qc ON qc.question_id = q.question_id
    LEFT JOIN categories c ON c.category_id = qc.category_id
    {where_sql}
    ORDER BY q.question_id DESC;
    """
    return fetch_all(sql, tuple(params))


def get_question_by_id(question_id: int):
    """Vrátí detail jedné otázky včetně navázané kategorie."""
    sql = """
    SELECT
        q.question_id,
        q.question_text,
        q.answer_a,
        q.answer_b,
        q.answer_c,
        q.answer_d,
        q.correct_answer,
        q.difficulty_id,
        qc.category_id
    FROM questions q
    LEFT JOIN questions_categories qc ON qc.question_id = q.question_id
    WHERE q.question_id = %s;
    """
    return fetch_one(sql, (question_id,))


def create_question(payload: dict, category_id: int, created_by: int | None = None):
    """Vytvoří otázku a naváže ji na jednu kategorii (M:N tabulka)."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO questions (
                question_text, answer_a, answer_b, answer_c, answer_d,
                correct_answer, difficulty_id, created_by
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
            """,
            (
                payload["question_text"],
                payload["answer_a"],
                payload["answer_b"],
                payload["answer_c"],
                payload["answer_d"],
                payload["correct_answer"],
                payload["difficulty_id"],
                created_by,
            ),
        )
        question_id = cur.lastrowid

        cur.execute(
            "INSERT INTO questions_categories (question_id, category_id) VALUES (%s, %s);",
            (question_id, category_id),
        )

        conn.commit()
        return question_id
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def create_questions_bulk(payloads: list[dict], created_by: int | None = None):
    """
    Vytvoří více otázek v jedné transakci.

    Každý payload musí obsahovat:
    question_text, answer_a, answer_b, answer_c, answer_d,
    correct_answer, difficulty_id, category_id
    """
    if not payloads:
        return 0

    conn = get_connection()
    cur = conn.cursor()
    try:
        for payload in payloads:
            cur.execute(
                """
                INSERT INTO questions (
                    question_text, answer_a, answer_b, answer_c, answer_d,
                    correct_answer, difficulty_id, created_by
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                """,
                (
                    payload["question_text"],
                    payload["answer_a"],
                    payload["answer_b"],
                    payload["answer_c"],
                    payload["answer_d"],
                    payload["correct_answer"],
                    payload["difficulty_id"],
                    created_by,
                ),
            )
            question_id = cur.lastrowid

            cur.execute(
                "INSERT INTO questions_categories (question_id, category_id) VALUES (%s, %s);",
                (question_id, payload["category_id"]),
            )

        conn.commit()
        return len(payloads)
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def update_question(question_id: int, payload: dict, category_id: int):
    """Upraví otázku a přepíše její kategorii."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE questions
            SET question_text = %s,
                answer_a = %s,
                answer_b = %s,
                answer_c = %s,
                answer_d = %s,
                correct_answer = %s,
                difficulty_id = %s
            WHERE question_id = %s;
            """,
            (
                payload["question_text"],
                payload["answer_a"],
                payload["answer_b"],
                payload["answer_c"],
                payload["answer_d"],
                payload["correct_answer"],
                payload["difficulty_id"],
                question_id,
            ),
        )

        # V MVP držíme jednu kategorii, proto nejdřív smažeme starou vazbu.
        cur.execute("DELETE FROM questions_categories WHERE question_id = %s;", (question_id,))
        cur.execute(
            "INSERT INTO questions_categories (question_id, category_id) VALUES (%s, %s);",
            (question_id, category_id),
        )

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def delete_question(question_id: int):
    """Smaže otázku. Vazby v questions_categories odstraní ON DELETE CASCADE."""
    return execute("DELETE FROM questions WHERE question_id = %s;", (question_id,))


# ---------------------------------------------------------------------------
# Výsledky, leaderboard, statistiky
# ---------------------------------------------------------------------------

def _build_results_where(filters: dict):
    """Sestaví SQL WHERE část pro filtrování výsledků."""
    conditions = []
    params = []

    if filters.get("username"):
        conditions.append("u.username LIKE %s")
        params.append(f"%{filters['username']}%")

    if filters.get("category_id"):
        conditions.append("r.category_id = %s")
        params.append(filters["category_id"])

    if filters.get("difficulty_id"):
        conditions.append("r.difficulty_id = %s")
        params.append(filters["difficulty_id"])

    if filters.get("date_from"):
        conditions.append("DATE(r.played_at) >= %s")
        params.append(filters["date_from"])

    if filters.get("date_to"):
        conditions.append("DATE(r.played_at) <= %s")
        params.append(filters["date_to"])

    where_sql = ""
    if conditions:
        where_sql = "WHERE " + " AND ".join(conditions)

    return where_sql, params


def get_filtered_results(filters: dict | None = None, order: str = "score_desc", limit: int | None = 200):
    """Vrátí výsledky s JOIN na users/categories/difficulties podle filtrů."""
    ensure_results_duration_column()
    safe_order = {
        "score_desc": "r.score DESC, r.played_at DESC",
        "score_asc": "r.score ASC, r.played_at DESC",
        "newest": "r.played_at DESC",
        "oldest": "r.played_at ASC",
        "speedrun": (
            "r.category_id ASC, "
            "r.difficulty_id ASC, "
            "ROUND((r.score / NULLIF(r.total_questions, 0)) * 100, 2) DESC, "
            "r.score DESC, "
            "r.duration_seconds IS NULL ASC, "
            "r.duration_seconds ASC, "
            "r.played_at ASC"
        ),
    }.get(order, "r.score DESC, r.played_at DESC")

    where_sql, params = _build_results_where(filters or {})

    sql = f"""
    SELECT
        r.result_id,
        u.username,
        c.name AS category,
        d.name AS difficulty,
        r.score,
        r.total_questions,
        r.duration_seconds,
        r.played_at,
        ROUND((r.score / NULLIF(r.total_questions, 0)) * 100, 2) AS success_pct
    FROM results r
    JOIN users u ON u.user_id = r.user_id
    JOIN categories c ON c.category_id = r.category_id
    JOIN difficulties d ON d.difficulty_id = r.difficulty_id
    {where_sql}
    ORDER BY {safe_order}
    """

    if limit is not None:
        sql += " LIMIT %s"
        params.append(limit)

    sql += ";"
    return fetch_all(sql, tuple(params))


def get_leaderboard(limit: int = 20):
    """Kompatibilní helper pro původní leaderboard route."""
    return get_filtered_results(filters={}, order="score_desc", limit=limit)


def get_recent_results(limit: int = 8):
    """Vrátí poslední výsledky pro úvodní stránku."""
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
    ORDER BY r.played_at DESC
    LIMIT %s;
    """
    return fetch_all(sql, (limit,))


def delete_results_by_ids(result_ids: list[int]):
    """Smaže výsledky podle seznamu ID (bulk delete přes checkboxy)."""
    if not result_ids:
        return 0

    placeholders = ", ".join(["%s"] * len(result_ids))
    sql = f"DELETE FROM results WHERE result_id IN ({placeholders});"
    return execute(sql, tuple(result_ids))


def get_stats_by_category():
    """Agregace pro graf: počet pokusů a průměrná úspěšnost podle kategorií."""
    sql = """
    SELECT
        c.name,
        COUNT(r.result_id) AS attempts,
        ROUND(AVG((r.score / NULLIF(r.total_questions, 0)) * 100), 2) AS avg_success
    FROM categories c
    LEFT JOIN results r ON r.category_id = c.category_id
    GROUP BY c.category_id, c.name
    ORDER BY attempts DESC, c.name;
    """
    return fetch_all(sql)


def get_stats_by_difficulty():
    """Agregace pro graf: úspěšnost, speedrun čas a podíl perfektních výsledků."""
    ensure_results_duration_column()
    sql = """
    SELECT
        d.name,
        COUNT(r.result_id) AS attempts,
        ROUND(AVG((r.score / NULLIF(r.total_questions, 0)) * 100), 2) AS avg_success,
        ROUND(AVG(r.duration_seconds), 2) AS avg_duration_seconds,
        ROUND(
            (SUM(CASE WHEN r.score = r.total_questions THEN 1 ELSE 0 END) / NULLIF(COUNT(r.result_id), 0)) * 100,
            2
        ) AS perfect_pct
    FROM difficulties d
    LEFT JOIN results r ON r.difficulty_id = d.difficulty_id
    GROUP BY d.difficulty_id, d.name
    ORDER BY d.difficulty_id;
    """
    return fetch_all(sql)


def get_top_users(limit: int = 10):
    """Vrátí TOP hráče podle průměrné úspěšnosti a počtu pokusů."""
    sql = """
    SELECT
        u.username,
        COUNT(r.result_id) AS attempts,
        ROUND(AVG((r.score / NULLIF(r.total_questions, 0)) * 100), 2) AS avg_success
    FROM users u
    JOIN results r ON r.user_id = u.user_id
    GROUP BY u.user_id, u.username
    HAVING attempts > 0
    ORDER BY avg_success DESC, attempts DESC, u.username
    LIMIT %s;
    """
    return fetch_all(sql, (limit,))


# ---------------------------------------------------------------------------
# CSV import/export helpery
# ---------------------------------------------------------------------------

def import_results_csv(file_storage):
    """
    Importuje výsledky z CSV souboru.

    Očekávané sloupce:
    username,category,difficulty,score,total_questions,played_at(optional),duration_seconds(optional)

    Import je transakční: při chybě se neuloží nic.
    """
    ensure_results_duration_column()

    if not file_storage or not file_storage.filename:
        raise ValueError("Nebyl vybrán žádný CSV soubor.")

    raw = file_storage.stream.read()
    if not raw:
        raise ValueError("CSV soubor je prázdný.")

    try:
        decoded = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV musí být v UTF-8 kódování.") from exc

    reader = csv.DictReader(StringIO(decoded))
    required = {"username", "category", "difficulty", "score", "total_questions"}

    if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
        missing = sorted(required - set(reader.fieldnames or []))
        raise ValueError(f"CSV nemá povinné sloupce: {', '.join(missing)}")

    rows = list(reader)
    if not rows:
        raise ValueError("CSV neobsahuje žádné datové řádky.")

    user_map = {row["username"]: row["user_id"] for row in fetch_all("SELECT user_id, username FROM users;")}
    category_map = {row["name"]: row["category_id"] for row in get_categories()}
    difficulty_map = {row["name"]: row["difficulty_id"] for row in get_difficulties()}

    prepared = []
    errors = []

    for idx, row in enumerate(rows, start=2):
        username = (row.get("username") or "").strip()
        category = (row.get("category") or "").strip()
        difficulty = (row.get("difficulty") or "").strip()

        if username not in user_map:
            errors.append(f"Řádek {idx}: neznámý uživatel '{username}'.")
            continue
        if category not in category_map:
            errors.append(f"Řádek {idx}: neznámá kategorie '{category}'.")
            continue
        if difficulty not in difficulty_map:
            errors.append(f"Řádek {idx}: neznámá obtížnost '{difficulty}'.")
            continue

        try:
            score = int((row.get("score") or "").strip())
            total = int((row.get("total_questions") or "").strip())
        except ValueError:
            errors.append(f"Řádek {idx}: score/total_questions musí být celá čísla.")
            continue

        if total <= 0:
            errors.append(f"Řádek {idx}: total_questions musí být > 0.")
            continue
        if score < 0 or score > total:
            errors.append(f"Řádek {idx}: score musí být v rozsahu 0..total_questions.")
            continue

        played_at_raw = (row.get("played_at") or "").strip()
        if played_at_raw:
            try:
                played_at = datetime.fromisoformat(played_at_raw.replace("Z", "+00:00"))
                played_at_value = played_at.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                errors.append(
                    f"Řádek {idx}: played_at musí být ve formátu ISO (např. 2026-03-25T14:30:00)."
                )
                continue
        else:
            played_at_value = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        duration_raw = (row.get("duration_seconds") or "").strip()
        if duration_raw:
            try:
                duration_value = int(duration_raw)
            except ValueError:
                errors.append(f"Řádek {idx}: duration_seconds musí být celé číslo.")
                continue
            if duration_value < 0:
                errors.append(f"Řádek {idx}: duration_seconds musí být >= 0.")
                continue
        else:
            duration_value = None

        prepared.append(
            (
                user_map[username],
                category_map[category],
                difficulty_map[difficulty],
                score,
                total,
                duration_value,
                played_at_value,
            )
        )

    if errors:
        preview = " ".join(errors[:4])
        if len(errors) > 4:
            preview += f" (a dalších {len(errors) - 4} chyb)"
        raise ValueError(preview)

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.executemany(
            """
            INSERT INTO results (
                user_id, category_id, difficulty_id,
                score, total_questions, duration_seconds, played_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s);
            """,
            prepared,
        )
        conn.commit()
        return len(prepared)
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
