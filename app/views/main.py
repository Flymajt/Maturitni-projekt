import csv
# `csv`, `re`, `date`, `wraps`, `StringIO` jsou součást standardní knihovny Pythonu.
import re
from datetime import date
from functools import wraps
from io import StringIO

# Externí balíček z `site-packages` (instalace přes pip),
# slouží ke komunikaci s MySQL databází.
import mysql.connector
from flask import (
    # `Response` = ruční vytvoření HTTP odpovědi (např. CSV soubor místo HTML).
    Response,
    # `abort` = okamžité ukončení požadavku s HTTP chybou (např. 404 Not Found).
    abort,
    # `flash` = krátká zpráva uložená do session, která se ukáže až na další stránce.
    # Druhý parametr (`success`, `warning`, `danger`, `info`) je "typ zprávy" pro barvu/styl v šabloně.
    flash,
    # `redirect` + `url_for` = bezpečné přesměrování uživatele na jinou route.
    redirect,
    render_template,
    request,
    session,
    url_for,
)

# Import instance Flask aplikace ze souboru `app/__init__.py`
from app import app
# Import databázových helper funkcí ze souboru `app/db.py`
from app.db import (
    count_question_reports,
    create_category,
    create_user,
    create_questions_bulk,
    count_questions,
    count_filtered_results,
    count_user_history_rows,
    delete_category,
    delete_user_by_id,
    delete_question,
    delete_results_by_ids,
    fetch_one,
    get_categories,
    get_categories_with_stats,
    get_difficulties,
    get_filtered_results,
    get_question_by_id,
    get_recent_results,
    get_user_history_rows,
    get_user_history_summary,
    get_user_history_trend,
    get_stats_by_category,
    get_stats_by_difficulty,
    get_top_users,
    get_users_simple,
    get_question_reports,
    import_results_csv,
    list_questions,
    get_user_profile_summary,
    update_question_report_status,
    update_category_description,
    update_user_profile_title,
    update_user_password,
    update_user_username,
    update_question,
    verify_login,
)

LEVEL_TITLES = [
    # Každá položka je dvojice: (minimální level, text title).
    # Seznam je schválně od nejvyššího levelu k nejnižšímu.
    (25, "Legenda"),
    (20, "Mistr"),
    (15, "Expert"),
    (10, "Znalec"),
    (5, "Hráč"),
    (1, "Začátečník"),
]


# ---------------------------------------------------------------------------
# Auth guard helpery
# ---------------------------------------------------------------------------


def _level_title_for(level: int) -> str:
    # Vrátí automatický title podle hráčova levelu.
    # Seznam LEVEL_TITLES je řazen od nejvyššího levelu dolů.
    for min_level, title in LEVEL_TITLES:
        # Tady se program rozhoduje:
        # jakmile je hráčův level dost vysoký, vrátíme odpovídající title.
        if level >= min_level:
            return title
    # Bezpečnostní návratová hodnota.
    return "Začátečník"


def _available_titles_for(level: int):
    # Vrátí seznam všech title, které má hráč pro svůj level odemčené.
    # Procházíme dvojice (min_level, title) a bereme jen ty, které splní podmínku.
    unlocked = [title for min_level, title in LEVEL_TITLES if level >= min_level]
    # Otočíme pořadí, aby ve výběru byly od jednodušších title po vyšší.
    return list(reversed(unlocked))

def _to_int(value):
    # Bezpečný převod hodnoty z URL/formuláře na celé číslo.
    if value in (None, ""):
        # Prázdný vstup nebereme jako chybu, ale jako "není vyplněno".
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        # Když převod nejde, vrátíme None místo vyhození chyby.
        return None


def _get_filters(args):
    # Posbírá filtry z URL parametrů do jednoho slovníku.
    # Tím sjednotíme formát, který pak posíláme do DB helperů.
    return {
        # Textové hledání podle uživatelského jména.
        "username": (args.get("username") or "").strip(),
        # ID kategorie převedené bezpečně na číslo (nebo None).
        "category_id": _to_int(args.get("category_id")),
        # ID obtížnosti převedené bezpečně na číslo (nebo None).
        "difficulty_id": _to_int(args.get("difficulty_id")),
        # Spodní hranice data (od).
        "date_from": (args.get("date_from") or "").strip(),
        # Horní hranice data (do).
        "date_to": (args.get("date_to") or "").strip(),
    }


def _to_iso_date_or_empty(value: str) -> str:
    # Převede zadané datum na formát YYYY-MM-DD.
    # Když datum není vyplněné nebo je neplatné, vrátí prázdný text.
    if not value:
        return ""
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        return ""

def _filters_query_dict(filters, order):
    # Připraví parametry do URL tak, aby při přechodech zůstaly aktivní filtry i řazení.
    params = {"order": order}
    # Projdeme všechny filtry (klíč + hodnota) jeden po druhém.
    for key, value in filters.items():
        # Do URL ukládáme jen vyplněné hodnoty.
        if value not in (None, ""):
            params[key] = value
    return params


def _filters_query_with_page(filters, order, page: int):
    # Stejné jako `_filters_query_dict`, navíc přidává stránkování.
    params = _filters_query_dict(filters, order)
    if page > 1:
        # Stránku 1 obvykle do URL nedáváme, proto podmínka > 1.
        params["page"] = page
    return params


def _admin_questions_query_dict(
    search: str,
    category_id: int | None,
    difficulty_id: int | None,
    page: int,
):
    # Sestaví URL parametry pro stránku správy otázek v adminu.
    params = {}
    if search:
        # Do URL uložíme fulltext hledání.
        params["q"] = search
    if category_id:
        # Do URL uložíme filtr kategorie.
        params["category_id"] = category_id
    if difficulty_id:
        # Do URL uložíme filtr obtížnosti.
        params["difficulty_id"] = difficulty_id
    if page > 1:
        # Stránku 1 schválně vynecháváme, aby URL byla kratší.
        params["page"] = page
    return params


def _history_filters_query_with_page(filters, order, page: int):
    # Sestaví URL parametry pro stránku "Moje historie".
    params = {"order": order}
    # Projdeme konkrétní klíče filtrů jeden po druhém.
    for key in ("category_id", "difficulty_id", "date_from", "date_to"):
        value = filters.get(key)
        if value not in (None, ""):
            params[key] = value
    if page > 1:
        params["page"] = page
    return params


def _admin_reports_query_dict(status: str, page: int):
    # Sestaví URL parametry pro stránku hlášení otázek v adminu.
    params = {}
    if status:
        params["status"] = status
    if page > 1:
        params["page"] = page
    return params


def get_current_user():
    # Vrátí stručná data přihlášeného uživatele ze session.
    user_id = session.get("user_id")
    # Když chybí user_id, nikdo není přihlášen.
    if not user_id:
        return None
    return {
        # Jedinečné ID uživatele v databázi.
        "user_id": user_id,
        # Přihlašovací jméno.
        "username": session.get("username"),
        # Role (`user` nebo `admin`).
        "role": session.get("role"),
    }


@app.context_processor
def inject_current_user():
    # `@app.context_processor` znamená, že vrácená data jsou dostupná
    # ve všech šablonách bez nutnosti je ručně předávat v každém `render_template`.
    # Klíč `current_user` pak používají HTML šablony napříč celým webem.
    return {"current_user": get_current_user()}


@app.template_filter("format_duration")
def format_duration(seconds):
    # Převod sekund na čitelný text času.
    # Vrací buď mm:ss, nebo hh:mm:ss.
    if seconds in (None, ""):
        return "-"
    try:
        # Pokusíme se převést vstup na celé číslo.
        value = int(seconds)
    except (TypeError, ValueError):
        # Neplatný vstup = bezpečně pomlčka.
        return "-"
    if value < 0:
        return "-"

    # Rozpočítáme celkové sekundy na hodiny/minuty/sekundy.
    # `divmod(a, b)` vrátí dvojici: (kolikrát se b vejde do a, zbytek).
    hours, rest = divmod(value, 3600)
    minutes, secs = divmod(rest, 60)
    # Tady se program rozhoduje:
    # pokud je aspoň jedna hodina, zobrazíme i hodiny.
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def login_required(view):
    # Dekorátor, který chrání stránky: bez přihlášení na ně nepustí.

    @wraps(view)
    def wrapped(*args, **kwargs):
        # Když v session není `user_id`, uživatel není přihlášen.
        if not session.get("user_id"):
            # `flash` zpráva se neukáže hned tady v Pythonu,
            # ale až po redirectu v HTML šabloně (přes Jinja `get_flashed_messages`).
            flash("Pro pokračování se přihlas.", "warning")
            # Přesměrování na login + `next`, aby se po loginu mohl vrátit zpět.
            # `request.path` obsahuje právě navštívenou URL cestu.
            return redirect(url_for("login", next=request.path))
        # Přihlášený uživatel může pokračovat do původní route funkce.
        return view(*args, **kwargs)

    # Vracíme "obalenou" funkci, ne původní `view`.
    return wrapped


def admin_required(view):
    # Dekorátor pro stránky, kam smí jen admin.
    # Je navázaný na `login_required`, takže nejdřív kontrola loginu.

    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        # Tady se program rozhoduje: pokud role není admin, vrátíme uživatele na home.
        if session.get("role") != "admin":
            flash("Do této části má přístup pouze admin.", "danger")
            return redirect(url_for("home"))
        # Pokud role je `admin`, pustíme požadavek dál.
        return view(*args, **kwargs)

    return wrapped


# ---------------------------------------------------------------------------
# Veřejné stránky
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    # Route `/` = hlavní stránka webu.
    recent_results = get_recent_results(limit=8)
    # Do šablony posíláme posledních 8 výsledků.
    # HTML soubor, který se načte: `app/templates/index.html`.
    return render_template("index.html", recent_results=recent_results)


@app.route("/dbtest")
def dbtest():
    # Jednoduchý interní test spojení s databází.
    # SQL `SELECT 1 AS ok` vrátí hodnotu 1 v klíči `ok`, takže víme, že DB odpovídá.
    row = fetch_one("SELECT 1 AS ok;")
    # Vracíme jednoduchý text (ne HTML šablonu), aby test byl rychlý a přehledný.
    return f"MySQL OK: {row['ok']}"


@app.route("/login", methods=["GET", "POST"])
def login():
    # Route `/login`:
    # - GET zobrazí formulář
    # - POST zpracuje odeslaná data
    if request.method == "POST":
        # Načteme hodnoty z formuláře.
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        # Tady se program rozhoduje: bez jména nebo hesla login neproběhne.
        if not username or not password:
            flash("Vyplň uživatelské jméno i heslo.", "danger")
            return render_template("login.html")

        # Ověření kombinace jméno/heslo v databázi.
        user = verify_login(username, password)
        if not user:
            flash("Neplatné přihlašovací údaje.", "danger")
            # Při neúspěchu znovu načteme login obrazovku (`app/templates/login.html`).
            return render_template("login.html")

        # Úspěšný login: uložíme základní údaje do session.
        session["user_id"] = user["user_id"]
        session["username"] = user["username"]
        session["role"] = user["role"]
        flash(f"Přihlášen jako {user['username']}.", "success")

        # Volitelný návrat na stránku, ze které byl uživatel přesměrován na login.
        next_url = request.args.get("next", "")
        # Bezpečnost: povolujeme jen interní cesty začínající `/`.
        if next_url.startswith("/"):
            return redirect(next_url)

        # Rozhodnutí podle role.
        if user["role"] == "admin":
            # Přesměrování do route `admin_dashboard` (URL `/admin`).
            return redirect(url_for("admin_dashboard"))
        # Běžný uživatel jde po přihlášení na route `home` (URL `/`).
        return redirect(url_for("home"))

    # GET větev: jen zobrazíme formulář.
    # HTML soubor, který se načte: `app/templates/login.html`.
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    # Route `/register`:
    # - GET zobrazí registrační formulář
    # - POST provede validaci a pokus o vytvoření uživatele
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        password2 = request.form.get("password2") or ""

        # Povinná pole.
        if not username or not password or not password2:
            flash("Vyplň všechna registrační pole.", "danger")
            # U chyby vracíme stejný formulář (`app/templates/register.html`).
            return render_template("register.html")

        # Základní minimální délka jména.
        if len(username) < 3:
            flash("Uživatelské jméno musí mít aspoň 3 znaky.", "danger")
            return render_template("register.html")

        # Základní minimální délka hesla.
        if len(password) < 4:
            flash("Heslo musí mít aspoň 4 znaky.", "danger")
            return render_template("register.html")

        # Kontrola síly hesla: aspoň jedno velké písmeno + aspoň jedna číslice.
        if not re.search(r"[A-Z]", password) or not re.search(r"\d", password):
            flash("Heslo musí obsahovat aspoň jedno velké písmeno a jedno číslo.", "danger")
            return render_template("register.html")

        # Obě hesla se musí shodovat.
        if password != password2:
            flash("Hesla se neshodují.", "danger")
            return render_template("register.html")

        try:
            # Pokus o vytvoření uživatele v DB.
            create_user(username, password, role="user")
            flash("Registrace proběhla úspěšně. Teď se přihlas.", "success")
            # Po úspěchu posíláme uživatele na route `login` (URL `/login`).
            return redirect(url_for("login"))
        except mysql.connector.errors.IntegrityError:
            # Typicky duplicita username.
            # DB má unikátní omezení na jméno, proto stejný username vyhodí tuto chybu.
            flash("Toto uživatelské jméno už existuje.", "danger")
        except Exception as exc:
            # `exc` je objekt chyby; `str(exc)` z něj udělá čitelný text pro člověka.
            flash(f"Registrace selhala: {exc}", "danger")

    # GET větev nebo POST s chybou: zobrazení registrace z `app/templates/register.html`.
    return render_template("register.html")


@app.route("/logout")
@login_required
def logout():
    # Route `/logout`: vyčistí session (odhlášení uživatele).
    session.clear()
    flash("Byl jsi úspěšně odhlášen.", "info")
    # Po odhlášení přesměrujeme na hlavní stránku.
    return redirect(url_for("home"))


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    # Route `/profile` je jen pro přihlášeného uživatele (`@login_required`).
    user_id = session.get("user_id")
    # Načteme souhrn dat profilu z DB.
    profile_data = get_user_profile_summary(user_id)
    if not profile_data:
        flash("Profil se nepodařilo načíst.", "danger")
        return redirect(url_for("home"))

    # Vypočteme, které title může uživatel vybírat.
    available_titles = _available_titles_for(profile_data["level"])
    selected_title = profile_data.get("profile_title")
    # Když je uložený title už mimo aktuálně dostupné, zahodíme ho.
    if selected_title and selected_title not in available_titles:
        selected_title = None

    # POST = uživatel ukládá nový title.
    if request.method == "POST":
        new_title = (request.form.get("profile_title") or "").strip()
        # Tady se program rozhoduje: title musí být mezi odemčenými možnostmi.
        if new_title and new_title not in available_titles:
            flash("Vybraný title není dostupný pro tvůj aktuální level.", "danger")
        else:
            # Uložíme ruční title (nebo None, pokud nic nevybral).
            update_user_profile_title(user_id, new_title or None)
            flash("Profilový title byl uložen.", "success")
            return redirect(url_for("profile"))

    # `auto_title` = title vypočtený automaticky podle levelu.
    auto_title = _level_title_for(profile_data["level"])
    # `current_title` = ručně zvolený title, jinak fallback na automatický.
    current_title = selected_title or auto_title

    return render_template(
        # HTML soubor, který se načte: `app/templates/profile.html`.
        "profile.html",
        profile=profile_data,
        auto_title=auto_title,
        current_title=current_title,
        available_titles=available_titles,
        selected_title=selected_title,
    )


@app.route("/my-history")
@login_required
def my_history():
    # Route `/my-history` je osobní historie přihlášeného uživatele.
    per_page = 15
    # ID uživatele bereme ze session (nastavené při loginu).
    user_id = session.get("user_id")

    # Načteme filtry z URL.
    filters = {
        "category_id": _to_int(request.args.get("category_id")),
        "difficulty_id": _to_int(request.args.get("difficulty_id")),
        "date_from": (request.args.get("date_from") or "").strip(),
        "date_to": (request.args.get("date_to") or "").strip(),
    }
    order = request.args.get("order", "newest")
    # `or 1` znamená: když je page prázdné/neplatné, vezmeme první stránku.
    page = _to_int(request.args.get("page")) or 1
    if page < 1:
        # Stránka nesmí být menší než 1.
        page = 1

    # Uložíme si původní text dat kvůli validaci/chybovým hláškám.
    raw_date_from = filters.get("date_from", "")
    raw_date_to = filters.get("date_to", "")
    # Pokus o převod na standardní formát.
    filters["date_from"] = _to_iso_date_or_empty(raw_date_from)
    filters["date_to"] = _to_iso_date_or_empty(raw_date_to)

    # Informace uživateli, když zadal neplatný formát.
    if raw_date_from and not filters["date_from"]:
        flash("Datum od má neplatný formát.", "warning")
    if raw_date_to and not filters["date_to"]:
        flash("Datum do má neplatný formát.", "warning")
    # Tady se program rozhoduje: "datum do" nesmí být menší než "datum od".
    if filters["date_from"] and filters["date_to"] and filters["date_to"] < filters["date_from"]:
        filters["date_to"] = filters["date_from"]
        flash("Datum do nemůže být menší než datum od. Automaticky jsem ho upravil.", "warning")

    # Spočítáme celkový počet záznamů a podle něj počet stránek.
    total_rows = count_user_history_rows(user_id=user_id, filters=filters)
    total_pages = max(1, (total_rows + per_page - 1) // per_page)
    # Když uživatel otevře příliš vysokou stránku, posuneme ho na poslední dostupnou.
    if page > total_pages:
        page = total_pages

    # Načtení aktuální stránky dat + souhrn + trend do grafu.
    rows = get_user_history_rows(
        user_id=user_id,
        filters=filters,
        order=order,
        limit=per_page,
        offset=(page - 1) * per_page,
    )
    summary = get_user_history_summary(user_id=user_id, filters=filters)
    # `limit=10` znamená: do grafu bereme posledních 10 časových bodů.
    trend_rows = get_user_history_trend(user_id=user_id, limit=10, filters=filters)

    # Vypočítáme "okno" čísel stránek (např. 3 4 5 6 7).
    start_page = max(1, page - 2)
    end_page = min(total_pages, page + 2)
    # Pro každé číslo stránky připravíme i URL parametry.
    page_items = [
        {"number": p, "params": _history_filters_query_with_page(filters, order, p)}
        for p in range(start_page, end_page + 1)
    ]

    return render_template(
        # HTML soubor, který se načte: `app/templates/my_history.html`.
        "my_history.html",
        rows=rows,
        summary=summary,
        trend_rows=trend_rows,
        filters=filters,
        order=order,
        options={
            # Seznam kategorií pro výběrový filtr v horní části stránky.
            "categories": get_categories(),
            # Seznam obtížností pro výběrový filtr.
            "difficulties": get_difficulties(),
        },
        pagination={
            # Aktuální číslo stránky.
            "page": page,
            # Celkový počet nalezených řádků v DB.
            "total_rows": total_rows,
            # Celkový počet stránek po rozdělení na `per_page`.
            "total_pages": total_pages,
            "has_prev": page > 1,
            "has_next": page < total_pages,
            "prev_params": _history_filters_query_with_page(filters, order, page - 1),
            "next_params": _history_filters_query_with_page(filters, order, page + 1),
            "page_items": page_items,
        },
    )


@app.route("/leaderboard")
def leaderboard():
    # Route `/leaderboard` je veřejná tabulka výsledků.
    per_page = 15
    # Načtení všech filtrů (username, category, difficulty, date od-do) z URL.
    filters = _get_filters(request.args)
    order = request.args.get("order", "score_desc")
    page = _to_int(request.args.get("page")) or 1
    if page < 1:
        page = 1

    # Validace datum filtrů.
    raw_date_from = filters.get("date_from", "")
    raw_date_to = filters.get("date_to", "")
    filters["date_from"] = _to_iso_date_or_empty(raw_date_from)
    filters["date_to"] = _to_iso_date_or_empty(raw_date_to)

    if raw_date_from and not filters["date_from"]:
        flash("Datum od má neplatný formát.", "warning")
    if raw_date_to and not filters["date_to"]:
        flash("Datum do má neplatný formát.", "warning")
    if filters["date_from"] and filters["date_to"] and filters["date_to"] < filters["date_from"]:
        filters["date_to"] = filters["date_from"]
        flash("Datum do nemůže být menší než datum od. Automaticky jsem ho upravil.", "warning")

    # Stránkování.
    total_rows = count_filtered_results(filters=filters)
    total_pages = max(1, (total_rows + per_page - 1) // per_page)
    if page > total_pages:
        page = total_pages

    # Načtení řádků pro aktuální stránku.
    rows = get_filtered_results(
        filters=filters,
        order=order,
        limit=per_page,
        offset=(page - 1) * per_page,
    )

    start_page = max(1, page - 2)
    end_page = min(total_pages, page + 2)
    # Cyklus: vytvoří položky stránkování po jedné.
    page_items = [
        {"number": p, "params": _filters_query_with_page(filters, order, p)}
        for p in range(start_page, end_page + 1)
    ]

    options = {
        # Data pro dropdown kategorií v šabloně.
        "categories": get_categories(),
        # Data pro dropdown obtížností v šabloně.
        "difficulties": get_difficulties(),
    }

    return render_template(
        # HTML soubor, který se načte: `app/templates/leaderboard.html`.
        "leaderboard.html",
        rows=rows,
        filters=filters,
        options=options,
        order=order,
        export_params=_filters_query_dict(filters, order),
        pagination={
            "page": page,
            "per_page": per_page,
            "total_rows": total_rows,
            "total_pages": total_pages,
            "has_prev": page > 1,
            "has_next": page < total_pages,
            "prev_params": _filters_query_with_page(filters, order, page - 1),
            "next_params": _filters_query_with_page(filters, order, page + 1),
            "page_items": page_items,
        },
    )


@app.route("/results/export.csv")
def results_export_csv():
    # Route `/results/export.csv` vrací soubor CSV.
    # Nevykresluje HTML šablonu, ale rovnou textový soubor ke stažení.
    filters = _get_filters(request.args)
    order = request.args.get("order", "score_desc")
    filters["date_from"] = _to_iso_date_or_empty(filters.get("date_from", ""))
    filters["date_to"] = _to_iso_date_or_empty(filters.get("date_to", ""))
    if filters["date_from"] and filters["date_to"] and filters["date_to"] < filters["date_from"]:
        filters["date_to"] = filters["date_from"]

    # Pro export bereme všechna data podle filtrů (bez limitu stránkování).
    rows = get_filtered_results(filters=filters, order=order, limit=None)

    # `StringIO` vytvoří "virtuální soubor" v paměti.
    output = StringIO()
    # `csv.writer(...)` se stará o správné oddělovače/sloupce v CSV formátu.
    writer = csv.writer(output)
    # Hlavička CSV sloupců.
    writer.writerow(
        ["username", "category", "difficulty", "score", "total_questions", "duration_seconds", "played_at"]
    )

    # Projdeme každý řádek výsledků a zapíšeme ho do CSV.
    for row in rows:
        writer.writerow(
            [
                row["username"],
                row["category"],
                row["difficulty"],
                row["score"],
                row["total_questions"],
                row["duration_seconds"],
                row["played_at"],
            ]
        )

    csv_data = output.getvalue()
    # `csv_data` je teď jeden velký text se sloupci oddělenými čárkou.
    # Vracíme HTTP response typu CSV + header pro stažení souboru.
    return Response(
        csv_data,
        mimetype="text/csv",
        # `Content-Disposition: attachment` řekne prohlížeči "stáhni soubor".
        # `filename=...` je návrh názvu, který se má předvyplnit při uložení.
        headers={"Content-Disposition": "attachment; filename=leaderboard_export.csv"},
    )


@app.route("/stats")
def stats_page():
    # Route `/stats` = stránka statistik.
    # Grafy se vykreslují na frontendu (např. Chart.js).
    category_stats = get_stats_by_category()
    difficulty_stats = get_stats_by_difficulty()
    top_users = get_top_users(limit=10)

    return render_template(
        # HTML soubor, který se načte: `app/templates/stats.html`.
        "stats.html",
        category_stats=category_stats,
        difficulty_stats=difficulty_stats,
        top_users=top_users,
    )


# ---------------------------------------------------------------------------
# Admin sekce
# ---------------------------------------------------------------------------

@app.route("/admin")
@admin_required
def admin_dashboard():
    # Route `/admin` = hlavní rozcestník administrace.
    # HTML soubor, který se načte: `app/templates/admin/dashboard.html`.
    return render_template("admin/dashboard.html")


@app.route("/admin/reports", methods=["GET", "POST"])
@admin_required
def admin_reports():
    # Route `/admin/reports` = přehled hlášení otázek + změna statusu.
    allowed_statuses = {"new", "reviewed", "resolved", "rejected"}
    raw_status = (request.args.get("status") or "").strip().lower()
    # Tady se program rozhoduje:
    # pokud status není mezi povolenými, zahodíme ho.
    status = raw_status if raw_status in allowed_statuses else ""
    if raw_status and not status:
        flash("Neplatný filtr statusu. Zobrazuji všechna hlášení.", "warning")

    page = _to_int(request.args.get("page")) or 1
    # Stránka nesmí být menší než 1, proto korekce.
    if page < 1:
        page = 1
    per_page = 15

    # POST větev = změna statusu konkrétního hlášení.
    if request.method == "POST":
        report_id = _to_int(request.form.get("report_id"))
        new_status = (request.form.get("new_status") or "").strip().lower()
        current_status = (request.form.get("current_status") or "").strip().lower()
        redirect_page = _to_int(request.form.get("redirect_page")) or 1
        # Po akci se vracíme na stejný filtr + stránku.
        redirect_params = _admin_reports_query_dict(current_status if current_status in allowed_statuses else "", redirect_page)

        if not report_id:
            flash("Neplatné ID hlášení.", "danger")
            return redirect(url_for("admin_reports", **redirect_params))

        try:
            # Uložení nového statusu do DB.
            changed = update_question_report_status(
                report_id=report_id,
                new_status=new_status,
                # `resolved_by` si ukládáme kvůli historii, kdo status změnil.
                resolved_by=session.get("user_id"),
            )
            # `changed` typicky znamená počet upravených řádků.
            if changed:
                flash("Status hlášení byl úspěšně změněn.", "success")
            else:
                flash("Hlášení nebylo nalezeno nebo se nic nezměnilo.", "warning")
        except ValueError as exc:
            flash(str(exc), "danger")
        except Exception as exc:
            flash(f"Status hlášení se nepodařilo uložit: {exc}", "danger")

        return redirect(url_for("admin_reports", **redirect_params))

    # GET větev = načtení stránky přehledu.
    total_rows = count_question_reports(status=status or None)
    total_pages = max(1, (total_rows + per_page - 1) // per_page)
    if page > total_pages:
        page = total_pages

    rows = get_question_reports(
        status=status or None,
        limit=per_page,
        offset=(page - 1) * per_page,
    )

    start_page = max(1, page - 2)
    end_page = min(total_pages, page + 2)
    # Cyklus přes stránkování.
    page_items = [
        {"number": p, "params": _admin_reports_query_dict(status, p)}
        for p in range(start_page, end_page + 1)
    ]

    return render_template(
        # HTML soubor, který se načte: `app/templates/admin/reports.html`.
        "admin/reports.html",
        rows=rows,
        status=status,
        statuses=["new", "reviewed", "resolved", "rejected"],
        status_labels={
            # Překlad interních status kódů na text do UI.
            "new": "Nové",
            "reviewed": "Zkontrolované",
            "resolved": "Vyřešené",
            "rejected": "Zamítnuté",
        },
        pagination={
            "page": page,
            "total_rows": total_rows,
            "total_pages": total_pages,
            "has_prev": page > 1,
            "has_next": page < total_pages,
            "prev_params": _admin_reports_query_dict(status, page - 1),
            "next_params": _admin_reports_query_dict(status, page + 1),
            "page_items": page_items,
        },
    )


@app.route("/admin/questions")
@admin_required
def admin_questions():
    # Route `/admin/questions` = seznam otázek s filtrováním a stránkováním.
    per_page = 15
    search = (request.args.get("q") or "").strip()
    category_id = _to_int(request.args.get("category_id"))
    difficulty_id = _to_int(request.args.get("difficulty_id"))
    page = _to_int(request.args.get("page")) or 1
    # Negativní/0 stránka nedává smysl, opravíme na první.
    if page < 1:
        page = 1

    # Spočítáme počet řádků kvůli stránkování.
    total_rows = count_questions(search=search, category_id=category_id, difficulty_id=difficulty_id)
    total_pages = max(1, (total_rows + per_page - 1) // per_page)
    if page > total_pages:
        page = total_pages

    # Načteme otázky pro aktuální stránku.
    questions = list_questions(
        search=search,
        category_id=category_id,
        difficulty_id=difficulty_id,
        limit=per_page,
        offset=(page - 1) * per_page,
    )

    start_page = max(1, page - 2)
    end_page = min(total_pages, page + 2)
    # Pro každé číslo stránky připravíme URL parametry.
    page_items = [
        {
            "number": p,
            "params": _admin_questions_query_dict(search, category_id, difficulty_id, p),
        }
        for p in range(start_page, end_page + 1)
    ]

    return render_template(
        # HTML soubor, který se načte: `app/templates/admin/questions.html`.
        "admin/questions.html",
        questions=questions,
        categories=get_categories(),
        difficulties=get_difficulties(),
        search=search,
        category_id=category_id,
        difficulty_id=difficulty_id,
        pagination={
            "page": page,
            "total_rows": total_rows,
            "total_pages": total_pages,
            "has_prev": page > 1,
            "has_next": page < total_pages,
            "prev_params": _admin_questions_query_dict(search, category_id, difficulty_id, page - 1),
            "next_params": _admin_questions_query_dict(search, category_id, difficulty_id, page + 1),
            "page_items": page_items,
        },
    )


def _read_question_payload(form):
    # Načte data jedné otázky z formuláře a zkontroluje je.
    payload = {
        # Každé textové pole ořežeme (`strip`) kvůli mezerám na začátku/konci.
        "question_text": (form.get("question_text") or "").strip(),
        "answer_a": (form.get("answer_a") or "").strip(),
        "answer_b": (form.get("answer_b") or "").strip(),
        "answer_c": (form.get("answer_c") or "").strip(),
        "answer_d": (form.get("answer_d") or "").strip(),
        "correct_answer": (form.get("correct_answer") or "").strip().upper(),
        "difficulty_id": _to_int(form.get("difficulty_id")),
    }
    # Kategorie je v DB samostatně, proto ji držíme mimo `payload`.
    category_id = _to_int(form.get("category_id"))

    # Povinné pole: text otázky.
    if not payload["question_text"]:
        raise ValueError("Text otázky je povinný.")

    # Cyklus: zkontrolujeme, že všechny odpovědi A-D jsou vyplněné.
    for key in ("answer_a", "answer_b", "answer_c", "answer_d"):
        if not payload[key]:
            raise ValueError("Všechny odpovědi A-D musí být vyplněné.")

    # Správná odpověď musí být jen A/B/C/D.
    if payload["correct_answer"] not in {"A", "B", "C", "D"}:
        raise ValueError("Správná odpověď musí být jedna z možností A, B, C nebo D.")

    if not payload["difficulty_id"]:
        raise ValueError("Vyber obtížnost.")

    if not category_id:
        raise ValueError("Vyber kategorii.")

    # Vracíme validovaná data a vybranou kategorii.
    return payload, category_id


def _read_bulk_question_payloads(form):
    # Načte více otázek z hromadného formuláře a každou ověří.
    # `getlist(...)` vrací seznam hodnot stejného názvu pole.
    question_text_list = form.getlist("question_text[]")
    answer_a_list = form.getlist("answer_a[]")
    answer_b_list = form.getlist("answer_b[]")
    answer_c_list = form.getlist("answer_c[]")
    answer_d_list = form.getlist("answer_d[]")
    correct_answer_list = form.getlist("correct_answer[]")
    difficulty_id_list = form.getlist("difficulty_id[]")
    category_id_list = form.getlist("category_id[]")

    # Zjistíme nejdelší seznam, abychom věděli kolik "řádků" formuláře projít.
    max_len = max(
        len(question_text_list),
        len(answer_a_list),
        len(answer_b_list),
        len(answer_c_list),
        len(answer_d_list),
        len(correct_answer_list),
        len(difficulty_id_list),
        len(category_id_list),
    )

    if max_len == 0:
        raise ValueError("Formulář neobsahuje žádná data.")

    payloads = []
    # Procházíme řádky formuláře jeden po druhém.
    for i in range(max_len):
        # Když některý seznam nemá daný index, použijeme prázdnou hodnotu.
        question_text = (question_text_list[i] if i < len(question_text_list) else "").strip()
        answer_a = (answer_a_list[i] if i < len(answer_a_list) else "").strip()
        answer_b = (answer_b_list[i] if i < len(answer_b_list) else "").strip()
        answer_c = (answer_c_list[i] if i < len(answer_c_list) else "").strip()
        answer_d = (answer_d_list[i] if i < len(answer_d_list) else "").strip()
        correct_answer = (correct_answer_list[i] if i < len(correct_answer_list) else "").strip().upper()
        difficulty_id = _to_int(difficulty_id_list[i] if i < len(difficulty_id_list) else None)
        category_id = _to_int(category_id_list[i] if i < len(category_id_list) else None)

        # Prázdný blok (uživatel ho nevyplnil) přeskočíme.
        if not any([question_text, answer_a, answer_b, answer_c, answer_d, correct_answer, difficulty_id, category_id]):
            # Prázdný řádek nebereme jako chybu, jen ho přeskočíme.
            continue

        # Pro uživatelské chyby zobrazujeme číslování od 1.
        row_no = i + 1
        # Tady se program rozhoduje: jakmile je něco neplatné, vrací konkrétní chybu.
        if not question_text:
            raise ValueError(f"Otázka #{row_no}: text otázky je povinný.")
        if not all([answer_a, answer_b, answer_c, answer_d]):
            raise ValueError(f"Otázka #{row_no}: vyplň všechny odpovědi A-D.")
        if correct_answer not in {"A", "B", "C", "D"}:
            raise ValueError(f"Otázka #{row_no}: správná odpověď musí být A/B/C/D.")
        if not difficulty_id:
            raise ValueError(f"Otázka #{row_no}: vyber obtížnost.")
        if not category_id:
            raise ValueError(f"Otázka #{row_no}: vyber kategorii.")

        # Když řádek prošel validací, uložíme ho do výsledného seznamu.
        payloads.append(
            {
                "question_text": question_text,
                "answer_a": answer_a,
                "answer_b": answer_b,
                "answer_c": answer_c,
                "answer_d": answer_d,
                "correct_answer": correct_answer,
                "difficulty_id": difficulty_id,
                "category_id": category_id,
            }
        )

    # Po průchodu musí být aspoň jedna validní otázka.
    if not payloads:
        raise ValueError("Vyplň alespoň jednu otázku.")

    return payloads


@app.route("/admin/questions/new", methods=["GET", "POST"])
@admin_required
def admin_question_new():
    # Route `/admin/questions/new` = vytvoření nové otázky / více otázek najednou.
    if request.method == "POST":
        try:
            # 1) Načteme a zvalidujeme vstup.
            payloads = _read_bulk_question_payloads(request.form)
            # 2) Uložíme otázky do DB.
            created = create_questions_bulk(payloads, created_by=session.get("user_id"))
            # `created` je počet skutečně vložených otázek.
            flash(f"Otázky byly úspěšně vytvořeny. Počet: {created}", "success")
            return redirect(url_for("admin_questions"))
        except ValueError as exc:
            flash(str(exc), "danger")
        except Exception as exc:
            flash(f"Nepodařilo se uložit otázky: {exc}", "danger")

    return render_template(
        # HTML soubor, který se načte: `app/templates/admin/question_form.html`.
        "admin/question_form.html",
        mode="new",
        # U nové otázky posíláme prázdný slovník, aby formulář začínal čistě.
        question={},
        categories=get_categories(),
        difficulties=get_difficulties(),
    )


@app.route("/admin/categories", methods=["GET", "POST"])
@admin_required
def admin_categories():
    # Route `/admin/categories`:
    # - zobrazení kategorií
    # - vytvoření/smazání/úprava popisu
    if request.method == "POST":
        # Formulář posílá typ akce (create, delete, update_description).
        action = (request.form.get("action") or "").strip()

        if action == "create":
            name = (request.form.get("name") or "").strip()
            description = (request.form.get("description") or "").strip()

            if len(name) < 2:
                flash("Název kategorie musí mít aspoň 2 znaky.", "danger")
            else:
                try:
                    # Vytvoření nové kategorie.
                    create_category(name, description)
                    flash("Kategorie byla úspěšně přidána.", "success")
                    # Redirect zabrání opětovnému odeslání formuláře po refreshi.
                    return redirect(url_for("admin_categories"))
                except mysql.connector.errors.IntegrityError:
                    flash("Kategorie s tímto názvem už existuje.", "danger")
                except Exception as exc:
                    flash(f"Nepodařilo se přidat kategorii: {exc}", "danger")

        elif action == "delete":
            category_id = _to_int(request.form.get("category_id"))
            # Tady se program rozhoduje: bez platného ID nelze mazat.
            if not category_id:
                flash("Neplatná kategorie pro smazání.", "danger")
            else:
                try:
                    deleted = delete_category(category_id)
                    # `deleted` je počet smazaných řádků.
                    if deleted:
                        flash("Kategorie byla úspěšně smazána.", "success")
                    else:
                        flash("Kategorie nebyla nalezena.", "warning")
                    return redirect(url_for("admin_categories"))
                except mysql.connector.errors.IntegrityError:
                    flash(
                        "Tuto kategorii nelze smazat, protože je navázaná na výsledky nebo další data.",
                        "danger",
                    )
                except Exception as exc:
                    flash(f"Nepodařilo se smazat kategorii: {exc}", "danger")
        elif action == "update_description":
            category_id = _to_int(request.form.get("category_id"))
            description = (request.form.get("description") or "").strip()
            if not category_id:
                flash("Neplatná kategorie pro úpravu popisu.", "danger")
            else:
                try:
                    # Aktualizace popisu.
                    changed = update_category_description(category_id, description)
                    if changed:
                        flash("Popis kategorie byl úspěšně upraven.", "success")
                    else:
                        flash("Kategorie nebyla nalezena nebo popis zůstal stejný.", "warning")
                    return redirect(url_for("admin_categories"))
                except Exception as exc:
                    flash(f"Nepodařilo se upravit popis kategorie: {exc}", "danger")
        else:
            flash("Neplatná akce ve správě kategorií.", "danger")

    # HTML soubor, který se načte: `app/templates/admin/categories.html`.
    return render_template("admin/categories.html", categories=get_categories_with_stats())


@app.route("/admin/questions/<int:question_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_question_edit(question_id: int):
    # Route `/admin/questions/<id>/edit` = úprava jedné existující otázky.
    question = get_question_by_id(question_id)
    # Pokud otázka neexistuje, vrátíme 404.
    if not question:
        # `abort(404)` vrátí standardní HTTP chybu "Stránka nenalezena".
        # Kód pod tímto řádkem už se v této větvi nespustí.
        abort(404)

    if request.method == "POST":
        try:
            # Načtení + validace dat z formuláře.
            payload, category_id = _read_question_payload(request.form)
            # Uložení změn do DB.
            update_question(question_id, payload, category_id)
            flash("Otázka byla úspěšně upravena.", "success")
            return redirect(url_for("admin_questions"))
        except ValueError as exc:
            # U uživatelské/validační chyby ukážeme přesně text, který funkce vyhodila.
            flash(str(exc), "danger")
        except Exception as exc:
            flash(f"Nepodařilo se upravit otázku: {exc}", "danger")

        # Po chybě vracíme hodnoty z formuláře, aby je admin neztratil.
        question = {
            "question_id": question_id,
            "question_text": request.form.get("question_text"),
            "answer_a": request.form.get("answer_a"),
            "answer_b": request.form.get("answer_b"),
            "answer_c": request.form.get("answer_c"),
            "answer_d": request.form.get("answer_d"),
            "correct_answer": request.form.get("correct_answer"),
            "difficulty_id": _to_int(request.form.get("difficulty_id")),
            "category_id": _to_int(request.form.get("category_id")),
        }

    return render_template(
        # HTML soubor, který se načte: `app/templates/admin/question_form.html`.
        "admin/question_form.html",
        mode="edit",
        question=question,
        categories=get_categories(),
        difficulties=get_difficulties(),
    )


@app.route("/admin/questions/<int:question_id>/delete", methods=["POST"])
@admin_required
def admin_question_delete(question_id: int):
    # Route `/admin/questions/<id>/delete` = smazání otázky.
    deleted = delete_question(question_id)
    # Tady se program rozhoduje podle toho, jestli DB opravdu něco smazala.
    if deleted:
        flash("Otázka byla smazána.", "success")
    else:
        flash("Otázku se nepodařilo smazat (neexistuje).", "warning")
    return redirect(url_for("admin_questions"))


@app.route("/admin/results", methods=["GET", "POST"])
@admin_required
def admin_results():
    # Route `/admin/results` = správa výsledků (filtr, mazání, export/import).
    filters = _get_filters(request.args)
    # Výchozí řazení v adminu je podle ID od nejnovějších.
    order = request.args.get("order", "id_desc")

    # Validace datových filtrů.
    raw_date_from = filters.get("date_from", "")
    raw_date_to = filters.get("date_to", "")
    filters["date_from"] = _to_iso_date_or_empty(raw_date_from)
    filters["date_to"] = _to_iso_date_or_empty(raw_date_to)

    if raw_date_from and not filters["date_from"]:
        flash("Datum od má neplatný formát.", "warning")
    if raw_date_to and not filters["date_to"]:
        flash("Datum do má neplatný formát.", "warning")

    if filters["date_from"] and filters["date_to"] and filters["date_to"] < filters["date_from"]:
        filters["date_to"] = filters["date_from"]
        flash("Datum do nemůže být menší než datum od. Automaticky jsem ho upravil.", "warning")

    # POST větev = hromadné mazání vybraných výsledků.
    if request.method == "POST":
        raw_ids = request.form.getlist("selected_results")
        # Seznam převedeme na int a neplatné hodnoty zahodíme.
        result_ids = [rid for rid in (_to_int(v) for v in raw_ids) if rid is not None]

        if not result_ids:
            flash("Nejdřív vyber alespoň jeden výsledek ke smazání.", "warning")
        else:
            deleted = delete_results_by_ids(result_ids)
            flash(f"Smazáno záznamů: {deleted}", "success")

        return redirect(url_for("admin_results", **_filters_query_dict(filters, order)))

    # GET větev = načtení dat pro tabulku.
    rows = get_filtered_results(filters=filters, order=order, limit=500)
    options = {
        # Filtry do admin tabulky výsledků.
        "categories": get_categories(),
        "difficulties": get_difficulties(),
        "users": get_users_simple(),
    }

    return render_template(
        # HTML soubor, který se načte: `app/templates/admin/results.html`.
        "admin/results.html",
        rows=rows,
        options=options,
        filters=filters,
        order=order,
        export_params=_filters_query_dict(filters, order),
    )


@app.route("/results/import", methods=["POST"])
@admin_required
def results_import():
    # Route `/results/import` = import CSV do výsledků.
    # Soubor se očekává ve formulářovém poli `csv_file`.
    csv_file = request.files.get("csv_file")
    # `request.files` obsahuje nahrané soubory z formuláře (`enctype="multipart/form-data"`).

    try:
        # Import je transakční (řeší DB vrstva).
        inserted = import_results_csv(csv_file)
        flash(f"Import proběhl úspěšně. Vloženo řádků: {inserted}", "success")
    except ValueError as exc:
        flash(str(exc), "danger")
    except Exception as exc:
        flash(f"Import selhal: {exc}", "danger")

    return redirect(url_for("admin_results"))


@app.route("/admin/users", methods=["GET", "POST"])
@admin_required
def admin_users():
    # Route `/admin/users` = seznam uživatelů + administrace účtů.
    # Akce:
    # - smazání uživatele
    # - přejmenování uživatele
    # - změna hesla uživatele
    users = get_users_simple()
    # `selected_user_id` dává smysl jen u POST požadavku.
    selected_user_id = _to_int(request.form.get("selected_user_id")) if request.method == "POST" else None

    if request.method == "POST":
        action = (request.form.get("admin_action") or "").strip()

        # Tady se program rozhoduje: nejdřív musí být vybraný uživatel.
        if not selected_user_id:
            flash("Nejdřív vyber uživatele pro úpravu.", "warning")
        else:
            # Najdeme vybraného uživatele v aktuálním seznamu.
            # `next(...)` vrátí první shodu z cyklu; když žádná není, vrátí default `None`.
            selected_user = next((u for u in users if u["user_id"] == selected_user_id), None)
            if not selected_user:
                flash("Vybraný uživatel neexistuje.", "danger")
            elif action == "delete":
                # Bezpečnost: admin nesmí smazat sám sebe.
                if selected_user["user_id"] == session.get("user_id"):
                    flash("Nemůžeš smazat aktuálně přihlášeného admina.", "danger")
                else:
                    # Bezpečnost: nesmí zmizet poslední admin.
                    admin_count = sum(1 for u in users if u["role"] == "admin")
                    if selected_user["role"] == "admin" and admin_count <= 1:
                        flash("Nelze smazat posledního admina v systému.", "danger")
                    else:
                        deleted = delete_user_by_id(selected_user_id)
                        if deleted:
                            flash(f"Uživatel '{selected_user['username']}' byl smazán.", "success")
                            selected_user_id = None
                        else:
                            flash("Uživatele se nepodařilo smazat.", "danger")
            elif action == "rename":
                new_username = (request.form.get("new_username") or "").strip()
                if len(new_username) < 3:
                    flash("Nové uživatelské jméno musí mít aspoň 3 znaky.", "danger")
                else:
                    try:
                        # Přejmenování uživatele v DB.
                        changed = update_user_username(selected_user_id, new_username)
                        if changed:
                            flash(f"Uživatel byl přejmenován na '{new_username}'.", "success")
                        else:
                            flash("Přejmenování neproběhlo.", "warning")
                    except mysql.connector.errors.IntegrityError:
                        flash("Toto uživatelské jméno už existuje.", "danger")
            elif action == "password":
                new_password = request.form.get("new_password") or ""
                new_password2 = request.form.get("new_password2") or ""
                # Základní validace nového hesla.
                if len(new_password) < 4:
                    flash("Nové heslo musí mít aspoň 4 znaky.", "danger")
                elif new_password != new_password2:
                    flash("Nová hesla se neshodují.", "danger")
                else:
                    # Změna hesla (DB vrstva ukládá hash, ne čisté heslo).
                    changed = update_user_password(selected_user_id, new_password)
                    if changed:
                        flash(f"Heslo uživatele '{selected_user['username']}' bylo změněno.", "success")
                    else:
                        flash("Změna hesla neproběhla.", "warning")
            else:
                flash("Neplatná akce.", "danger")

        # Po akci načteme uživatele znovu, aby stránka ukazovala aktuální stav.
        users = get_users_simple()

    return render_template(
        # HTML soubor, který se načte: `app/templates/admin/users.html`.
        "admin/users.html",
        users=users,
        selected_user_id=selected_user_id,
    )
