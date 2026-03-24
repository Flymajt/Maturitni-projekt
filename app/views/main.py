from app import app
from flask import render_template
from app.db import fetch_one, get_leaderboard


@app.route("/")
def home():
    return render_template("index.html")


# url adera pro vyzkoušení jestli databaze je dostupna
@app.route("/dbtest")
def dbtest():
    row = fetch_one("SELECT 1 AS ok;")
    return f"MySQL OK: {row['ok']}"


@app.route("/leaderboard")
def leaderboard():
    rows = get_leaderboard(limit=20)
    return render_template("leaderboard.html", rows=rows)
