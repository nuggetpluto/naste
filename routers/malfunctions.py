from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from db import get_connection
from session import session_data
from datetime import datetime

router = APIRouter()
templates = Jinja2Templates(directory="templates")


# ---------- СПИСОК НЕИСПРАВНОСТЕЙ ----------
@router.get("/malfunctions", response_class=HTMLResponse)
async def malfunctions_list(request: Request):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT m.*, e.full_name AS employee_name
        FROM malfunctions m
        LEFT JOIN employees e ON m.employee_id = e.id
        ORDER BY m.id DESC
    """)
    malfunctions = cursor.fetchall()
    conn.close()

    return templates.TemplateResponse("malfunctions.html", {
        "request": request,
        "malfunctions": malfunctions
    })


# ---------- ФОРМА ДОБАВЛЕНИЯ ----------
@router.get("/malfunctions/add", response_class=HTMLResponse)
async def add_malfunction_form(request: Request):

    # Проверка авторизации
    if "current_user_id" not in session_data:
        return RedirectResponse("/", status_code=303)

    # Список мест — обычные строки
    locations = [
        "Вольер",
        "Участок",
        "Кухня",
        "Склад",
        "Администрация",
        "Медпункт",
        "Террариум",
        "Вигвам",
        "Парк",
        "Питомник"
    ]

    return templates.TemplateResponse("malfunction_add.html", {
        "request": request,
        "locations": locations
    })


# ---------- ДОБАВЛЕНИЕ НЕИСПРАВНОСТИ ----------
@router.post("/malfunctions/add", response_class=HTMLResponse)
async def add_malfunction(
        request: Request,
        place: str = Form(...),
        description: str = Form(...)
):
    if "current_user_id" not in session_data:
        return RedirectResponse("/", status_code=303)

    employee_id = session_data["current_user_id"]

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO malfunctions (employee_id, created_at, description, place, status)
        VALUES (?, ?, ?, ?, ?)
    """, (
        employee_id,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        description,
        place,
        "Зафиксировано"
    ))

    conn.commit()
    conn.close()

    return RedirectResponse("/malfunctions", status_code=303)