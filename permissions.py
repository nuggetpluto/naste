from fastapi import Request
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from functools import wraps

import psycopg2.extras

from session import session_data
from db import get_connection


def role_required(allowed_roles: list, ajax: bool = False):
    """
    Проверка прав доступа.
    - Если ajax=True → вместо HTML возвращает JSON-ошибки
    """

    def decorator(func):

        @wraps(func)
        async def wrapper(*args, **kwargs):

            # ---- получить request ----
            request: Request = kwargs.get("request")
            if not request and len(args) > 0:
                # request всегда первый аргумент
                request = args[0]

            if not request:
                if ajax:
                    return JSONResponse(
                        status_code=500,
                        content={"success": False, "error": "Request not found"}
                    )
                return HTMLResponse("Ошибка: request не найден", status_code=500)

            # ---- проверка авторизации ----
            user_id = session_data.get("current_user_id")
            if not user_id:
                if ajax:
                    return JSONResponse(
                        status_code=401,
                        content={"success": False, "error": "Not authenticated"}
                    )
                return RedirectResponse("/login", status_code=303)

            # ---- получить роль ----
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
                if ajax:
                    return JSONResponse(
                        status_code=401,
                        content={"success": False, "error": "User not found"}
                    )
                return RedirectResponse("/login", status_code=303)

            # ---- проверка доступа ----
            if user["role"] not in allowed_roles:
                if ajax:
                    return JSONResponse(
                        status_code=403,
                        content={"success": False, "error": "Access denied"}
                    )
                return HTMLResponse(
                    "<h2 style='color:red'>Ошибка 403: доступ запрещён</h2>",
                    status_code=403,
                )

            # ---- доступ разрешён ----
            return await func(*args, **kwargs)

        return wrapper

    return decorator