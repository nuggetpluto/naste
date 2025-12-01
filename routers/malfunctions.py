from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import psycopg2.extras
from datetime import datetime

from db import get_connection
from permissions import role_required
from session import session_data

router = APIRouter()
templates = Jinja2Templates(directory="templates")


# ============================================================
# 📌 СПИСОК НЕИСПРАВНОСТЕЙ + ФИЛЬТРЫ
# ============================================================
@router.get("/malfunctions", response_class=HTMLResponse)
async def malfunctions_list(request: Request):

    role = session_data.get("current_user_role")

    # Параметры фильтра
    place = request.query_params.get("place", "all")
    status = request.query_params.get("status", "all")

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    sql = """
        SELECT 
            m."IDНеисправности" AS id,
            m."ДатаФиксации" AS created_at,
            m."ОписаниеПроблемы" AS description,
            m."Место" AS place,
            m."СтатусУстранения" AS status,
            m."ДатаРешения" AS solved_at,
            s."ФИО" AS employee_name
        FROM "Неисправность" m
        LEFT JOIN "Сотрудник" s 
            ON m."IDСотрудника" = s."IDСотрудника"
        WHERE 1=1
    """

    params = []

    # Зоотехник — только вольеры
    if role == "zootechnician":
        sql += ' AND m."Место" = %s'
        params.append("Вольер")

    # Фильтр по месту
    if place in ("Вольер", "Участок"):
        sql += ' AND m."Место" = %s'
        params.append(place)

    # Фильтр по статусу
    if status in ("Зафиксировано", "В процессе", "Устранено"):
        sql += ' AND m."СтатусУстранения" = %s'
        params.append(status)

    # Сортировка
    sql += ' ORDER BY m."IDНеисправности" DESC'

    cursor.execute(sql, params)
    malfunctions = cursor.fetchall()

    conn.close()

    return templates.TemplateResponse(
        "malfunctions.html",
        {
            "request": request,
            "malfunctions": malfunctions,
            "role": role,
            "filter_place": place,
            "filter_status": status,
        }
    )


# ============================================================
# ➕ ФОРМА ДОБАВЛЕНИЯ
# ============================================================
@router.get("/malfunctions/add", response_class=HTMLResponse)
@role_required(["manager", "zootechnician"])
async def add_malfunction_form(request: Request):

    role = session_data["current_user_role"]

    # Менеджеру — выбор списка
    locations = ["Вольер", "Участок"] if role == "manager" else None

    return templates.TemplateResponse(
        "malfunctions_add.html",
        {
            "request": request,
            "locations": locations,
            "role": role
        }
    )


# ============================================================
# ➕ ДОБАВЛЕНИЕ (manager, zootechnician)
# ============================================================
@router.post("/malfunctions/add", response_class=HTMLResponse)
@role_required(["manager", "zootechnician"])
async def add_malfunction(request: Request, description: str = Form(...), place: str | None = Form(None)):

    employee_id = session_data["current_user_id"]
    role = session_data["current_user_role"]

    # Зоотехник добавляет ТОЛЬКО в "Вольер"
    if role == "zootechnician":
        place = "Вольер"

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO "Неисправность"
            ("IDСотрудника", "ДатаФиксации", "ОписаниеПроблемы", "Место", "СтатусУстранения")
        VALUES (%s, CURRENT_DATE, %s, %s, 'Зафиксировано')
    """, (employee_id, description, place))

    conn.commit()
    conn.close()

    return RedirectResponse("/malfunctions", status_code=303)


# ============================================================
# ✏ РЕДАКТИРОВАНИЕ (STATUS) — Только director
# ============================================================
@router.get("/malfunctions/edit/{mal_id}", response_class=HTMLResponse)
@role_required(["director"])
async def edit_malfunction_form(request: Request, mal_id: int):

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT 
            "IDНеисправности" AS id,
            "ОписаниеПроблемы" AS description,
            "Место" AS place,
            "СтатусУстранения" AS status
        FROM "Неисправность"
        WHERE "IDНеисправности" = %s
    """, (mal_id,))

    mal = cursor.fetchone()
    conn.close()

    return templates.TemplateResponse("malfunction_edit.html", {"request": request, "mal": mal})


@router.post("/malfunctions/edit/{mal_id}", response_class=HTMLResponse)
@role_required(["director"])
async def edit_malfunction(request: Request, mal_id: int):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT "СтатусУстранения" FROM "Неисправность" WHERE "IDНеисправности" = %s', (mal_id,))
    current = cursor.fetchone()[0]

    if current == "Зафиксировано":
        new_status = "В процессе"
        cursor.execute('UPDATE "Неисправность" SET "СтатусУстранения"=%s WHERE "IDНеисправности"=%s',
                       (new_status, mal_id))

    elif current == "В процессе":
        new_status = "Устранено"
        cursor.execute('UPDATE "Неисправность" SET "СтатусУстранения"=%s, "ДатаРешения"=CURRENT_DATE WHERE "IDНеисправности"=%s',
                       (new_status, mal_id))

    conn.commit()
    conn.close()

    return RedirectResponse("/malfunctions", status_code=303)

@router.get("/malfunctions/update-text/{mal_id}", response_class=HTMLResponse)
@role_required(["manager", "zootechnician"])
async def update_text_form(request: Request, mal_id: int):

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT "IDНеисправности" AS id, "ОписаниеПроблемы" AS description,
               "Место" AS place, "СтатусУстранения" AS status
        FROM "Неисправность"
        WHERE "IDНеисправности"=%s
    """, (mal_id,))

    mal = cursor.fetchone()
    conn.close()

    if not mal:
        return HTMLResponse("Не найдено", 404)

    if mal["status"] == "Устранено":
        return HTMLResponse("Эта неисправность уже устранена и не может быть изменена.", 400)

    return templates.TemplateResponse(
        "malfunction_update.html",
        {"request": request, "mal": mal, "role": session_data["current_user_role"]}
    )

@router.post("/malfunctions/update-text/{mal_id}", response_class=HTMLResponse)
@role_required(["manager", "zootechnician"])
async def update_text(request: Request, mal_id: int,
                      description: str = Form(...)):

    conn = get_connection()
    cursor = conn.cursor()

    # Проверяем статус
    cursor.execute(
        'SELECT "СтатусУстранения" FROM "Неисправность" WHERE "IDНеисправности"=%s',
        (mal_id,)
    )
    status = cursor.fetchone()[0]

    if status == "Устранено":
        conn.close()
        return HTMLResponse("Нельзя редактировать устранённую неисправность.", 400)

    # Меняем только описание — без 'Место'
    cursor.execute("""
        UPDATE "Неисправность"
        SET "ОписаниеПроблемы"=%s
        WHERE "IDНеисправности"=%s
    """, (description, mal_id))

    conn.commit()
    conn.close()

    return RedirectResponse("/malfunctions", status_code=303)