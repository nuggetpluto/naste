import sqlite3

DB_NAME = "zoo.db"

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row  # возвращает строки в виде словарей
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS employees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        phone TEXT,
        role TEXT DEFAULT 'zootechnician',
        status TEXT DEFAULT 'active'
    );
    """)

    cursor.execute("""
    INSERT OR IGNORE INTO employees (username, password, full_name, role)
    VALUES ('admin', '123', 'Администратор', 'admin');
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS animals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        species TEXT NOT NULL,
        gender TEXT CHECK(gender IN ('Самец', 'Самка')) DEFAULT 'Самец',
        health_status TEXT CHECK(health_status IN ('Здоров', 'Болен', 'На лечении')) DEFAULT 'Здоров',
        birth_date TEXT,
        employee_id INTEGER,
        status TEXT DEFAULT 'Активен',
        FOREIGN KEY (employee_id) REFERENCES employees(id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS feed (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        type TEXT CHECK(type IN ('Влажный', 'Сухой', 'Комбикорм')) DEFAULT 'Сухой',
        unit TEXT DEFAULT 'кг',
        quantity REAL DEFAULT 0
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS feedings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        animal_id INTEGER NOT NULL,
        feed_id INTEGER NOT NULL,
        employee_id INTEGER NOT NULL,
        amount REAL NOT NULL CHECK(amount >= 0),
        feeding_time TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (animal_id) REFERENCES animals(id),
        FOREIGN KEY (feed_id) REFERENCES feed(id),
        FOREIGN KEY (employee_id) REFERENCES employees(id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        feed_id INTEGER NOT NULL,
        employee_id INTEGER NOT NULL,
        quantity REAL NOT NULL CHECK(quantity >= 0),
        expense_date TEXT DEFAULT CURRENT_DATE,
        FOREIGN KEY (feed_id) REFERENCES feed(id),
        FOREIGN KEY (employee_id) REFERENCES employees(id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER NOT NULL,
        status TEXT CHECK(status IN ('Заявка принята','Ожидание','В процессе','Доставлено')) DEFAULT 'Заявка принята',
        request_date TEXT DEFAULT CURRENT_DATE,
        FOREIGN KEY (employee_id) REFERENCES employees(id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS purchase_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        purchase_id INTEGER NOT NULL,
        feed_id INTEGER NOT NULL,
        quantity REAL NOT NULL CHECK(quantity >= 0),
        FOREIGN KEY (purchase_id) REFERENCES purchases(id),
        FOREIGN KEY (feed_id) REFERENCES feed(id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS malfunctions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        description TEXT NOT NULL,
        place TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Зафиксировано',
        resolved_at TEXT
    )
    """)

    conn.commit()
    conn.close()