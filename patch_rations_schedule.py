import sqlite3

DB_NAME = "zoo.db"

def column_exists(cursor, table, column):
    """Проверяет, есть ли колонка в таблице"""
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns

def patch_rations_schedule():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Проверяем колонку
    if column_exists(cursor, "rations", "schedule"):
        print("✔ Колонка 'schedule' уже существует — ничего делать не нужно.")
    else:
        print("➕ Добавляем колонку 'schedule'...")
        cursor.execute("""
            ALTER TABLE rations
            ADD COLUMN schedule TEXT DEFAULT '2 раза в день';
        """)
        print("✔ Колонка 'schedule' успешно добавлена!")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    print("=== Patch rations.schedule ===")
    patch_rations_schedule()
    print("=== Done ===")