from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.templating import _TemplateResponse
from datetime import datetime
import psycopg2.extras

from db import get_connection
from session import session_data


# ========= MIDDLEWARE: подгружаем текущего пользователя =========

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        user = None

        user_id = session_data.get("current_user_id")
        if user_id:
            conn = get_connection()
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            cursor.execute("""
                SELECT
                    "IDСотрудника" AS id,
                    "ФИО"          AS full_name,
                    "Должность"    AS position,
                    "КонтактныеДанные" AS phone,
                    "Пароль"       AS password,
                    "Статус"       AS status,
                    CASE
                        WHEN "Должность" = 'Администратор' THEN 'admin'
                        WHEN "Должность" = 'Руководитель'  THEN 'director'
                        WHEN "Должность" = 'Менеджер'      THEN 'manager'
                        WHEN "Должность" = 'Зоотехник'     THEN 'zootechnician'
                        ELSE 'zootechnician'
                    END            AS role
                FROM "Сотрудник"
                WHERE "IDСотрудника" = %s
            """, (user_id,))
            user = cursor.fetchone()
            conn.close()

        request.state.user = user
        response = await call_next(request)
        return response


# ========= FASTAPI app =========

app = FastAPI(middleware=[Middleware(AuthMiddleware)])

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")
templates.env.globals['now'] = datetime.now

# --- Патч TemplateResponse: автоматически пробрасываем user во все шаблоны ---

orig_init = _TemplateResponse.__init__


def patched_init(self, template, context, **kwargs):
    request = context.get("request")
    if request:
        context["user"] = getattr(request.state, "user", None)
    orig_init(self, template, context, **kwargs)


_TemplateResponse.__init__ = patched_init


# ========= РОУТЕРЫ =========

from auth import router as auth_router
from routers import (
    animals,
    feeds,
    feedings,
    expenses,
    purchases,
    employees,
    malfunctions,
    analytics_expenses,
    medical,
    rations,
    analytics_faults,
)

app.include_router(auth_router)
app.include_router(malfunctions.router)
app.include_router(animals.router)
app.include_router(feeds.router)
app.include_router(feedings.router)
app.include_router(expenses.router)
app.include_router(purchases.router)
app.include_router(employees.router)
app.include_router(analytics_expenses.router)
app.include_router(rations.router)
app.include_router(medical.router)
app.include_router(analytics_faults.router)


# ========= ГЛАВНАЯ (редирект на /login) =========

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})