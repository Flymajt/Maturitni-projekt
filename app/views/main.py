import csv
import re
from datetime import date
from functools import wraps
from io import StringIO

import mysql.connector
from flask import (
    Response,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from app import app
from app.db import (
    create_category,
    create_user,
    create_questions_bulk,
    count_questions,
    count_filtered_results,
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
    get_stats_by_category,
    get_stats_by_difficulty,
    get_top_users,
    get_users_simple,
    import_results_csv,
    list_questions,
    get_user_profile_summary,
    update_category_description,
    update_user_profile_title,
    update_user_password,
    update_user_username,
    update_question,
    verify_login,
)

LEVEL_TITLES = [
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
    """Vrátí název levelu podle definovaných milníků."""
    for min_level, title in LEVEL_TITLES:
        if level >= min_level:
            return title
    return "Začátečník"


def _available_titles_for(level: int):
    """Vrátí seznam title, které si hráč může zvolit pro daný level."""
    unlocked = [title for min_level, title in LEVEL_TITLES if level >= min_level]
    return list(reversed(unlocked))

def _to_int(value):
    """Bezpečný převod query/form hodnoty na int."""
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _get_filters(args):
    """Posbírá filtry leaderboardu/results z URL parametrů."""
    return {
        "username": (args.get("username") or "").strip(),
        "category_id": _to_int(args.get("category_id")),
        "difficulty_id": _to_int(args.get("difficulty_id")),
        "date_from": (args.get("date_from") or "").strip(),
        "date_to": (args.get("date_to") or "").strip(),
    }


def _to_iso_date_or_empty(value: str) -> str:
    """Vrátí datum ve formátu YYYY-MM-DD, nebo prázdný řetězec při neplatné hodnotě."""
    if not value:
        return ""
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        return ""

def _filters_query_dict(filters, order):
    """Převede aktuální filtry do dictu vhodného pro url_for(..., **params)."""
    params = {"order": order}
    for key, value in filters.items():
        if value not in (None, ""):
            params[key] = value
    return params


def _filters_query_with_page(filters, order, page: int):
    """Převede filtry do URL params včetně stránkování."""
    params = _filters_query_dict(filters, order)
    if page > 1:
        params["page"] = page
    return params


def _admin_questions_query_dict(
    search: str,
    category_id: int | None,
    difficulty_id: int | None,
    page: int,
):
    """Převede filtry správy otázek do URL parametrů včetně stránky."""
    params = {}
    if search:
        params["q"] = search
    if category_id:
        params["category_id"] = category_id
    if difficulty_id:
        params["difficulty_id"] = difficulty_id
    if page > 1:
        params["page"] = page
    return params


def get_current_user():
    """Vrátí uživatele ze session, nebo None pokud není přihlášen."""
    user_id = session.get("user_id")
    if not user_id:
        return None
    return {
        "user_id": user_id,
        "username": session.get("username"),
        "role": session.get("role"),
    }


@app.context_processor
def inject_current_user():
    """Zpřístupní current_user do všech Jinja šablon."""
    return {"current_user": get_current_user()}


@app.template_filter("format_duration")
def format_duration(seconds):
    """Převede sekundy na text mm:ss nebo hh:mm:ss."""
    if seconds in (None, ""):
        return "-"
    try:
        value = int(seconds)
    except (TypeError, ValueError):
        return "-"
    if value < 0:
        return "-"

    hours, rest = divmod(value, 3600)
    minutes, secs = divmod(rest, 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def login_required(view):
    """Decorator pro stránky dostupné jen přihlášenému uživateli."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Pro pokračování se přihlas.", "warning")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    """Decorator pro admin-only stránky."""

    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if session.get("role") != "admin":
            flash("Do této části má přístup pouze admin.", "danger")
            return redirect(url_for("home"))
        return view(*args, **kwargs)

    return wrapped


# ---------------------------------------------------------------------------
# Veřejné stránky
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    """Úvodní stránka systému s rozdílným obsahem podle login stavu."""
    recent_results = get_recent_results(limit=8)
    return render_template("index.html", recent_results=recent_results)


@app.route("/dbtest")
def dbtest():
    """Rychlý test, že web část komunikuje s MySQL databází."""
    row = fetch_one("SELECT 1 AS ok;")
    return f"MySQL OK: {row['ok']}"


@app.route("/login", methods=["GET", "POST"])
def login():
    """Web login pro všechny uživatele systému."""
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        if not username or not password:
            flash("Vyplň uživatelské jméno i heslo.", "danger")
            return render_template("login.html")

        user = verify_login(username, password)
        if not user:
            flash("Neplatné přihlašovací údaje.", "danger")
            return render_template("login.html")

        session["user_id"] = user["user_id"]
        session["username"] = user["username"]
        session["role"] = user["role"]
        flash(f"Přihlášen jako {user['username']}.", "success")

        next_url = request.args.get("next", "")
        if next_url.startswith("/"):
            return redirect(next_url)

        if user["role"] == "admin":
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("home"))

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Web registrace nového uživatele."""
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        password2 = request.form.get("password2") or ""

        if not username or not password or not password2:
            flash("Vyplň všechna registrační pole.", "danger")
            return render_template("register.html")

        if len(username) < 3:
            flash("Uživatelské jméno musí mít aspoň 3 znaky.", "danger")
            return render_template("register.html")

        if len(password) < 4:
            flash("Heslo musí mít aspoň 4 znaky.", "danger")
            return render_template("register.html")

        if not re.search(r"[A-Z]", password) or not re.search(r"\d", password):
            flash("Heslo musí obsahovat aspoň jedno velké písmeno a jedno číslo.", "danger")
            return render_template("register.html")

        if password != password2:
            flash("Hesla se neshodují.", "danger")
            return render_template("register.html")

        try:
            create_user(username, password, role="user")
            flash("Registrace proběhla úspěšně. Teď se přihlas.", "success")
            return redirect(url_for("login"))
        except mysql.connector.errors.IntegrityError:
            flash("Toto uživatelské jméno už existuje.", "danger")
        except Exception as exc:
            flash(f"Registrace selhala: {exc}", "danger")

    return render_template("register.html")


@app.route("/logout")
@login_required
def logout():
    """Odhlásí uživatele a smaže session data."""
    session.clear()
    flash("Byl jsi úspěšně odhlášen.", "info")
    return redirect(url_for("home"))


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    """Profil přihlášeného uživatele včetně XP, levelu a title."""
    user_id = session.get("user_id")
    profile_data = get_user_profile_summary(user_id)
    if not profile_data:
        flash("Profil se nepodařilo načíst.", "danger")
        return redirect(url_for("home"))

    available_titles = _available_titles_for(profile_data["level"])
    selected_title = profile_data.get("profile_title")
    if selected_title and selected_title not in available_titles:
        selected_title = None

    if request.method == "POST":
        new_title = (request.form.get("profile_title") or "").strip()
        if new_title and new_title not in available_titles:
            flash("Vybraný title není dostupný pro tvůj aktuální level.", "danger")
        else:
            update_user_profile_title(user_id, new_title or None)
            flash("Profilový title byl uložen.", "success")
            return redirect(url_for("profile"))

    auto_title = _level_title_for(profile_data["level"])
    current_title = selected_title or auto_title

    return render_template(
        "profile.html",
        profile=profile_data,
        auto_title=auto_title,
        current_title=current_title,
        available_titles=available_titles,
        selected_title=selected_title,
    )


@app.route("/leaderboard")
def leaderboard():
    """Veřejný leaderboard s filtrováním, řazením a exportem do CSV."""
    per_page = 15
    filters = _get_filters(request.args)
    order = request.args.get("order", "score_desc")
    page = _to_int(request.args.get("page")) or 1
    if page < 1:
        page = 1

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

    total_rows = count_filtered_results(filters=filters)
    total_pages = max(1, (total_rows + per_page - 1) // per_page)
    if page > total_pages:
        page = total_pages

    rows = get_filtered_results(
        filters=filters,
        order=order,
        limit=per_page,
        offset=(page - 1) * per_page,
    )

    start_page = max(1, page - 2)
    end_page = min(total_pages, page + 2)
    page_items = [
        {"number": p, "params": _filters_query_with_page(filters, order, p)}
        for p in range(start_page, end_page + 1)
    ]

    options = {
        "categories": get_categories(),
        "difficulties": get_difficulties(),
    }

    return render_template(
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
    """Exportuje právě filtrované výsledky leaderboardu do CSV."""
    filters = _get_filters(request.args)
    order = request.args.get("order", "score_desc")
    filters["date_from"] = _to_iso_date_or_empty(filters.get("date_from", ""))
    filters["date_to"] = _to_iso_date_or_empty(filters.get("date_to", ""))
    if filters["date_from"] and filters["date_to"] and filters["date_to"] < filters["date_from"]:
        filters["date_to"] = filters["date_from"]

    rows = get_filtered_results(filters=filters, order=order, limit=None)

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["username", "category", "difficulty", "score", "total_questions", "duration_seconds", "played_at"]
    )

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
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=leaderboard_export.csv"},
    )


@app.route("/stats")
def stats_page():
    """Stránka statistik s grafy (Chart.js)."""
    category_stats = get_stats_by_category()
    difficulty_stats = get_stats_by_difficulty()
    top_users = get_top_users(limit=10)

    return render_template(
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
    """Hlavní dashboard administrace."""
    return render_template("admin/dashboard.html")


@app.route("/admin/questions")
@admin_required
def admin_questions():
    """Seznam otázek s filtrováním a akcemi edit/delete."""
    per_page = 15
    search = (request.args.get("q") or "").strip()
    category_id = _to_int(request.args.get("category_id"))
    difficulty_id = _to_int(request.args.get("difficulty_id"))
    page = _to_int(request.args.get("page")) or 1
    if page < 1:
        page = 1

    total_rows = count_questions(search=search, category_id=category_id, difficulty_id=difficulty_id)
    total_pages = max(1, (total_rows + per_page - 1) // per_page)
    if page > total_pages:
        page = total_pages

    questions = list_questions(
        search=search,
        category_id=category_id,
        difficulty_id=difficulty_id,
        limit=per_page,
        offset=(page - 1) * per_page,
    )

    start_page = max(1, page - 2)
    end_page = min(total_pages, page + 2)
    page_items = [
        {
            "number": p,
            "params": _admin_questions_query_dict(search, category_id, difficulty_id, p),
        }
        for p in range(start_page, end_page + 1)
    ]

    return render_template(
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
    """Načte a validuje data otázky z formuláře."""
    payload = {
        "question_text": (form.get("question_text") or "").strip(),
        "answer_a": (form.get("answer_a") or "").strip(),
        "answer_b": (form.get("answer_b") or "").strip(),
        "answer_c": (form.get("answer_c") or "").strip(),
        "answer_d": (form.get("answer_d") or "").strip(),
        "correct_answer": (form.get("correct_answer") or "").strip().upper(),
        "difficulty_id": _to_int(form.get("difficulty_id")),
    }
    category_id = _to_int(form.get("category_id"))

    if not payload["question_text"]:
        raise ValueError("Text otázky je povinný.")

    for key in ("answer_a", "answer_b", "answer_c", "answer_d"):
        if not payload[key]:
            raise ValueError("Všechny odpovědi A-D musí být vyplněné.")

    if payload["correct_answer"] not in {"A", "B", "C", "D"}:
        raise ValueError("Správná odpověď musí být jedna z možností A, B, C nebo D.")

    if not payload["difficulty_id"]:
        raise ValueError("Vyber obtížnost.")

    if not category_id:
        raise ValueError("Vyber kategorii.")

    return payload, category_id


def _read_bulk_question_payloads(form):
    """Načte a validuje více otázek z hromadného formuláře."""
    question_text_list = form.getlist("question_text[]")
    answer_a_list = form.getlist("answer_a[]")
    answer_b_list = form.getlist("answer_b[]")
    answer_c_list = form.getlist("answer_c[]")
    answer_d_list = form.getlist("answer_d[]")
    correct_answer_list = form.getlist("correct_answer[]")
    difficulty_id_list = form.getlist("difficulty_id[]")
    category_id_list = form.getlist("category_id[]")

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
    for i in range(max_len):
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
            continue

        row_no = i + 1
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

    if not payloads:
        raise ValueError("Vyplň alespoň jednu otázku.")

    return payloads


@app.route("/admin/questions/new", methods=["GET", "POST"])
@admin_required
def admin_question_new():
    """Vytvoření jedné nebo více nových otázek."""
    if request.method == "POST":
        try:
            payloads = _read_bulk_question_payloads(request.form)
            created = create_questions_bulk(payloads, created_by=session.get("user_id"))
            flash(f"Otázky byly úspěšně vytvořeny. Počet: {created}", "success")
            return redirect(url_for("admin_questions"))
        except ValueError as exc:
            flash(str(exc), "danger")
        except Exception as exc:
            flash(f"Nepodařilo se uložit otázky: {exc}", "danger")

    return render_template(
        "admin/question_form.html",
        mode="new",
        question={},
        categories=get_categories(),
        difficulties=get_difficulties(),
    )


@app.route("/admin/categories", methods=["GET", "POST"])
@admin_required
def admin_categories():
    """Admin správa kategorií (vytvoření + přehled)."""
    if request.method == "POST":
        action = (request.form.get("action") or "").strip()

        if action == "create":
            name = (request.form.get("name") or "").strip()
            description = (request.form.get("description") or "").strip()

            if len(name) < 2:
                flash("Název kategorie musí mít aspoň 2 znaky.", "danger")
            else:
                try:
                    create_category(name, description)
                    flash("Kategorie byla úspěšně přidána.", "success")
                    return redirect(url_for("admin_categories"))
                except mysql.connector.errors.IntegrityError:
                    flash("Kategorie s tímto názvem už existuje.", "danger")
                except Exception as exc:
                    flash(f"Nepodařilo se přidat kategorii: {exc}", "danger")

        elif action == "delete":
            category_id = _to_int(request.form.get("category_id"))
            if not category_id:
                flash("Neplatná kategorie pro smazání.", "danger")
            else:
                try:
                    deleted = delete_category(category_id)
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

    return render_template("admin/categories.html", categories=get_categories_with_stats())


@app.route("/admin/questions/<int:question_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_question_edit(question_id: int):
    """Editace existující otázky."""
    question = get_question_by_id(question_id)
    if not question:
        abort(404)

    if request.method == "POST":
        try:
            payload, category_id = _read_question_payload(request.form)
            update_question(question_id, payload, category_id)
            flash("Otázka byla úspěšně upravena.", "success")
            return redirect(url_for("admin_questions"))
        except ValueError as exc:
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
        "admin/question_form.html",
        mode="edit",
        question=question,
        categories=get_categories(),
        difficulties=get_difficulties(),
    )


@app.route("/admin/questions/<int:question_id>/delete", methods=["POST"])
@admin_required
def admin_question_delete(question_id: int):
    """Smazání otázky z DB."""
    deleted = delete_question(question_id)
    if deleted:
        flash("Otázka byla smazána.", "success")
    else:
        flash("Otázku se nepodařilo smazat (neexistuje).", "warning")
    return redirect(url_for("admin_questions"))


@app.route("/admin/results", methods=["GET", "POST"])
@admin_required
def admin_results():
    """Admin správa výsledků: filtry, bulk delete, import/export."""
    filters = _get_filters(request.args)
    order = request.args.get("order", "id_desc")

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

    if request.method == "POST":
        raw_ids = request.form.getlist("selected_results")
        result_ids = [rid for rid in (_to_int(v) for v in raw_ids) if rid is not None]

        if not result_ids:
            flash("Nejdřív vyber alespoň jeden výsledek ke smazání.", "warning")
        else:
            deleted = delete_results_by_ids(result_ids)
            flash(f"Smazáno záznamů: {deleted}", "success")

        return redirect(url_for("admin_results", **_filters_query_dict(filters, order)))

    rows = get_filtered_results(filters=filters, order=order, limit=500)
    options = {
        "categories": get_categories(),
        "difficulties": get_difficulties(),
        "users": get_users_simple(),
    }

    return render_template(
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
    """Import výsledků z CSV (admin-only, transakčně)."""
    csv_file = request.files.get("csv_file")

    try:
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
    """
    Admin-only seznam registrovaných uživatelů.

    Ve spodní části stránky jsou hromadné úpravy:
    - vymazat uživatele,
    - přejmenovat uživatele,
    - změnit heslo uživatele.
    """
    users = get_users_simple()
    selected_user_id = _to_int(request.form.get("selected_user_id")) if request.method == "POST" else None

    if request.method == "POST":
        action = (request.form.get("admin_action") or "").strip()

        if not selected_user_id:
            flash("Nejdřív vyber uživatele pro úpravu.", "warning")
        else:
            selected_user = next((u for u in users if u["user_id"] == selected_user_id), None)
            if not selected_user:
                flash("Vybraný uživatel neexistuje.", "danger")
            elif action == "delete":
                if selected_user["user_id"] == session.get("user_id"):
                    flash("Nemůžeš smazat aktuálně přihlášeného admina.", "danger")
                else:
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
                if len(new_password) < 4:
                    flash("Nové heslo musí mít aspoň 4 znaky.", "danger")
                elif new_password != new_password2:
                    flash("Nová hesla se neshodují.", "danger")
                else:
                    changed = update_user_password(selected_user_id, new_password)
                    if changed:
                        flash(f"Heslo uživatele '{selected_user['username']}' bylo změněno.", "success")
                    else:
                        flash("Změna hesla neproběhla.", "warning")
            else:
                flash("Neplatná akce.", "danger")

        users = get_users_simple()

    return render_template(
        "admin/users.html",
        users=users,
        selected_user_id=selected_user_id,
    )

