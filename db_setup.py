import mysql.connector

def main():
    mydb = mysql.connector.connect(
        host="dbs.spskladno.cz",
        user="student28",
        password="spsnet",
        database="vyuka28"
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
    mycursor.execute("""CREATE TABLE users(
        user_id int PRIMARY KEY AUTO_INCREMENT,
        username varchar(50) NOT NULL UNIQUE,
        password_hash varchar(255) NOT NULL,
        role char(5) NOT NULL DEFAULT 'user',
        created_at datetime NOT NULL DEFAULT CURRENT_TIMESTAMP
    );""")
    mydb.commit()

    mycursor.execute("""CREATE TABLE categories(
        category_id int PRIMARY KEY AUTO_INCREMENT,
        name varchar(50) NOT NULL UNIQUE,
        description varchar(255)
    );""")
    mydb.commit()

    mycursor.execute("""CREATE TABLE difficulties(
        difficulty_id int PRIMARY KEY AUTO_INCREMENT,
        name char(10) NOT NULL UNIQUE,
        points_multiplier decimal(3,2) NOT NULL DEFAULT 1.00
    );""")
    mydb.commit()

    mycursor.execute("""CREATE TABLE questions(
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
    );""")
    mydb.commit()

    mycursor.execute("""CREATE TABLE questions_categories(
        question_id int NOT NULL,
        category_id int NOT NULL,
        PRIMARY KEY (question_id, category_id),
        FOREIGN KEY (question_id) REFERENCES questions(question_id) ON DELETE CASCADE,
        FOREIGN KEY (category_id) REFERENCES categories(category_id) ON DELETE CASCADE
    );""")
    mydb.commit()

    mycursor.execute("""CREATE TABLE results(
        result_id int PRIMARY KEY AUTO_INCREMENT,
        user_id int NOT NULL,
        category_id int NOT NULL,
        difficulty_id int NOT NULL,
        score int NOT NULL,
        total_questions int NOT NULL,
        played_at datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
        FOREIGN KEY (category_id) REFERENCES categories(category_id),
        FOREIGN KEY (difficulty_id) REFERENCES difficulties(difficulty_id)
    );""")
    mydb.commit()

    # INSERT: pouze admin (žádný testuser)
    mycursor.execute("""INSERT INTO users(username, password_hash, role)
        VALUES ('admin','HASH','admin');""")
    mydb.commit()

    # Kategorie (počítáme s ID: IT=1, Sport=2, Historie=3)
    mycursor.execute("""INSERT INTO categories(name, description)
        VALUES
        ('IT','Základy IT'),
        ('Sport','Sportovní otázky'),
        ('Historie','Historie');
    """)
    mydb.commit()

    # Obtížnosti (počítáme s ID: Easy=1, Medium=2, Hard=3)
    mycursor.execute("""INSERT INTO difficulties(name, points_multiplier)
        VALUES
        ('Easy',1.00),
        ('Medium',1.25),
        ('Hard',1.50);
    """)
    mydb.commit()

    # 27 otázek: 3 témata × 3 obtížnosti × 3 otázky
    # (created_by=1 = admin)
    mycursor.execute("""INSERT INTO questions
        (question_text, answer_a, answer_b, answer_c, answer_d, correct_answer, difficulty_id, created_by)
        VALUES
        -- IT / Easy (IDs 1-3)
        ('Co znamená zkratka CPU?','Central Processing Unit','Computer Power Unit','Core Process Utility','Central Program Usage','A',1,1),
        ('Který z těchto je operační systém?','Chrome','Windows','Python','HTML','B',1,1),
        ('Co je RAM?','Pevný disk','Operační systém','Paměť pro běh programů','Grafická karta','C',1,1),

        -- IT / Medium (IDs 4-6)
        ('Co znamená zkratka URL?','Uniform Resource Locator','Universal Render Language','User Route Link','Unified Resource Log','A',2,1),
        ('K čemu slouží SQL?','Úprava obrázků','Dotazování databází','Tvorba 3D modelů','Komprese videa','B',2,1),
        ('Co dělá protokol HTTPS oproti HTTP?','Zrychlí internet','Šifruje komunikaci','Zakáže cookies','Změní IP adresu','B',2,1),

        -- IT / Hard (IDs 7-9)
        ('Co je normalizace databáze (obecně)?','Zvětšení tabulek','Snížení redundance a zlepšení struktury','Šifrování dat','Zálohování databáze','B',3,1),
        ('K čemu slouží JOIN v SQL?','Smazání tabulky','Spojení řádků z více tabulek','Vytvoření indexu','Změna datového typu','B',3,1),
        ('Co je primární klíč (PK)?','Sloupec s duplikáty','Jedinečný identifikátor řádku','Cizí klíč','Náhodné číslo bez pravidel','B',3,1),

        -- Sport / Easy (IDs 10-12)
        ('Kolik hráčů je na hřišti za jeden fotbalový tým?','9','10','11','12','C',1,1),
        ('Jak se jmenuje tenisové skóre 0?','Zero','Love','Nil','None','B',1,1),
        ('Jaký sport se hraje s oranžovým míčem a košem?','Hokej','Basketbal','Rugby','Baseball','B',1,1),

        -- Sport / Medium (IDs 13-15)
        ('Kolik setů se obvykle hraje ve volejbale na vítězné 3 sety?','Do 2 setů','Do 3 setů','Do 5 setů','Do 7 setů','C',2,1),
        ('Jak se jmenuje nejvyšší fotbalová soutěž v Anglii?','La Liga','Serie A','Premier League','Bundesliga','C',2,1),
        ('Co znamená zkratka VAR ve fotbale?','Video Assistant Referee','Virtual Arena Replay','Verified Action Rule','Video Attack Review','A',2,1),

        -- Sport / Hard (IDs 16-18)
        ('Kolik bodů má touchdown v americkém fotbale (bez extra point)?','3','6','7','10','B',3,1),
        ('Jaký je oficiální rozměr basketbalového koše (výška)?','2,05 m','2,45 m','3,05 m','3,50 m','C',3,1),
        ('Kolik hráčů je na ledě za tým v hokeji během hry?','4','5','6','7','C',3,1),

        -- Historie / Easy (IDs 19-21)
        ('V jakém roce začala 2. světová válka?','1914','1939','1945','1929','B',1,1),
        ('Kdo byl první prezident České republiky?','Václav Havel','Tomáš G. Masaryk','Edvard Beneš','Miloš Zeman','A',1,1),
        ('Která civilizace postavila pyramidy v Gíze?','Římané','Egypťané','Vikingové','Mayové','B',1,1),

        -- Historie / Medium (IDs 22-24)
        ('Kdy byla podepsána Magna Charta?','1215','1492','1776','1918','A',2,1),
        ('Kdo objevil Ameriku (v roce 1492)?','James Cook','Kryštof Kolumbus','Marco Polo','Ferdinand Magellan','B',2,1),
        ('V jakém roce vzniklo Československo?','1918','1938','1948','1989','A',2,1),

        -- Historie / Hard (IDs 25-27)
        ('Co byla studená válka?','Válka v Arktidě','Konflikt bez přímé bitvy velmocí, hlavně politický','Občanská válka v USA','Válka v Antarktidě','B',3,1),
        ('Který panovník zavedl v habsburské monarchii reformy a patent o zrušení nevolnictví?','Marie Terezie','Josef II.','Karel IV.','Ferdinand I.','B',3,1),
        ('Co znamená pojem „renesance“?','Obnova/ znovuzrození umění a vědy','Vynález elektřiny','Vznik internetu','Období pravěku','A',3,1);
    """)
    mydb.commit()

    # Napojení otázek na kategorie (M:N tabulka)
    # IT = category_id 1, Sport = 2, Historie = 3
    mycursor.execute("""INSERT INTO questions_categories(question_id, category_id)
        VALUES
        -- IT (1-9)
        (1,1),(2,1),(3,1),(4,1),(5,1),(6,1),(7,1),(8,1),(9,1),
        -- Sport (10-18)
        (10,2),(11,2),(12,2),(13,2),(14,2),(15,2),(16,2),(17,2),(18,2),
        -- Historie (19-27)
        (19,3),(20,3),(21,3),(22,3),(23,3),(24,3),(25,3),(26,3),(27,3);
    """)
    mydb.commit()


    mycursor.close()
    mydb.close()
    print("Hotovo: 3 obtížnosti, 3 témata, 27 otázek (3 na téma na obtížnost).")


if __name__ == "__main__":
    main()
