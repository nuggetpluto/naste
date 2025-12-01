import psycopg2
import psycopg2.extras

# ================================
# НАСТРОЙКИ ПОДКЛЮЧЕНИЯ К POSTGRES
# ================================

DB_SETTINGS = {
    "host": "localhost",        # или IP, если внешний сервер
    "port": 5432,
    "dbname": "Зоопарк",            # имя твоей БД в PostgreSQL
    "user": "postgres",
    "password": "killeu1501"        # твой пароль
}

# ================================
# ФУНКЦИЯ ПОЛУЧЕНИЯ СОЕДИНЕНИЯ
# ================================

def get_connection():
    conn = psycopg2.connect(
        host=DB_SETTINGS["host"],
        port=DB_SETTINGS["port"],
        dbname=DB_SETTINGS["dbname"],
        user=DB_SETTINGS["user"],
        password=DB_SETTINGS["password"]
    )
    return conn