import hashlib
import secrets

# Externí balíček pro připojení k MySQL databázi (instalace přes pip).
import mysql.connector

# Import konfigurace projektu ze souboru `config.py`
from config import Config


def _hash_password(password: str) -> str:
    # Tato pomocná funkce vezme čisté heslo a vrátí bezpečnější uloženou podobu.
    # Výsledek bude ve formátu `salt$hash`, stejně jako očekává login logika v aplikaci.
    # `salt` = náhodný text přidaný k heslu, aby stejné heslo nemělo vždy stejný hash.
    salt = secrets.token_hex(16)
    # SHA-256 spočítá jednosměrný otisk (hash) z `salt + heslo`.
    # Jednosměrný znamená: z hashe nejde snadno dostat původní heslo.
    digest = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    # Uložíme oba kusy dohromady, oddělené znakem `$`.
    return f"{salt}${digest}"


def _question_seed_data():
    # Tato funkce vrací připravený seznam otázek, který se vloží do DB při inicializaci.
    # Každá položka je n-tice v pořadí:
    # (název_kategorie, název_obtížnosti, text_otázky, odpověď_A, odpověď_B, odpověď_C, odpověď_D, správná_odpověď).
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

        # Příroda / Easy (3)
        ("Příroda", "Easy", "Jaké zvíře je známé jako „král zvířat“?", "Tygr", "Lev", "Slon", "Medvěd", "B"),
        ("Příroda", "Easy", "Jakou barvu má chlorofyl?", "Červenou", "Modrou", "Zelenou", "Žlutou", "C"),
        ("Příroda", "Easy", "Co dýchají lidé k přežití?", "Dusík", "Vodík", "Oxid uhličitý", "Kyslík", "D"),

        # Příroda / Medium (5)
        ("Příroda", "Medium", "Který orgán je hlavním místem fotosyntézy u rostlin?", "List", "Kořen", "Stonek", "Květ", "A"),
        ("Příroda", "Medium", "Kolik kostí má dospělý člověk přibližně?", "106", "306", "206", "406", "C"),
        ("Příroda", "Medium", "Jaké je největší suchozemské zvíře?", "Nosorožec", "Hroch", "Žirafa", "Slon africký", "D"),
        ("Příroda", "Medium", "Která planeta je nejblíže Slunci?", "Venuše", "Merkur", "Země", "Mars", "B"),
        ("Příroda", "Medium", "Co způsobuje střídání ročních období na Zemi?", "Vzdálenost od Slunce", "Rotace Země", "Naklonění zemské osy", "Gravitace Měsíce", "C"),

        # Příroda / Hard (7)
        ("Příroda", "Hard", "Který proces umožňuje rostlinám přeměnit světelnou energii na chemickou?", "Dýchání", "Fotosyntéza", "Fermentace", "Transpirace", "B"),
        ("Příroda", "Hard", "Jaký je nejhlubší známý oceánský příkop na Zemi?", "Tonga příkop", "Kermadecký příkop", "Jávský příkop", "Mariánský příkop", "D"),
        ("Příroda", "Hard", "Který plyn tvoří největší část zemské atmosféry?", "Kyslík", "Oxid uhličitý", "Dusík", "Argon", "C"),
        ("Příroda", "Hard", "Jak se nazývá proces, při kterém se pevná látka mění přímo na plyn?", "Kondenzace", "Sublimace", "Depozice", "Evaporace", "B"),
        ("Příroda", "Hard", "Který biom je charakteristický permafrostem?", "Savana", "Tundra", "Tropický prales", "Step", "B"),
        ("Příroda", "Hard", "Jaký typ horniny vzniká ochlazením magmatu?", "Vyvřelá", "Sedimentární", "Metamorfovaná", "Organická", "A"),
        ("Příroda", "Hard", "Který z těchto živočichů má otevřenou oběhovou soustavu?", "Rak", "Žížala", "Chobotnice", "Pták", "A"),
    ]


def main():
    # Hlavní funkce pro jednorázovou přípravu databáze.
    # Pozor: tento skript maže existující tabulky a vytvoří je znovu od nuly.

    # Připojení k MySQL podle hodnot z `Config`.
    mydb = mysql.connector.connect(
        # Adresa databázového serveru (typicky `localhost` v lokálním vývoji).
        host=Config.DB_HOST,
        # Uživatelské jméno do databáze.
        user=Config.DB_USER,
        # Heslo do databáze.
        password=Config.DB_PASSWORD,
        # Název databáze, ve které budeme vytvářet tabulky.
        database=Config.DB_NAME,
        # Port: když v configu chybí, použije se výchozí 3306.
        port=getattr(Config, "DB_PORT", 3306),
    )

    # `cursor` je objekt, přes který posíláme SQL příkazy do databáze.
    mycursor = mydb.cursor()

    # Zajistíme UTF-8 (utf8mb4), aby se správně ukládala čeština i speciální znaky.
    mycursor.execute("SET NAMES utf8mb4;")
    # Dočasně vypneme kontrolu cizích klíčů, aby šlo bezpečně mazat tabulky v libovolném pořadí.
    mycursor.execute("SET FOREIGN_KEY_CHECKS=0;")
    # Potvrdíme změny nastavení session.
    mydb.commit()

    # DROP tabulek:
    # `IF EXISTS` znamená, že SQL nespadne chybou, když tabulka zatím neexistuje.
    # Mažeme od tabulek s vazbami, ale s vypnutými FK kontrolami by fungovalo i jinak.
    mycursor.execute("DROP TABLE IF EXISTS question_reports;")
    mycursor.execute("DROP TABLE IF EXISTS question_attempts;")
    mycursor.execute("DROP TABLE IF EXISTS results;")
    mycursor.execute("DROP TABLE IF EXISTS questions_categories;")
    mycursor.execute("DROP TABLE IF EXISTS questions;")
    mycursor.execute("DROP TABLE IF EXISTS categories;")
    mycursor.execute("DROP TABLE IF EXISTS difficulties;")
    mycursor.execute("DROP TABLE IF EXISTS users;")
    # Potvrdíme mazání.
    mydb.commit()

    # Po mazání vrátíme kontrolu cizích klíčů zpět na zapnuto.
    mycursor.execute("SET FOREIGN_KEY_CHECKS=1;")
    mydb.commit()

    # CREATE tabulek:
    # Následuje vytvoření všech potřebných tabulek aplikace.
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
    # `commit()` ukládá právě provedený CREATE natrvalo.
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
    # Tato tabulka je "spojovací" (vazba otázka <-> kategorie).
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
    # `duration_seconds` je volitelný sloupec (NULL), když čas není k dispozici.
    mydb.commit()

    mycursor.execute(
        """CREATE TABLE question_attempts(
        attempt_id int PRIMARY KEY AUTO_INCREMENT,
        user_id int NOT NULL,
        question_id int NOT NULL,
        category_id int NOT NULL,
        difficulty_id int NOT NULL,
        is_correct tinyint(1) NOT NULL,
        mode varchar(20) NOT NULL DEFAULT 'normal',
        answered_at datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_attempts_user_question (user_id, question_id),
        INDEX idx_attempts_user_time (user_id, answered_at),
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
        FOREIGN KEY (question_id) REFERENCES questions(question_id) ON DELETE CASCADE,
        FOREIGN KEY (category_id) REFERENCES categories(category_id),
        FOREIGN KEY (difficulty_id) REFERENCES difficulties(difficulty_id)
    );"""
    )
    # INDEXy v této tabulce zrychlují časté filtrování podle uživatele a času.
    mydb.commit()

    mycursor.execute(
        """CREATE TABLE question_reports(
        report_id int PRIMARY KEY AUTO_INCREMENT,
        question_id int NOT NULL,
        user_id int NOT NULL,
        reason varchar(60) NOT NULL,
        note varchar(500),
        status varchar(20) NOT NULL DEFAULT 'new',
        created_at datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        resolved_by int NULL,
        INDEX idx_reports_status (status),
        INDEX idx_reports_question (question_id),
        INDEX idx_reports_user_time (user_id, created_at),
        FOREIGN KEY (question_id) REFERENCES questions(question_id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
        FOREIGN KEY (resolved_by) REFERENCES users(user_id) ON DELETE SET NULL
    );"""
    )
    # `updated_at ... ON UPDATE CURRENT_TIMESTAMP` se aktualizuje automaticky při změně řádku.
    mydb.commit()

    # INSERT: admin účet
    # Vytvoříme hash hesla místo ukládání čistého hesla.
    admin_hash = _hash_password(Config.ADMIN_DEFAULT_PASSWORD)
    mycursor.execute(
        # `%s` placeholdery = bezpečné předání parametrů bez ručního skládání SQL textu.
        "INSERT INTO users(username, password_hash, role) VALUES (%s, %s, 'admin');",
        (Config.ADMIN_DEFAULT_USERNAME, admin_hash),
    )
    # `lastrowid` je ID právě vloženého admin uživatele.
    admin_user_id = mycursor.lastrowid
    mydb.commit()

    # Kategorie:
    # Vložíme 4 základní témata.
    mycursor.execute(
        """INSERT INTO categories(name, description)
        VALUES
        ('IT','Různé otázky ze světa technologií.'),
        ('Sport','Otázky ze světa sportu.'),
        ('Historie','Otázky z minulosti i významných událostí.'),
        ('Příroda','Znalosti o přírodě, zvířatech, rostlinách a Zemi.');
    """
    )
    mydb.commit()

    # Obtížnosti:
    # Každá obtížnost má také násobič bodů (`points_multiplier`).
    mycursor.execute(
        """INSERT INTO difficulties(name, points_multiplier)
        VALUES
        ('Easy',1.00),
        ('Medium',1.25),
        ('Hard',1.50);
    """
    )
    mydb.commit()

    # Mapy ID pro seed otázek:
    # Načteme ID z DB a uděláme slovníky typu "název -> ID",
    # aby šly otázky z textových názvů převést na cizí klíče.
    mycursor.execute("SELECT category_id, name FROM categories;")
    category_map = {name: category_id for category_id, name in mycursor.fetchall()}

    mycursor.execute("SELECT difficulty_id, name FROM difficulties;")
    difficulty_map = {name: difficulty_id for difficulty_id, name in mycursor.fetchall()}

    # Vložení otázek + vazeb na kategorie.
    question_rows = _question_seed_data()
    # Procházíme otázky jednu po druhé.
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
        # Uložíme si ID nově vložené otázky.
        question_id = mycursor.lastrowid

        # Do spojovací tabulky uložíme vazbu otázky na konkrétní kategorii.
        mycursor.execute(
            "INSERT INTO questions_categories(question_id, category_id) VALUES (%s, %s);",
            (question_id, category_map[category_name]),
        )

    # Potvrdíme všechny vložené otázky a vazby naráz.
    mydb.commit()

    # Korektně zavřeme kurzor i DB spojení.
    mycursor.close()
    mydb.close()

    # Informační výstup do terminálu.
    print("Hotovo: 4 témata, Easy=3, Medium=5, Hard=7 na každé téma (celkem 60 otázek).")


if __name__ == "__main__":
    # Tento blok se spustí jen při přímém spuštění souboru:
    # `python db_setup.py`
    main()
