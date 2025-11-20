from fastapi import Request
from fastapi.responses import RedirectResponse, HTMLResponse
from functools import wraps
from session import session_data
from db import get_connection


def role_required(allowed_roles: list):
    """
    Проверка роли:
    - пользователь авторизован
    - его роль входит в список allowed_roles
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):

            # ===== ИЗВЛЕКАЕМ REQUEST =====
            request: Request = kwargs.get("request")
            if not request:
                # fallback — если request передали как позиционный аргумент
                if len(args) > 0:
                    request = args[0]
                else:
                    return HTMLResponse("Ошибка: request не найден", status_code=500)

            # ===== ПРОВЕРКА АВТОРИЗАЦИИ =====
            user_id = session_data.get("current_user_id")
            if not user_id:
                return RedirectResponse("/login", status_code=303)

            # ===== ЗАГРУЗКА ПОЛЬЗОВАТЕЛЯ =====
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, role FROM employees WHERE id=?", (user_id,))
            user = cursor.fetchone()
            conn.close()

            if not user:
                return RedirectResponse("/login", status_code=303)

            # ===== ПРОВЕРКА ДОСТУПА =====
            if user["role"] not in allowed_roles:
                return HTMLResponse(
                    "<h2 style='color:red'>Ошибка 403: доступ запрещён</h2>",
                    status_code=403
                )

            # ===== ДОПУСК =====
            return await func(*args, **kwargs)

        return wrapper

    return decorator