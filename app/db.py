import csv
# `csv` je součást standardní knihovny Pythonu (není to váš vlastní soubor).
# `hashlib` je standardní knihovna Pythonu (nástroje pro hashování).
import hashlib
# `secrets` je standardní knihovna Pythonu pro bezpečné náhodné hodnoty.
import secrets
# `datetime` (standardní knihovna) pracuje s datem a časem.
from datetime import datetime
# `StringIO` (standardní knihovna) umožní pracovat s textem jako se "souborovým proudem".
from io import StringIO

import mysql.connector
from flask import current_app

# `current_app` je z Flasku (také externí balíček v `site-packages/flask/...`).
# Používáme ho, protože obsahuje nastavení aplikace (včetně údajů k DB).
# `current_app` funguje jen uvnitř Flask kontextu (např. při zpracování HTTP požadavku).

# Tyto proměnné si pamatují, jestli jsme už při běhu aplikace kontrolovali
# konkrétní sloupec/tabulku. Důvod: nechceme stejnou kontrolu dělat pořád dokola.
_duration_column_checked = False
_profile_title_column_checked = False
_question_attempts_table_checked = False
_question_reports_table_checked = False


# ---------------------------------------------------------------------------
# Obecné DB utility
# ---------------------------------------------------------------------------

def get_connection():
    # Tato funkce vytvoří nové spojení s databází MySQL.
    # Proč to máme v samostatné funkci: aby se stejné kroky neopakovaly všude v kódu.
    cfg = current_app.config
    # `cfg` je slovník s nastavením Flask aplikace (např. DB_HOST, DB_USER...).
    # Pokud by některý klíč v configu chyběl, Python tady vyhodí chybu `KeyError`,
    # což je dobře: hned poznáme, že konfigurace není kompletní.
    return mysql.connector.connect(
        # Tady předáváme jednotlivé hodnoty z konfigurace databázovému konektoru.
        host=cfg["DB_HOST"],
        user=cfg["DB_USER"],
        password=cfg["DB_PASSWORD"],
        database=cfg["DB_NAME"],
        # Pokud v konfiguraci není DB_PORT, použije se výchozí port 3306.
        port=cfg.get("DB_PORT", 3306),
    )


def fetch_one(sql: str, params: tuple = ()):
    # Tato funkce spustí SQL dotaz typu SELECT a vrátí právě jeden řádek.
    # Když nic nenajde, vrátí `None`.
    conn = get_connection()
    # `dictionary=True` znamená, že řádek dostaneme jako slovník:
    # například {"user_id": 1, "username": "admin"}.
    cur = conn.cursor(dictionary=True)
    try:
        # SQL dotaz posíláme bezpečně přes parametry (`%s` + tuple), ne skládáním textu.
        # Důvod: předcházíme SQL injection a zároveň nemusíme ručně řešit escapování uvozovek.
        cur.execute(sql, params)
        # `fetchone()` vrátí první nalezený řádek (slovník), nebo `None`, když nic nenašlo.
        return cur.fetchone()
    finally:
        # `finally` se spustí vždy (i při chybě), takže se připojení vždy korektně zavře.
        cur.close()
        conn.close()


def fetch_all(sql: str, params: tuple = ()):
    # Tato varianta vrací všechny nalezené řádky (seznam slovníků).
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(sql, params)
        # `fetchall()` vrací list (seznam) řádků. Když není nic nalezeno, vrátí prázdný list `[]`.
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


def execute(sql: str, params: tuple = ()):
    # Tato funkce je pro změnové dotazy (INSERT/UPDATE/DELETE).
    # Vrací počet řádků, které se reálně změnily.
    conn = get_connection()
    # Zde nepotřebujeme slovníky, protože nečteme data zpět.
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
        # U změn je nutné zavolat `commit()`, jinak by se změna neuložila natrvalo.
        conn.commit()
        # `rowcount` = kolik řádků DB opravdu ovlivnila.
        # Pozor: u některých typů dotazů může DB vracet speciální hodnoty (závisí na driveru/DB).
        return cur.rowcount
    finally:
        cur.close()
        conn.close()


def ensure_results_duration_column():
    # Funkce hlídá, aby v tabulce `results` existoval sloupec `duration_seconds`.
    # Hodí se to při postupném rozšiřování projektu (migrace schématu).
    global _duration_column_checked
    # `global` říká: pracujeme s proměnnou definovanou nahoře v souboru, ne s lokální kopií.
    # Pokud už kontrola v tomto běhu proběhla, rovnou skončíme.
    if _duration_column_checked:
        return

    conn = get_connection()
    cur = conn.cursor()
    try:
        # Ověříme, zda sloupec existuje.
        cur.execute("SHOW COLUMNS FROM results LIKE 'duration_seconds';")
        exists = cur.fetchone()
        # Pokud neexistuje, přidáme ho.
        if not exists:
            cur.execute("ALTER TABLE results ADD COLUMN duration_seconds INT NULL AFTER total_questions;")
            conn.commit()
        # Zapamatujeme si, že kontrola už proběhla.
        _duration_column_checked = True
    finally:
        cur.close()
        conn.close()


def ensure_users_profile_title_column():
    # Úplně stejná logika jako výše, jen pro sloupec `profile_title` v tabulce `users`.
    global _profile_title_column_checked
    if _profile_title_column_checked:
        return

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SHOW COLUMNS FROM users LIKE 'profile_title';")
        exists = cur.fetchone()
        if not exists:
            cur.execute("ALTER TABLE users ADD COLUMN profile_title VARCHAR(50) NULL AFTER role;")
            conn.commit()
        _profile_title_column_checked = True
    finally:
        cur.close()
        conn.close()


def ensure_question_attempts_table():
    # Tato funkce kontroluje, zda existuje tabulka `question_attempts`.
    # Když ne, vytvoří ji.
    global _question_attempts_table_checked
    if _question_attempts_table_checked:
        return

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SHOW TABLES LIKE 'question_attempts';")
        exists = cur.fetchone()
        if not exists:
            # Vytvoříme tabulku pokusů o jednotlivé otázky.
            # Cizí klíče zajišťují vazby na existující uživatele/otázky/kategorie/obtížnosti.
            # `ON DELETE CASCADE` znamená: když smažeme rodiče (např. uživatele),
            # DB automaticky smaže i navázané záznamy v této tabulce.
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
                    FOREIGN KEY (category_id) REFERENCES categories(category_id) ON DELETE CASCADE,
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
    # Kontrola/vytvoření tabulky, do které se ukládají nahlášené otázky.
    global _question_reports_table_checked
    if _question_reports_table_checked:
        return

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SHOW TABLES LIKE 'question_reports';")
        exists = cur.fetchone()
        if not exists:
            # Vytvoříme tabulku hlášení.
            # `status` pomáhá adminovi poznat stav řešení hlášení (nové, vyřešené...).
            # `updated_at ... ON UPDATE CURRENT_TIMESTAMP` = DB automaticky přepíše čas
            # při každé změně řádku, takže máme historii poslední úpravy.
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
# Auth helpery (stejný formát hash jako desktop: salt$sha256)
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    # Vytvoříme náhodnou "sůl" (salt), aby stejné heslo nevedlo vždy ke stejnému hashi.
    salt = secrets.token_hex(16)
    # Spojíme salt + heslo, zakódujeme na bajty a spočítáme SHA-256 hash.
    digest = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    # Uložíme obě části do jednoho řetězce odděleného znakem `$`.
    # Heslo se neukládá v čitelné podobě, ale jako jednosměrný otisk (hash).
    return f"{salt}${digest}"


def check_password(stored: str, password: str) -> bool:
    # Nejprve si ověříme, že uložená hodnota má očekávaný formát `salt$hash`.
    if not stored or "$" not in stored:
        return False
    # Rozdělíme uloženou hodnotu na salt a hash.
    salt, digest = stored.split("$", 1)
    # Ze zadaného hesla vypočítáme hash stejným způsobem jako při ukládání.
    check = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    # Bezpečné porovnání proti timing útokům.
    # `compare_digest` porovnává "konstantním stylem" a neprozrazuje časem,
    # kde přesně se řetězce liší.
    return secrets.compare_digest(digest, check)


def get_user_by_username(username: str):
    # SQL dotaz: hledáme konkrétního uživatele podle jména.
    sql = "SELECT user_id, username, password_hash, role, created_at FROM users WHERE username = %s;"
    return fetch_one(sql, (username,))


def get_user_by_id(user_id: int):
    # SQL dotaz: hledáme konkrétního uživatele podle jeho číselného ID.
    sql = "SELECT user_id, username, role, created_at FROM users WHERE user_id = %s;"
    return fetch_one(sql, (user_id,))


def verify_login(username: str, password: str):
    # 1) Najdeme uživatele podle zadaného jména.
    user = get_user_by_username(username)
    # 2) Když uživatel neexistuje, přihlášení selže.
    if not user:
        return None
    # 3) Když heslo nesedí, přihlášení také selže.
    if not check_password(user["password_hash"], password):
        return None
    # 4) Vracíme jen bezpečné údaje, ne hash hesla.
    # Díky tomu se hash hesla dál zbytečně "nenosí" po aplikaci.
    return {
        "user_id": user["user_id"],
        "username": user["username"],
        "role": user["role"],
    }


def create_user(username: str, password: str, role: str = "user"):
    # Před uložením hesla ho vždy převedeme na hash.
    pwd_hash = hash_password(password)
    sql = "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s);"
    return execute(sql, (username, pwd_hash, role))


# ---------------------------------------------------------------------------
# Referenční data
# ---------------------------------------------------------------------------

def get_categories():
    # Načte všechny kategorie seřazené podle názvu (A-Z).
    return fetch_all("SELECT category_id, name FROM categories ORDER BY name;")


def get_categories_with_stats():
    # Načte kategorie a zároveň spočítá, kolik je k nim přiřazených otázek.
    # `LEFT JOIN` znamená, že dostaneme i kategorie, které zatím nemají žádnou otázku.
    # Díky tomu se v adminu zobrazí i "prázdné" kategorie (nejen ty, co už mají otázky).
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
    # Vloží novou kategorii do databáze.
    # `description or None` zajistí, že prázdný text uložíme jako NULL.
    # `NULL` v databázi znamená "hodnota není zadaná", což je lepší než ukládat prázdný řetězec všude.
    sql = "INSERT INTO categories (name, description) VALUES (%s, %s);"
    return execute(sql, (name, description or None))


def delete_category(category_id: int):
    # Smaže kategorii "natvrdo" včetně navázaných dat:
    # - výsledky v `results`
    # - pokusy v `question_attempts`
    # - vazby otázka<->kategorie v `questions_categories`
    # - otázky, které po odebrání vazby zůstanou bez jakékoli kategorie
    # Vše běží v jedné transakci, aby nevznikla napůl smazaná data.
    conn = get_connection()
    cur = conn.cursor()
    try:
        # Nejdřív si uložíme otázky patřící do této kategorie.
        # Později smažeme jen ty, které po odebrání vazby osiří.
        cur.execute(
            "SELECT DISTINCT question_id FROM questions_categories WHERE category_id = %s;",
            (category_id,),
        )
        question_ids = [row[0] for row in cur.fetchall()]

        # Smazání dat navázaných přímo na kategorii.
        # Pořadí je zvolené tak, aby nevznikaly konflikty cizích klíčů.
        cur.execute("DELETE FROM results WHERE category_id = %s;", (category_id,))
        cur.execute("DELETE FROM question_attempts WHERE category_id = %s;", (category_id,))
        cur.execute("DELETE FROM questions_categories WHERE category_id = %s;", (category_id,))

        # Smazání otázek, které byly v této kategorii a už nemají žádnou jinou vazbu.
        if question_ids:
            # Pro seznam ID vytvoříme správný počet placeholderů: `%s, %s, %s, ...`.
            placeholders = ", ".join(["%s"] * len(question_ids))
            cur.execute(
                f"""
                DELETE q
                FROM questions q
                LEFT JOIN questions_categories qc ON qc.question_id = q.question_id
                WHERE q.question_id IN ({placeholders})
                  AND qc.question_id IS NULL;
                """,
                # Hodnoty ID posíláme zvlášť jako tuple (bezpečně, bez ručního skládání SQL).
                tuple(question_ids),
            )

        # Nakonec smažeme samotnou kategorii.
        cur.execute("DELETE FROM categories WHERE category_id = %s;", (category_id,))
        deleted_categories = cur.rowcount
        conn.commit()
        return deleted_categories
    except Exception:
        # Jakákoli chyba = vrátit transakci zpět do původního stavu.
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def update_category_description(category_id: int, description: str = ""):
    # Upraví popis existující kategorie.
    sql = "UPDATE categories SET description = %s WHERE category_id = %s;"
    return execute(sql, (description or None, category_id))


def get_difficulties():
    # Načte seznam obtížností (např. lehká/střední/těžká).
    return fetch_all("SELECT difficulty_id, name FROM difficulties ORDER BY difficulty_id;")


def get_users_simple():
    # Vrací základní přehled uživatelů pro filtry a administraci.
    sql = "SELECT user_id, username, role, created_at FROM users ORDER BY username;"
    return fetch_all(sql)


def update_user_username(user_id: int, new_username: str):
    # Změní uživatelské jméno u konkrétního uživatele.
    sql = "UPDATE users SET username = %s WHERE user_id = %s;"
    return execute(sql, (new_username, user_id))


def update_user_password(user_id: int, new_password: str):
    # Před uložením nového hesla opět vytvoříme hash.
    new_hash = hash_password(new_password)
    sql = "UPDATE users SET password_hash = %s WHERE user_id = %s;"
    return execute(sql, (new_hash, user_id))


def delete_user_by_id(user_id: int):
    # Smaže uživatele podle ID.
    sql = "DELETE FROM users WHERE user_id = %s;"
    return execute(sql, (user_id,))


def get_user_profile_summary(user_id: int):
    # Vrátí profilové shrnutí: základní údaje + statistiky + XP + level.
    # Nejdřív se ujistíme, že existuje sloupec pro vlastní titul v profilu.
    ensure_users_profile_title_column()

    # Načteme základ uživatele.
    user_sql = "SELECT user_id, username, profile_title FROM users WHERE user_id = %s;"
    user = fetch_one(user_sql, (user_id,))
    # Když uživatel neexistuje, není co vracet.
    if not user:
        return None

    # Spočítáme souhrn nad tabulkou výsledků.
    # `COALESCE(..., 0)` = když SQL vrátí NULL, použij 0.
    # `CASE WHEN ... THEN ... ELSE ... END` = podmínka přímo uvnitř SQL výpočtu.
    stats_sql = """
    SELECT
        COUNT(*) AS quizzes_played,
        COALESCE(SUM(r.score), 0) AS total_correct_answers,
        COALESCE(SUM(r.total_questions), 0) AS total_answered_questions,
        COALESCE(
            SUM(
                20
                + (r.score * 10)
                + CASE
                    WHEN r.total_questions > 0 AND r.score = r.total_questions THEN 30
                    WHEN r.total_questions > 0 AND (r.score / r.total_questions) >= 0.8 THEN 15
                    ELSE 0
                END
            ),
            0
        ) AS total_xp
    FROM results r
    WHERE r.user_id = %s;
    """
    # Když by query vrátila None, použijeme prázdný slovník, ať se s ním dá bezpečně pracovat.
    stats = fetch_one(stats_sql, (user_id,)) or {}

    # Vše převedeme na čísla, aby další výpočty byly spolehlivé.
    quizzes_played = int(stats.get("quizzes_played") or 0)
    total_correct_answers = int(stats.get("total_correct_answers") or 0)
    total_answered_questions = int(stats.get("total_answered_questions") or 0)
    total_xp = int(stats.get("total_xp") or 0)

    # Když není žádná zodpovězená otázka, procenta necháme 0.0.
    success_pct = 0.0
    # Tady se program rozhoduje: jen pokud máme aspoň jednu otázku,
    # má smysl počítat úspěšnost.
    if total_answered_questions > 0:
        success_pct = round((total_correct_answers / total_answered_questions) * 100, 2)

    # Jednoduchý level systém: každých 100 XP je nový level.
    level = (total_xp // 100) + 1
    next_level_xp = level * 100
    # Kolik XP máme "uvnitř" aktuální stovky.
    # Např. 245 XP -> `245 % 100` = 45 (tedy 45 % do další úrovně).
    xp_progress_pct = total_xp % 100

    # Vracíme hotový slovník, který se používá ve view/templatu profilu.
    return {
        "user_id": user["user_id"],
        "username": user["username"],
        "profile_title": user.get("profile_title"),
        "level": level,
        "total_xp": total_xp,
        "next_level_xp": next_level_xp,
        "xp_progress_pct": xp_progress_pct,
        "quizzes_played": quizzes_played,
        "success_pct": success_pct,
    }


def update_user_profile_title(user_id: int, profile_title: str | None):
    # Uloží ručně zvolený profilový titul uživatele.
    ensure_users_profile_title_column()
    sql = "UPDATE users SET profile_title = %s WHERE user_id = %s;"
    return execute(sql, (profile_title, user_id))


# ---------------------------------------------------------------------------
# Moje historie (user)
# ---------------------------------------------------------------------------

def _build_user_history_where(user_id: int, filters: dict | None = None):
    # Pomocná funkce: postaví WHERE část SQL dotazu podle zadaných filtrů.
    data = filters or {}
    # Základní pravidlo: historie musí patřit jen aktuálnímu uživateli.
    conditions = ["r.user_id = %s"]
    params = [user_id]

    # Každý `if` znamená "použij filtr jen tehdy, když ho uživatel opravdu zadal".
    if data.get("category_id"):
        conditions.append("r.category_id = %s")
        params.append(data["category_id"])
    if data.get("difficulty_id"):
        conditions.append("r.difficulty_id = %s")
        params.append(data["difficulty_id"])
    if data.get("date_from"):
        # `DATE(...)` odřízne čas, takže porovnáváme čistě datum (den/měsíc/rok).
        conditions.append("DATE(r.played_at) >= %s")
        params.append(data["date_from"])
    if data.get("date_to"):
        conditions.append("DATE(r.played_at) <= %s")
        params.append(data["date_to"])

    # Vracej SQL podmínku i parametry ve stejném pořadí.
    return "WHERE " + " AND ".join(conditions), params


def get_user_history_rows(
    user_id: int,
    filters: dict | None = None,
    order: str = "newest",
    limit: int | None = 15,
    offset: int = 0,
):
    # Vrátí jednotlivé pokusy uživatele (řádky tabulky historie).
    # Nejdřív jistota, že DB schéma obsahuje sloupec s délkou trvání.
    ensure_results_duration_column()
    # Postavíme filtrovací podmínku a parametry.
    where_sql, params = _build_user_history_where(user_id, filters)
    # Povolené varianty řazení. Používáme mapu, aby uživatel nemohl poslat libovolný SQL text.
    # To je bezpečnostní krok: hodnotu `order` nikdy nevkládáme přímo "naslepo".
    safe_order = {
        "newest": "r.played_at DESC",
        "oldest": "r.played_at ASC",
        "best": "r.score DESC, r.played_at DESC",
        "worst": "r.score ASC, r.played_at DESC",
        "speedrun": (
            "r.category_id ASC, "
            "r.difficulty_id ASC, "
            # `NULLIF(r.total_questions, 0)` vrátí NULL místo nuly, takže nehrozí dělení nulou.
            "ROUND((r.score / NULLIF(r.total_questions, 0)) * 100, 2) DESC, "
            "r.score DESC, "
            "r.duration_seconds IS NULL ASC, "
            "r.duration_seconds ASC, "
            "r.played_at ASC"
        ),
    }.get(order, "r.played_at DESC")
    # Pokud je `order` neznámý, použije se bezpečný default: nejnovější nahoře.

    # Sestavíme hlavní dotaz.
    sql = f"""
    SELECT
        r.result_id,
        c.name AS category,
        d.name AS difficulty,
        r.score,
        r.total_questions,
        r.duration_seconds,
        r.played_at,
        ROUND((r.score / NULLIF(r.total_questions, 0)) * 100, 2) AS success_pct
    FROM results r
    JOIN categories c ON c.category_id = r.category_id
    JOIN difficulties d ON d.difficulty_id = r.difficulty_id
    {where_sql}
    ORDER BY {safe_order}
    """

    # Stránkování: limit + volitelný offset.
    if limit is not None:
        sql += " LIMIT %s"
        params.append(limit)
        # Offset dává smysl jen když je > 0.
        if offset and offset > 0:
            sql += " OFFSET %s"
            params.append(offset)

    sql += ";"
    return fetch_all(sql, tuple(params))


def count_user_history_rows(user_id: int, filters: dict | None = None):
    # Vrátí celkový počet záznamů historie (pro stránkování).
    where_sql, params = _build_user_history_where(user_id, filters)
    sql = f"""
    SELECT COUNT(*) AS total
    FROM results r
    {where_sql};
    """
    row = fetch_one(sql, tuple(params))
    return int((row or {}).get("total") or 0)


def get_user_history_summary(user_id: int, filters: dict | None = None):
    # Spočítá souhrnné statistiky pro zobrazení na stránce "Moje historie".
    # AVG = průměrná procentuální úspěšnost přes všechny pokusy.
    where_sql, params = _build_user_history_where(user_id, filters)
    sql = f"""
    SELECT
        COUNT(*) AS attempts,
        COALESCE(SUM(r.score), 0) AS total_correct_answers,
        COALESCE(SUM(r.total_questions), 0) AS total_answered_questions,
        COALESCE(ROUND(AVG((r.score / NULLIF(r.total_questions, 0)) * 100), 2), 0) AS avg_success_pct,
        COALESCE(MAX((r.score / NULLIF(r.total_questions, 0)) * 100), 0) AS best_success_pct
    FROM results r
    {where_sql};
    """
    row = fetch_one(sql, tuple(params)) or {}
    # Bezpečný převod hodnot na čísla.
    attempts = int(row.get("attempts") or 0)
    total_correct = int(row.get("total_correct_answers") or 0)
    total_questions = int(row.get("total_answered_questions") or 0)
    overall_success_pct = 0.0
    # Tady se program rozhoduje: procenta počítáme jen pokud bylo něco zodpovězeno.
    if total_questions > 0:
        overall_success_pct = round((total_correct / total_questions) * 100, 2)

    return {
        "attempts": attempts,
        "avg_success_pct": float(row.get("avg_success_pct") or 0.0),
        "best_success_pct": round(float(row.get("best_success_pct") or 0.0), 2),
        "overall_success_pct": overall_success_pct,
        "total_correct_answers": total_correct,
        "total_answered_questions": total_questions,
    }


def get_user_history_trend(user_id: int, limit: int = 12, filters: dict | None = None):
    # Připraví data pro trend graf (čas + procenta úspěšnosti).
    where_sql, params = _build_user_history_where(user_id, filters)
    # LIMIT jde jako další parametr na konec.
    params.append(limit)
    sql = f"""
    SELECT
        r.played_at,
        ROUND((r.score / NULLIF(r.total_questions, 0)) * 100, 2) AS success_pct
    FROM results r
    {where_sql}
    ORDER BY r.played_at DESC
    LIMIT %s;
    """
    rows = fetch_all(sql, tuple(params))
    # Dotaz vrací nejnovější první, ale graf obvykle chceme chronologicky.
    # Proto seznam obrátíme, aby čas běžel zleva doprava "od starších k novějším".
    rows.reverse()
    return rows


# ---------------------------------------------------------------------------
# Otázky - CRUD pro admin web
# ---------------------------------------------------------------------------

def _build_questions_where(search: str = "", category_id: int | None = None, difficulty_id: int | None = None):
    # Pomocná funkce: skládá WHERE podmínky pro výpis otázek.
    conditions = []
    params = []

    # Přidáme jen filtry, které uživatel opravdu vyplnil.
    if search:
        # `LIKE %text%` hledá i výskyty uprostřed věty (nejen přesnou shodu).
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

    # Výstupem je text WHERE + odpovídající parametry.
    return where_sql, params


def list_questions(
    search: str = "",
    category_id: int | None = None,
    difficulty_id: int | None = None,
    limit: int | None = None,
    offset: int = 0,
):
    # Vrátí seznam otázek s kategorií, obtížností a počtem hlášení.
    # Nejdřív jistota, že tabulka hlášení existuje (kvůli JOIN poddotazu).
    ensure_question_reports_table()
    where_sql, params = _build_questions_where(search, category_id, difficulty_id)

    # Hlavní dotaz.
    # `LEFT JOIN` je tu záměrně, aby se otázka ukázala i když k ní chybí vazba/hlášení.
    # Poddotaz níže spočítá počet hlášení pro každou otázku zvlášť.
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
        COALESCE(qr.report_count, 0) AS report_count,
        q.created_at
    FROM questions q
    JOIN difficulties d ON d.difficulty_id = q.difficulty_id
    LEFT JOIN questions_categories qc ON qc.question_id = q.question_id
    LEFT JOIN categories c ON c.category_id = qc.category_id
    LEFT JOIN (
        SELECT question_id, COUNT(*) AS report_count
        FROM question_reports
        GROUP BY question_id
    ) qr ON qr.question_id = q.question_id
    {where_sql}
    ORDER BY q.question_id DESC
    """

    # Stránkování (stejný princip jako jinde).
    if limit is not None:
        sql += " LIMIT %s"
        params.append(limit)
        if offset and offset > 0:
            sql += " OFFSET %s"
            params.append(offset)

    sql += ";"
    return fetch_all(sql, tuple(params))


def count_questions(search: str = "", category_id: int | None = None, difficulty_id: int | None = None):
    # Spočítá počet otázek pro aktuální filtry (kvůli stránkování v adminu).
    where_sql, params = _build_questions_where(search, category_id, difficulty_id)
    sql = f"""
    SELECT COUNT(*) AS total
    FROM questions q
    LEFT JOIN questions_categories qc ON qc.question_id = q.question_id
    {where_sql};
    """
    row = fetch_one(sql, tuple(params))
    return int((row or {}).get("total") or 0)


def get_question_by_id(question_id: int):
    # Načte detail jedné konkrétní otázky podle ID.
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
    # Vytvoří jednu otázku a hned ji naváže na kategorii.
    # Děláme to v jedné transakci, aby nevznikla "napůl uložená" data.
    conn = get_connection()
    cur = conn.cursor()
    try:
        # 1) Vložíme otázku.
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
        # ID právě vložené otázky.
        # `lastrowid` vrací auto-increment ID, které databáze právě vytvořila.
        question_id = cur.lastrowid

        # 2) Vložíme vazbu otázka -> kategorie.
        cur.execute(
            "INSERT INTO questions_categories (question_id, category_id) VALUES (%s, %s);",
            (question_id, category_id),
        )

        # 3) Potvrdíme celou transakci.
        conn.commit()
        return question_id
    except Exception:
        # Při chybě vrátíme databázi do původního stavu.
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def create_questions_bulk(payloads: list[dict], created_by: int | None = None):
    # Hromadné vložení více otázek v jedné transakci.
    # Každý `payload` má obsahovat:
    # question_text, answer_a, answer_b, answer_c, answer_d,
    # correct_answer, difficulty_id, category_id.
    if not payloads:
        # Když není co ukládat, vrátíme 0.
        return 0

    conn = get_connection()
    cur = conn.cursor()
    try:
        # Procházíme seznam otázek jednu po druhé.
        # Každý průchod vloží otázku + vazbu do `questions_categories`.
        for payload in payloads:
            # Vložíme otázku.
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

            # Vložíme vazbu na kategorii.
            cur.execute(
                "INSERT INTO questions_categories (question_id, category_id) VALUES (%s, %s);",
                (question_id, payload["category_id"]),
            )

        # Pokud vše proběhlo, uložíme naráz celou dávku.
        conn.commit()
        return len(payloads)
    except Exception:
        # Jakákoli chyba = zrušit celou dávku.
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def update_question(question_id: int, payload: dict, category_id: int):
    # Upraví obsah otázky a nastaví její kategorii.
    conn = get_connection()
    cur = conn.cursor()
    try:
        # 1) Aktualizace textu/odpovědí/obtížnosti.
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

        # 2) V MVP držíme jednu kategorii, proto nejdřív smažeme starou vazbu.
        # Je to jednodušší a spolehlivé: vždy víme, že po kroku 3 zůstane právě jedna vazba.
        cur.execute("DELETE FROM questions_categories WHERE question_id = %s;", (question_id,))
        # 3) A vložíme novou vazbu.
        cur.execute(
            "INSERT INTO questions_categories (question_id, category_id) VALUES (%s, %s);",
            (question_id, category_id),
        )

        # 4) Potvrdíme změny.
        conn.commit()
    except Exception:
        # Při chybě vrátíme změny zpět.
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def delete_question(question_id: int):
    # Smaže otázku. Vazby v `questions_categories` se odstraní automaticky přes ON DELETE CASCADE.
    return execute("DELETE FROM questions WHERE question_id = %s;", (question_id,))


# ---------------------------------------------------------------------------
# Výsledky, leaderboard, statistiky
# ---------------------------------------------------------------------------

def _build_results_where(filters: dict):
    # Pomocná funkce pro skládání filtrů výsledků.
    conditions = []
    params = []

    if filters.get("username"):
        # Fulltext-like filtr podle části jména (např. "jan" najde i "janek").
        conditions.append("u.username LIKE %s")
        params.append(f"%{filters['username']}%")

    if filters.get("category_id"):
        conditions.append("r.category_id = %s")
        params.append(filters["category_id"])

    if filters.get("difficulty_id"):
        conditions.append("r.difficulty_id = %s")
        params.append(filters["difficulty_id"])

    if filters.get("date_from"):
        # Datum od (včetně).
        conditions.append("DATE(r.played_at) >= %s")
        params.append(filters["date_from"])

    if filters.get("date_to"):
        # Datum do (včetně).
        conditions.append("DATE(r.played_at) <= %s")
        params.append(filters["date_to"])

    where_sql = ""
    if conditions:
        where_sql = "WHERE " + " AND ".join(conditions)

    # Vrací text podmínky i parametry.
    return where_sql, params


def get_filtered_results(
    filters: dict | None = None,
    order: str = "score_desc",
    limit: int | None = 200,
    offset: int = 0,
):
    # Vrátí výsledky s uživatelem, kategorií a obtížností.
    # Obsahuje i řazení a stránkování.
    ensure_results_duration_column()
    # Převod uživatelského parametru `order` na bezpečný SQL výraz.
    # Kdybychom to neudělali přes whitelist, uživatel by mohl poslat nebezpečný SQL text.
    safe_order = {
        "id_desc": "r.result_id DESC",
        "id_asc": "r.result_id ASC",
        "score_desc": "r.score DESC, r.played_at DESC",
        "score_asc": "r.score ASC, r.played_at DESC",
        "newest": "r.played_at DESC",
        "oldest": "r.played_at ASC",
        "speedrun": (
            "r.category_id ASC, "
            "r.difficulty_id ASC, "
            # `NULLIF(..., 0)` chrání před dělením nulou.
            "ROUND((r.score / NULLIF(r.total_questions, 0)) * 100, 2) DESC, "
            "r.score DESC, "
            # `IS NULL ASC` dá nejdřív záznamy, které čas mají (NULL je až za nimi).
            "r.duration_seconds IS NULL ASC, "
            "r.duration_seconds ASC, "
            "r.played_at ASC"
        ),
    }.get(order, "r.score DESC, r.played_at DESC")

    # Filtry od uživatele převedeme na WHERE + params.
    where_sql, params = _build_results_where(filters or {})

    # Hlavní dotaz pro tabulku výsledků.
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

    # Stránkování.
    if limit is not None:
        sql += " LIMIT %s"
        params.append(limit)
        if offset and offset > 0:
            sql += " OFFSET %s"
            params.append(offset)

    sql += ";"
    return fetch_all(sql, tuple(params))


def count_filtered_results(filters: dict | None = None):
    # Vrátí jen počet výsledků (pro stránkování/počítadlo).
    where_sql, params = _build_results_where(filters or {})
    sql = f"""
    SELECT COUNT(*) AS total
    FROM results r
    JOIN users u ON u.user_id = r.user_id
    JOIN categories c ON c.category_id = r.category_id
    JOIN difficulties d ON d.difficulty_id = r.difficulty_id
    {where_sql};
    """
    row = fetch_one(sql, tuple(params))
    return int((row or {}).get("total") or 0)


def get_leaderboard(limit: int = 20):
    # Jednoduchý helper: vezme nejlepší výsledky podle skóre.
    return get_filtered_results(filters={}, order="score_desc", limit=limit)


def get_recent_results(limit: int = 8):
    # Vrátí několik nejnovějších výsledků pro úvodní stránku.
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
    # Smaže více výsledků najednou podle seznamu ID.
    if not result_ids:
        # Když seznam neobsahuje žádné ID, nic nemažeme.
        return 0

    # Vytvoříme správný počet `%s` placeholderů do IN (...).
    # Např. pro 3 ID vznikne text `%s, %s, %s`.
    placeholders = ", ".join(["%s"] * len(result_ids))
    sql = f"DELETE FROM results WHERE result_id IN ({placeholders});"
    # Samotné hodnoty ID stále posíláme separátně v `tuple(result_ids)` (bezpečně).
    return execute(sql, tuple(result_ids))


def get_stats_by_category():
    # Statistiky do grafu: počet pokusů + průměrná úspěšnost podle kategorie.
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
    # Statistiky podle obtížnosti (úspěšnost, průměrný čas, podíl perfektních výsledků).
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
    # Vrátí TOP uživatele podle průměrné úspěšnosti a počtu pokusů.
    # `HAVING` filtruje až po GROUP BY (na agregované výsledky).
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
# Hlášení otázek
# ---------------------------------------------------------------------------

_ALLOWED_REPORT_STATUSES = {"new", "reviewed", "resolved", "rejected"}
# Tento "whitelist" je seznam jediných povolených stavů hlášení.


def _normalize_report_status(status: str | None):
    # Přijme text statusu a převede ho na bezpečnou/platnou hodnotu.
    value = (status or "").strip().lower()
    # Když je vstup prázdný, vracíme None (žádný filtr).
    if not value:
        return None
    # Když je vstup mimo povolené hodnoty, vracíme None.
    if value not in _ALLOWED_REPORT_STATUSES:
        return None
    # Vracíme normalizovaný text (malá písmena, bez mezer navíc).
    return value


def create_question_report(question_id: int, user_id: int, reason: str, note: str = ""):
    # Uloží nové hlášení otázky od uživatele.
    ensure_question_reports_table()
    sql = """
    INSERT INTO question_reports (question_id, user_id, reason, note)
    VALUES (%s, %s, %s, %s);
    """
    # Očistíme vstup: odstraníme mezery navíc a omezíme maximální délku.
    clean_reason = (reason or "").strip()[:60]
    clean_note = (note or "").strip()[:500]
    return execute(sql, (question_id, user_id, clean_reason, clean_note or None))


def count_question_reports(status: str | None = None):
    # Spočítá hlášení (všechna, nebo jen pro vybraný status).
    ensure_question_reports_table()
    normalized = _normalize_report_status(status)
    # Tady se program rozhoduje: když je status platný, filtrujeme podle něj.
    if normalized:
        row = fetch_one(
            "SELECT COUNT(*) AS total FROM question_reports WHERE status = %s;",
            (normalized,),
        )
    else:
        # Jinak spočítáme úplně všechna hlášení.
        row = fetch_one("SELECT COUNT(*) AS total FROM question_reports;")
    return int((row or {}).get("total") or 0)


def get_question_reports(status: str | None = None, limit: int | None = 15, offset: int = 0):
    # Načte seznam hlášení pro admin stránku.
    ensure_question_reports_table()
    normalized = _normalize_report_status(status)
    params = []
    where_sql = ""
    # Pokud je status platný, přidáme WHERE filtr.
    if normalized:
        where_sql = "WHERE qr.status = %s"
        params.append(normalized)

    # CASE v ORDER BY nám umožní vlastní pořadí statusů.
    # Díky tomu budou "new" hlášení vždy před "reviewed/resolved/rejected".
    sql = f"""
    SELECT
        qr.report_id,
        qr.question_id,
        q.question_text,
        qr.user_id,
        reporter.username AS reporter_username,
        qr.reason,
        qr.note,
        qr.status,
        qr.created_at,
        qr.updated_at,
        qr.resolved_by,
        resolver.username AS resolved_by_username
    FROM question_reports qr
    JOIN questions q ON q.question_id = qr.question_id
    JOIN users reporter ON reporter.user_id = qr.user_id
    LEFT JOIN users resolver ON resolver.user_id = qr.resolved_by
    {where_sql}
    ORDER BY
        CASE qr.status
            WHEN 'new' THEN 0
            WHEN 'reviewed' THEN 1
            WHEN 'resolved' THEN 2
            WHEN 'rejected' THEN 3
            ELSE 4
        END,
        qr.created_at DESC
    """

    # Stránkování.
    if limit is not None:
        sql += " LIMIT %s"
        params.append(limit)
        if offset and offset > 0:
            sql += " OFFSET %s"
            params.append(offset)

    sql += ";"
    return fetch_all(sql, tuple(params))


def update_question_report_status(report_id: int, new_status: str, resolved_by: int | None):
    # Upraví status hlášení a případně uloží admina, který změnu provedl.
    ensure_question_reports_table()
    normalized = _normalize_report_status(new_status)
    # Když status není platný, vyhodíme chybu (aby volající věděl proč).
    if not normalized:
        raise ValueError("Neplatný status hlášení.")

    # `resolved_by` ukládáme jen u stavů, kde je to logické (reviewed/resolved/rejected).
    resolver_id = resolved_by if normalized in {"reviewed", "resolved", "rejected"} else None
    sql = """
    UPDATE question_reports
    SET status = %s,
        resolved_by = %s
    WHERE report_id = %s;
    """
    return execute(sql, (normalized, resolver_id, report_id))


def get_question_report_counts_by_question_ids(question_ids: list[int]):
    # Vrátí slovník: klíč je `question_id`, hodnota je počet hlášení.
    ensure_question_reports_table()
    if not question_ids:
        # Když není žádné ID, vracíme prázdný slovník.
        return {}

    placeholders = ", ".join(["%s"] * len(question_ids))
    # Počet `%s` musí přesně odpovídat počtu ID, jinak by dotaz selhal.
    sql = f"""
    SELECT question_id, COUNT(*) AS report_count
    FROM question_reports
    WHERE question_id IN ({placeholders})
    GROUP BY question_id;
    """
    rows = fetch_all(sql, tuple(question_ids))
    # Převod listu řádků na mapu {id: count}.
    return {int(row["question_id"]): int(row["report_count"]) for row in rows}


# ---------------------------------------------------------------------------
# CSV import/export helpery
# ---------------------------------------------------------------------------

def import_results_csv(file_storage):
    # Importuje výsledky z CSV souboru.
    # Očekávané sloupce:
    # username,category,difficulty,score,total_questions,played_at(optional),duration_seconds(optional)
    # Import je transakční: při chybě se neuloží nic.
    ensure_results_duration_column()

    # Kontrola, že soubor byl vůbec vybrán.
    if not file_storage or not file_storage.filename:
        raise ValueError("Nebyl vybrán žádný CSV soubor.")

    # Načteme celé binární tělo souboru.
    # `file_storage` je objekt Flask/Werkzeug (`FileStorage`) pro nahraný soubor z formuláře.
    raw = file_storage.stream.read()
    if not raw:
        raise ValueError("CSV soubor je prázdný.")

    # Očekáváme UTF-8 (s případným BOM).
    # `utf-8-sig` umí odstranit BOM značku na začátku souboru, pokud tam je.
    try:
        decoded = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV musí být v UTF-8 kódování.") from exc

    # DictReader čte CSV po řádcích jako slovníky podle názvů sloupců.
    # Klíče ve slovníku jsou názvy sloupců z hlavičky CSV.
    reader = csv.DictReader(StringIO(decoded))
    required = {"username", "category", "difficulty", "score", "total_questions"}

    # Ověříme, že CSV obsahuje všechny povinné sloupce.
    if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
        missing = sorted(required - set(reader.fieldnames or []))
        raise ValueError(f"CSV nemá povinné sloupce: {', '.join(missing)}")

    # Načteme datové řádky.
    rows = list(reader)
    if not rows:
        raise ValueError("CSV neobsahuje žádné datové řádky.")

    # Připravíme mapy "text -> ID", aby šly rychle převádět názvy na cizí klíče.
    user_map = {row["username"]: row["user_id"] for row in fetch_all("SELECT user_id, username FROM users;")}
    category_map = {row["name"]: row["category_id"] for row in get_categories()}
    difficulty_map = {row["name"]: row["difficulty_id"] for row in get_difficulties()}

    # `prepared` bude seznam zvalidovaných řádků připravených k insertu.
    # `errors` bude seznam chyb pro uživatele.
    prepared = []
    errors = []

    # `start=2` je schválně: řádek 1 je hlavička CSV.
    # Takže čísla chybových řádků odpovídají tomu, co uživatel vidí v editoru tabulek.
    for idx, row in enumerate(rows, start=2):
        # Očistíme textová pole.
        username = (row.get("username") or "").strip()
        category = (row.get("category") or "").strip()
        difficulty = (row.get("difficulty") or "").strip()

        # Tady se program rozhoduje: pokud se hodnota nenašla v mapě, řádek je neplatný.
        if username not in user_map:
            errors.append(f"Řádek {idx}: neznámý uživatel '{username}'.")
            continue
        if category not in category_map:
            errors.append(f"Řádek {idx}: neznámá kategorie '{category}'.")
            continue
        if difficulty not in difficulty_map:
            errors.append(f"Řádek {idx}: neznámá obtížnost '{difficulty}'.")
            continue

        # Převod skóre a celkového počtu otázek na čísla.
        try:
            score = int((row.get("score") or "").strip())
            total = int((row.get("total_questions") or "").strip())
        except ValueError:
            errors.append(f"Řádek {idx}: score/total_questions musí být celá čísla.")
            continue

        # Logické kontroly rozsahu.
        if total <= 0:
            errors.append(f"Řádek {idx}: total_questions musí být > 0.")
            continue
        if score < 0 or score > total:
            errors.append(f"Řádek {idx}: score musí být v rozsahu 0..total_questions.")
            continue

        # Datum/čas pokusu je volitelný.
        played_at_raw = (row.get("played_at") or "").strip()
        # Když je vyplněný, pokusíme se ho převést.
        if played_at_raw:
            try:
                # Nahrazení `Z` za `+00:00` pomáhá u UTC zápisu typu `2026-03-25T14:30:00Z`.
                played_at = datetime.fromisoformat(played_at_raw.replace("Z", "+00:00"))
                played_at_value = played_at.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                errors.append(
                    f"Řádek {idx}: played_at musí být ve formátu ISO (např. 2026-03-25T14:30:00)."
                )
                continue
        else:
            # Když chybí, použijeme aktuální čas importu.
            played_at_value = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Délka trvání (sekundy) je také volitelná.
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

        # Když řádek prošel všemi kontrolami, přidáme ho mezi připravená data.
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

    # Když se našly chyby, import zastavíme ještě před zápisem do DB.
    if errors:
        preview = " ".join(errors[:4])
        # Když je chyb hodně, doplníme informaci "a dalších X chyb".
        if len(errors) > 4:
            preview += f" (a dalších {len(errors) - 4} chyb)"
        raise ValueError(preview)

    # Zápis do DB provedeme dávkově v transakci.
    conn = get_connection()
    cur = conn.cursor()
    try:
        # `executemany` vloží více řádků jedním SQL příkazem.
        # Je to výrazně rychlejší než posílat 1 INSERT pro každý řádek zvlášť.
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
        # Potvrzení celé dávky najednou.
        conn.commit()
        return len(prepared)
    except Exception:
        # Jakákoli chyba při insertu = rollback celé dávky.
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
