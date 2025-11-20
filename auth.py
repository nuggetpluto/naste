from fastapi import APIRouter, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, HTMLResponse
from db import get_connection
from session import session_data

router = APIRouter()
templates = Jinja2Templates(directory="templates")


# ------------------ Вход ------------------

@router.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login", response_class=HTMLResponse)
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM employees 
        WHERE username=? AND password=? AND status='active'
    """, (username, password))
    user = cursor.fetchone()
    conn.close()

    if not user:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Неверный логин или пароль, либо сотрудник уволен."}
        )

    # Псевдо-сессия
    session_data["current_user_id"] = user["id"]

    # После успешного входа ведём на главную
    return RedirectResponse(url="/home", status_code=303)


# ------------------ Регистрация ------------------

@router.get("/register", response_class=HTMLResponse)
async def register_form(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@router.post("/register", response_class=HTMLResponse)
async def register(request: Request,
                   full_name: str = Form(...),
                   username: str = Form(...),
                   password: str = Form(...),
                   phone: str = Form(""),
                   role: str = Form("zootechnician")):

    conn = get_connection()
    cursor = conn.cursor()

    # Проверяем уникальность логина
    cursor.execute("SELECT id FROM employees WHERE username=?", (username,))
    if cursor.fetchone():
        conn.close()
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Логин уже используется."}
        )

    # Проверяем уникальность телефона, если он указан
    if phone:
        cursor.execute("SELECT id FROM employees WHERE phone=?", (phone,))
        if cursor.fetchone():
            conn.close()
            return templates.TemplateResponse(
                "register.html",
                {"request": request, "error": "Телефон уже используется."}
            )

    cursor.execute("""
        INSERT INTO employees (full_name, username, password, phone, role)
        VALUES (?, ?, ?, ?, ?)
    """, (full_name, username, password, phone, role))

    conn.commit()
    conn.close()

    return templates.TemplateResponse(
        "register.html",
        {"request": request, "message": "Сотрудник успешно зарегистрирован!"}
    )


# ------------------ Главная (/home) ------------------

@router.get("/home", response_class=HTMLResponse)
async def home_page(request: Request):

    # Проверка авторизации
    if "current_user_id" not in session_data:
        return RedirectResponse(url="/login", status_code=303)

    user_id = session_data["current_user_id"]

    conn = get_connection()
    cursor = conn.cursor()

    # Загружаем данные пользователя полностью
    cursor.execute("SELECT * FROM employees WHERE id=?", (user_id,))
    user = cursor.fetchone()

    # --- СТАТИСТИКА только для admin + director ---
    stats = {}

    if user["role"] in ("admin", "director"):
        cursor.execute("SELECT COUNT(*) FROM animals")
        stats["animals"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM employees WHERE status='active'")
        stats["employees"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM purchases")
        stats["purchases"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM malfunctions")
        stats["malfunctions"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM feedings")
        stats["feedings"] = cursor.fetchone()[0]

        cursor.execute("SELECT name, quantity FROM feed WHERE quantity < 5 ORDER BY quantity ASC")
        stats["low_feed"] = cursor.fetchall()

    conn.close()

    # ---- Рендер по роли ----
    if user["role"] == "admin":
        return templates.TemplateResponse(
            "home_admin.html",
            {"request": request, "user": user, "stats": stats}
        )

    if user["role"] == "director":
        return templates.TemplateResponse(
            "home_director.html",
            {"request": request, "user": user, "stats": stats}
        )

    if user["role"] == "manager":
        return templates.TemplateResponse(
            "home_manager.html",
            {"request": request, "user": user}
        )

    if user["role"] == "zootechnician":
        return templates.TemplateResponse(
            "home_zootechnician.html",
            {"request": request, "user": user}
        )

    # fallback (если роль неизвестна)
    return RedirectResponse("/profile")


# ------------------ Профиль ------------------

@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    if "current_user_id" not in session_data:
        return RedirectResponse(url="/login", status_code=303)

    user_id = session_data["current_user_id"]

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM employees WHERE id=?", (user_id,))
    user = cursor.fetchone()
    conn.close()

    return templates.TemplateResponse(
        "profile.html",
        {
            "request": request,
            "title": "Профиль сотрудника",
            "user": user
        }
    )


# ------------------ Обновление профиля ------------------

@router.post("/profile/update", response_class=HTMLResponse)
async def update_profile(request: Request,
                         phone: str = Form(...),
                         password: str = Form("")):

    if "current_user_id" not in session_data:
        return RedirectResponse(url="/login", status_code=303)

    user_id = session_data["current_user_id"]

    conn = get_connection()
    cursor = conn.cursor()

    # Проверка: телефон должен быть уникальным
    cursor.execute("""
        SELECT id FROM employees 
        WHERE phone=? AND id <> ?
    """, (phone, user_id))
    exist = cursor.fetchone()

    if exist:
        # Телефон уже у другого сотрудника
        cursor.execute("SELECT * FROM employees WHERE id=?", (user_id,))
        user = cursor.fetchone()
        conn.close()
        return templates.TemplateResponse(
            "profile.html",
            {
                "request": request,
                "title": "Профиль сотрудника",
                "error": "Этот номер телефона уже закреплён за другим сотрудником.",
                "user": user
            }
        )

    # Обновляем телефон
    cursor.execute("UPDATE employees SET phone=? WHERE id=?", (phone, user_id))

    # Обновляем пароль, если пользователь ввёл его
    if password.strip():
        cursor.execute("UPDATE employees SET password=? WHERE id=?", (password, user_id))

    conn.commit()

    # Берём обновлённые данные
    cursor.execute("SELECT * FROM employees WHERE id=?", (user_id,))
    user = cursor.fetchone()
    conn.close()

    return templates.TemplateResponse(
        "profile.html",
        {
            "request": request,
            "title": "Профиль сотрудника",
            "message": "Данные успешно обновлены!",
            "user": user
        }
    )


# ------------------ Выход ------------------

@router.get("/logout")
async def logout():
    session_data.clear()
    return RedirectResponse(url="/login", status_code=303)