import hashlib
import secrets

import mysql.connector

from config import Config


def _hash_password(password: str) -> str:
    """Vrati heslo ve formatu salt$hash kompatibilnim s login logikou."""
    salt = secrets.token_hex(16)
    digest = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return f"{salt}${digest}"


def _question_seed_data():
    """Vrátí seznam všech otázek pro 3 původní kategorie."""
    return [
        # IT / Easy (3)
        ("IT", "Easy", "Co znamená zkratka CPU?", "Central Processing Unit", "Computer Power Unit", "Core Process Utility", "Central Program Usage", "A"),
        ("IT", "Easy", "Který z těchto je operační systém?", "Chrome", "Windows", "Python", "HTML", "B"),
        ("IT", "Easy", "Co je RAM?", "Pevný disk", "Operační systém", "Paměť pro běh programů", "Grafická karta", "C"),

        # IT / Medium (5)
        ("IT", "Medium", "Co znamená zkratka URL?", "Uniform Resource Locator", "Universal Render Language", "User Route Link", "Unified Resource Log", "A"),
        ("IT", "Medium", "K čemu slouží SQL?", "Úprava obrázků", "Dotazování databází", "Tvorba 3D modelů", "Komprese videa", "B"),
        ("IT", "Medium", "Co dělá protokol HTTPS oproti HTTP?", "Zrychlí internet", "Šifruje komunikaci", "Zakáže cookies", "Změní IP adresu", "B"),
        ("IT", "Medium", "Co je API?", "Rozhraní pro komunikaci mezi aplikacemi", "Grafický editor", "Typ databáze", "Šifrovací algoritmus", "A"),
        ("IT", "Medium", "K čemu slouží index v databázi?", "Ke zvětšení tabulky", "Ke zrychlení vyhledávání", "Ke smazání duplicit", "Ke změně datového typu", "B"),

        # IT / Hard (7)
        ("IT", "Hard", "Co je normalizace databáze (obecně)?", "Zvětšení tabulek", "Snížení redundance a zlepšení struktury", "Šifrování dat", "Zálohování databáze", "B"),
        ("IT", "Hard", "K čemu slouží JOIN v SQL?", "Smazání tabulky", "Spojení řádků z více tabulek", "Vytvoření indexu", "Změna datového typu", "B"),
        ("IT", "Hard", "Co je primární klíč (PK)?", "Sloupec s duplikáty", "Jedinečný identifikátor řádku", "Cizí klíč", "Náhodné číslo bez pravidel", "B"),
        ("IT", "Hard", "Co označuje zkratka ACID u databází?", "Sadu webových protokolů", "Typ SQL příkazů", "Sadu síťových vrstev", "Základní vlastnosti transakcí", "D"),
        ("IT", "Hard", "Co je deadlock v databázi?", "Automatické zálohování", "Vzájemné zablokování transakcí", "Komprese tabulek", "Chyba v indexu", "B"),
        ("IT", "Hard", "Jaká je časová složitost binárního vyhledávání?", "O(n)", "O(log n)", "O(n^2)", "O(1)", "B"),
        ("IT", "Hard", "Co je DNS?", "Datový šifrovací standard", "Správce databáze", "Systém pro překlad domén na IP adresy", "Nástroj pro kompilaci", "C"),

        # Sport / Easy (3)
        ("Sport", "Easy", "Kolik hráčů je na hřišti za jeden fotbalový tým?", "9", "10", "11", "12", "C"),
        ("Sport", "Easy", "Jak se jmenuje tenisové skóre 0?", "Zero", "Love", "Nil", "None", "B"),
        ("Sport", "Easy", "Jaký sport se hraje s oranžovým míčem a košem?", "Hokej", "Basketbal", "Rugby", "Baseball", "B"),

        # Sport / Medium (5)
        ("Sport", "Medium", "Kolik setů se obvykle hraje ve volejbale na vítězné 3 sety?", "Do 2 setů", "Do 3 setů", "Do 5 setů", "Do 7 setů", "C"),
        ("Sport", "Medium", "Jak se jmenuje nejvyšší fotbalová soutěž v Anglii?", "La Liga", "Serie A", "Premier League", "Bundesliga", "C"),
        ("Sport", "Medium", "Co znamená zkratka VAR ve fotbale?", "Video Assistant Referee", "Virtual Arena Replay", "Verified Action Rule", "Video Attack Review", "A"),
        ("Sport", "Medium", "Kolik minut trvá standardní zápas NBA?", "40", "48", "60", "90", "B"),
        ("Sport", "Medium", "Jaký povrch má grandslam Roland Garros?", "Travnatý", "Tvrdý", "Antuka", "Koberec", "C"),

        # Sport / Hard (7)
        ("Sport", "Hard", "Kolik bodů má touchdown v americkém fotbale (bez extra point)?", "3", "6", "7", "10", "B"),
        ("Sport", "Hard", "Jaká je oficiální výška basketbalového koše?", "2,05 m", "2,45 m", "3,05 m", "3,50 m", "C"),
        ("Sport", "Hard", "Kolik hráčů je na ledě za tým v hokeji během hry?", "4", "5", "6", "7", "C"),
        ("Sport", "Hard", "Jak dlouhá je maratonská trať?", "40 km", "41 km", "42 km", "42,195 km", "D"),
        ("Sport", "Hard", "Kolik drah má olympijský plavecký bazén?", "6", "10", "8", "12", "B"),
        ("Sport", "Hard", "Kolik hráčů má baseballový tým v poli při obraně?", "9", "7", "10", "11", "A"),
        ("Sport", "Hard", "Který grandslam se hraje na trávě?", "US Open", "Australian Open", "Roland Garros", "Wimbledon", "D"),

        # Historie / Easy (3)
        ("Historie", "Easy", "V jakém roce začala 2. světová válka?", "1914", "1939", "1945", "1929", "B"),
        ("Historie", "Easy", "Kdo byl první prezident České republiky?", "Václav Havel", "Tomáš G. Masaryk", "Edvard Beneš", "Miloš Zeman", "A"),
        ("Historie", "Easy", "Která civilizace postavila pyramidy v Gíze?", "Římané", "Egypťané", "Vikingové", "Mayové", "B"),

        # Historie / Medium (5)
        ("Historie", "Medium", "Kdy byla podepsána Magna Charta?", "1215", "1492", "1776", "1918", "A"),
        ("Historie", "Medium", "Kdo objevil Ameriku (v roce 1492)?", "James Cook", "Kryštof Kolumbus", "Marco Polo", "Ferdinand Magellan", "B"),
        ("Historie", "Medium", "V jakém roce vzniklo Československo?", "1918", "1938", "1948", "1989", "A"),
        ("Historie", "Medium", "V kterém roce padla Berlínská zeď?", "1968", "1979", "1989", "1999", "C"),
        ("Historie", "Medium", "Která bitva v roce 1815 definitivně porazila Napoleona?", "Austerlitz", "Lipsko", "Trafalgar", "Waterloo", "D"),

        # Historie / Hard (7)
        ("Historie", "Hard", "Co byla studená válka?", "Válka v Arktidě", "Konflikt bez přímé bitvy velmocí, hlavně politický", "Občanská válka v USA", "Válka v Antarktidě", "B"),
        ("Historie", "Hard", "Který panovník zavedl patent o zrušení nevolnictví v habsburské monarchii?", "Marie Terezie", "Josef II.", "Karel IV.", "Ferdinand I.", "B"),
        ("Historie", "Hard", "Co znamená pojem renesance?", "Obnova a znovuzrození umění a vědy", "Vynález elektřiny", "Vznik internetu", "Období pravěku", "A"),
        ("Historie", "Hard", "Kdo sepsal 95 tezí, které odstartovaly reformaci?", "Jan Hus", "Jan Kalvín", "Martin Luther", "Erasmus Rotterdamský", "C"),
        ("Historie", "Hard", "Ve kterém roce začala Velká francouzská revoluce?", "1776", "1789", "1812", "1848", "B"),
        ("Historie", "Hard", "Který český král je znám jako Otec vlasti?", "Přemysl Otakar II.", "Václav II.", "Jiří z Poděbrad", "Karel IV.", "D"),
        ("Historie", "Hard", "Jak se jmenovala smlouva, která ukončila první světovou válku s Německem?", "Mnichovská", "Trianonská", "Versailleská", "Brestlitevský mír", "C"),
    ]


def main():
    mydb = mysql.connector.connect(
        host=Config.DB_HOST,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME,
        port=getattr(Config, "DB_PORT", 3306),
    )

    mycursor = mydb.cursor()

    mycursor.execute("SET NAMES utf8mb4;")
    mycursor.execute("SET FOREIGN_KEY_CHECKS=0;")
    mydb.commit()

    # DROP tabulek
    mycursor.execute("DROP TABLE IF EXISTS results;")
    mycursor.execute("DROP TABLE IF EXISTS questions_categories;")
    mycursor.execute("DROP TABLE IF EXISTS questions;")
    mycursor.execute("DROP TABLE IF EXISTS categories;")
    mycursor.execute("DROP TABLE IF EXISTS difficulties;")
    mycursor.execute("DROP TABLE IF EXISTS users;")
    mydb.commit()

    mycursor.execute("SET FOREIGN_KEY_CHECKS=1;")
    mydb.commit()

    # CREATE tabulek
    mycursor.execute(
        """CREATE TABLE users(
        user_id int PRIMARY KEY AUTO_INCREMENT,
        username varchar(50) NOT NULL UNIQUE,
        password_hash varchar(255) NOT NULL,
        role char(5) NOT NULL DEFAULT 'user',
        profile_title varchar(50) NULL,
        created_at datetime NOT NULL DEFAULT CURRENT_TIMESTAMP
    );"""
    )
    mydb.commit()

    mycursor.execute(
        """CREATE TABLE categories(
        category_id int PRIMARY KEY AUTO_INCREMENT,
        name varchar(50) NOT NULL UNIQUE,
        description varchar(255)
    );"""
    )
    mydb.commit()

    mycursor.execute(
        """CREATE TABLE difficulties(
        difficulty_id int PRIMARY KEY AUTO_INCREMENT,
        name char(10) NOT NULL UNIQUE,
        points_multiplier decimal(3,2) NOT NULL DEFAULT 1.00
    );"""
    )
    mydb.commit()

    mycursor.execute(
        """CREATE TABLE questions(
        question_id int PRIMARY KEY AUTO_INCREMENT,
        question_text varchar(500) NOT NULL,
        answer_a varchar(255) NOT NULL,
        answer_b varchar(255) NOT NULL,
        answer_c varchar(255) NOT NULL,
        answer_d varchar(255) NOT NULL,
        correct_answer char(1) NOT NULL,
        difficulty_id int NOT NULL,
        created_by int,
        created_at datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (difficulty_id) REFERENCES difficulties(difficulty_id),
        FOREIGN KEY (created_by) REFERENCES users(user_id) ON DELETE SET NULL
    );"""
    )
    mydb.commit()

    mycursor.execute(
        """CREATE TABLE questions_categories(
        question_id int NOT NULL,
        category_id int NOT NULL,
        PRIMARY KEY (question_id, category_id),
        FOREIGN KEY (question_id) REFERENCES questions(question_id) ON DELETE CASCADE,
        FOREIGN KEY (category_id) REFERENCES categories(category_id) ON DELETE CASCADE
    );"""
    )
    mydb.commit()

    mycursor.execute(
        """CREATE TABLE results(
        result_id int PRIMARY KEY AUTO_INCREMENT,
        user_id int NOT NULL,
        category_id int NOT NULL,
        difficulty_id int NOT NULL,
        score int NOT NULL,
        total_questions int NOT NULL,
        duration_seconds int NULL,
        played_at datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
        FOREIGN KEY (category_id) REFERENCES categories(category_id),
        FOREIGN KEY (difficulty_id) REFERENCES difficulties(difficulty_id)
    );"""
    )
    mydb.commit()

    # INSERT: admin
    admin_hash = _hash_password(Config.ADMIN_DEFAULT_PASSWORD)
    mycursor.execute(
        "INSERT INTO users(username, password_hash, role) VALUES (%s, %s, 'admin');",
        (Config.ADMIN_DEFAULT_USERNAME, admin_hash),
    )
    admin_user_id = mycursor.lastrowid
    mydb.commit()

    # Kategorie
    mycursor.execute(
        """INSERT INTO categories(name, description)
        VALUES
        ('IT','Zaklady IT'),
        ('Sport','Sportovni otazky'),
        ('Historie','Historie');
    """
    )
    mydb.commit()

    # Obtiznosti
    mycursor.execute(
        """INSERT INTO difficulties(name, points_multiplier)
        VALUES
        ('Easy',1.00),
        ('Medium',1.25),
        ('Hard',1.50);
    """
    )
    mydb.commit()

    # Mapy ID pro seed otazek
    mycursor.execute("SELECT category_id, name FROM categories;")
    category_map = {name: category_id for category_id, name in mycursor.fetchall()}

    mycursor.execute("SELECT difficulty_id, name FROM difficulties;")
    difficulty_map = {name: difficulty_id for difficulty_id, name in mycursor.fetchall()}

    # Vlozeni otazek + vazeb na kategorie
    question_rows = _question_seed_data()
    for category_name, difficulty_name, q_text, a, b, c, d, correct in question_rows:
        mycursor.execute(
            """
            INSERT INTO questions (
                question_text, answer_a, answer_b, answer_c, answer_d,
                correct_answer, difficulty_id, created_by
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
            """,
            (
                q_text,
                a,
                b,
                c,
                d,
                correct,
                difficulty_map[difficulty_name],
                admin_user_id,
            ),
        )
        question_id = mycursor.lastrowid

        mycursor.execute(
            "INSERT INTO questions_categories(question_id, category_id) VALUES (%s, %s);",
            (question_id, category_map[category_name]),
        )

    mydb.commit()

    mycursor.close()
    mydb.close()

    print("Hotovo: 3 temata, Easy=3, Medium=5, Hard=7 na kazde tema (celkem 45 otazek).")


if __name__ == "__main__":
    main()
