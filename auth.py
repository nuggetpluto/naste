from fastapi import APIRouter, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, HTMLResponse
import psycopg2.extras

from db import get_connection
from session import session_data

router = APIRouter()
templates = Jinja2Templates(directory="templates")


# =====================
#       LOGIN
# =====================

@router.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login", response_class=HTMLResponse)
async def login(
    request: Request,
    full_name: str = Form(...),
    password: str = Form(...)
):
    """
    Вход по ФИО и паролю.
    """

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT
            "IDСотрудника" AS id,
            "ФИО" AS full_name,
            "Должность" AS position,
            "КонтактныеДанные" AS phone,
            "Пароль" AS password,
            "Статус" AS status,
            CASE
                WHEN "Должность" = 'Администратор' THEN 'admin'
                WHEN "Должность" = 'Руководитель'  THEN 'director'
                WHEN "Должность" = 'Менеджер'      THEN 'manager'
                WHEN "Должность" = 'Зоотехник'     THEN 'zootechnician'
                ELSE 'zootechnician'
            END AS role
        FROM "Сотрудник"
        WHERE "ФИО" = %s
          AND "Пароль" = %s
          AND "Статус" = 'Активен'
    """, (full_name, password))

    user = cursor.fetchone()
    conn.close()

    if not user:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Неверные ФИО или пароль, либо сотрудник не активен."}
        )

    session_data["current_user_id"] = user["id"]
    session_data["current_user_role"] = user["role"]
    session_data["current_user_name"] = user["full_name"]

    # ⬅ сразу отправляем на профиль
    return RedirectResponse(url="/profile", status_code=303)


# =====================
#     REGISTER
# =====================

@router.get("/register", response_class=HTMLResponse)
async def register_form(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@router.post("/register", response_class=HTMLResponse)
async def register(
    request: Request,
    full_name: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    phone: str = Form(""),
    role: str = Form("zootechnician"),
):

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Проверка телефона
    if phone:
        cursor.execute('SELECT 1 FROM "Сотрудник" WHERE "КонтактныеДанные" = %s', (phone,))
        if cursor.fetchone():
            conn.close()
            return templates.TemplateResponse(
                "register.html",
                {"request": request, "error": "Телефон уже используется."}
            )

    cursor.execute('SELECT COALESCE(MAX("IDСотрудника"), 0) + 1 AS new_id FROM "Сотрудник"')
    new_id = cursor.fetchone()["new_id"]

    role_to_position = {
        "admin": "Администратор",
        "director": "Руководитель",
        "manager": "Менеджер",
        "zootechnician": "Зоотехник",
    }
    position = role_to_position.get(role, "Зоотехник")

    cursor.execute("""
        INSERT INTO "Сотрудник"
        ("IDСотрудника", "ФИО", "Должность",
         "КонтактныеДанные", "ГрафикРаботы", "Пароль", "Статус")
        VALUES (%s, %s, %s, %s, %s, %s, 'активен')
    """, (new_id, full_name, position, phone if phone else None, "5/2 08:00-18:00", password))

    conn.commit()
    conn.close()

    return templates.TemplateResponse(
        "register.html",
        {"request": request, "message": "Сотрудник успешно зарегистрирован!"}
    )


# =====================
#     HOME — теперь не нужен
# =====================

@router.get("/home", response_class=HTMLResponse)
async def home_page(request: Request):
    # Полностью заменяем домашнюю страницу на переход к профилю
    return RedirectResponse("/profile", status_code=303)


# =====================
#     PROFILE
# =====================

PROFILE_SELECT_SQL = """
    SELECT
        "IDСотрудника" AS id,
        "ФИО" AS full_name,
        "Должность" AS position,
        "КонтактныеДанные" AS phone,
        "Пароль" AS password,
        "Статус" AS status,
        CASE
            WHEN "Должность" = 'Администратор' THEN 'admin'
            WHEN "Должность" = 'Руководитель'  THEN 'director'
            WHEN "Должность" = 'Менеджер'      THEN 'manager'
            WHEN "Должность" = 'Зоотехник'     THEN 'zootechnician'
            ELSE 'zootechnician'
        END AS role
    FROM "Сотрудник"
    WHERE "IDСотрудника" = %s
"""


@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):

    if "current_user_id" not in session_data:
        return RedirectResponse(url="/login", status_code=303)

    user_id = session_data["current_user_id"]

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute(PROFILE_SELECT_SQL, (user_id,))
    user = cursor.fetchone()
    conn.close()

    return templates.TemplateResponse(
        "profile.html",
        {
            "request": request,
            "user": user,
            "message": None,
            "error": None,
        },
    )


# =====================
#   UPDATE PASSWORD
# =====================

@router.post("/profile/update", response_class=HTMLResponse)
async def update_profile(
    request: Request,
    old_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
):

    if "current_user_id" not in session_data:
        return RedirectResponse("/login")

    user_id = session_data["current_user_id"]

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute(PROFILE_SELECT_SQL, (user_id,))
    user = cursor.fetchone()

    if not user:
        conn.close()
        return RedirectResponse("/login", status_code=303)

    if old_password != user["password"]:
        conn.close()
        return templates.TemplateResponse(
            "profile.html",
            {"request": request, "user": user, "error": "Старый пароль неверный.", "message": None},
        )

    if new_password != confirm_password:
        conn.close()
        return templates.TemplateResponse(
            "profile.html",
            {"request": request, "user": user, "error": "Пароли не совпадают.", "message": None},
        )

    cursor.execute(
        'UPDATE "Сотрудник" SET "Пароль" = %s WHERE "IDСотрудника" = %s',
        (new_password, user_id),
    )
    conn.commit()
    conn.close()

    user["password"] = new_password

    return templates.TemplateResponse(
        "profile.html",
        {"request": request, "user": user, "message": "Пароль успешно обновлён.", "error": None},
    )


# =====================
#       LOGOUT
# =====================

@router.get("/logout")
async def logout():
    session_data.clear()
    return RedirectResponse("/login", status_code=303)