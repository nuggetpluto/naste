from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.templating import _TemplateResponse

from db import init_db, get_connection
from session import session_data

# ====== MIDDLEWARE ДЛЯ ПОДГРУЗКИ ПОЛЬЗОВАТЕЛЯ ======

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        user = None

        user_id = session_data.get("current_user_id")
        if user_id:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM employees WHERE id=?", (user_id,))
            user = cursor.fetchone()
            conn.close()

        # теперь user доступен в request.state
        request.state.user = user

        response = await call_next(request)
        return response


# ====== FASTAPI APP ======

app = FastAPI(middleware=[Middleware(AuthMiddleware)])

app.mount("/static", StaticFiles(directory="static"), name="static")


# ====== ТЕМПЛАТЫ ======

templates = Jinja2Templates(directory="templates")


# --- Автоматическая вставка user во ВСЕ TemplateResponse ---

orig_init = _TemplateResponse.__init__

def patched_init(self, template, context, **kwargs):
    request = context.get("request")
    if request:
        # user попадёт во ВСЕ html
        context["user"] = getattr(request.state, "user", None)
    orig_init(self, template, context, **kwargs)

_TemplateResponse.__init__ = patched_init



# ====== РОУТЫ ======

from auth import router as auth_router
from routers import animals, feed, feedings, expenses, purchases, employees, malfunctions, analytics

app.include_router(auth_router)
app.include_router(malfunctions.router)
app.include_router(animals.router)
app.include_router(feed.router)
app.include_router(feedings.router)
app.include_router(expenses.router)
app.include_router(purchases.router)
app.include_router(employees.router)
app.include_router(analytics.router)


# ====== ИНИЦИАЛИЗАЦИЯ БД ======

init_db()


# ====== ГЛАВНАЯ = /login ======

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})