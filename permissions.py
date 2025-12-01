from fastapi import Request
from fastapi.responses import RedirectResponse, HTMLResponse
from functools import wraps

import psycopg2.extras

from session import session_data
from db import get_connection


def role_required(allowed_roles: list):
    """
    Проверка прав доступа:
    - пользователь авторизован
    - его роль (admin/director/manager/zootechnician)
      входит в allowed_roles
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):

            # ===== достаём request =====
            request: Request = kwargs.get("request")
            if not request and len(args) > 0:
                request = args[0]

            if not request:
                return HTMLResponse("Ошибка: request не найден", status_code=500)

            # ===== проверка авторизации =====
            user_id = session_data.get("current_user_id")
            if not user_id:
                return RedirectResponse("/login", status_code=303)

            # ===== получаем роль из БД =====
            conn = get_connection()
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            cursor.execute("""
                SELECT
                    "IDСотрудника" AS id,
                    CASE
                        WHEN "Должность" = 'Администратор' THEN 'admin'
                        WHEN "Должность" = 'Руководитель'  THEN 'director'
                        WHEN "Должность" = 'Менеджер'      THEN 'manager'
                        WHEN "Должность" = 'Зоотехник'     THEN 'zootechnician'
                        ELSE 'zootechnician'
                    END AS role
                FROM "Сотрудник"
                WHERE "IDСотрудника" = %s
            """, (user_id,))
            user = cursor.fetchone()
            conn.close()

            if not user:
                return RedirectResponse("/login", status_code=303)

            if user["role"] not in allowed_roles:
                return HTMLResponse(
                    "<h2 style='color:red'>Ошибка 403: доступ запрещён</h2>",
                    status_code=403,
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator