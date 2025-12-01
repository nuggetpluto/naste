from fastapi import APIRouter, Request, Form, Query
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
import psycopg2.extras

from db import get_connection
from permissions import role_required

router = APIRouter()
templates = Jinja2Templates(directory="templates")


# ============================================================
#  СПИСОК РАЦИОНОВ
# ============================================================

@router.get("/rations", response_class=HTMLResponse)
@role_required(["manager", "zootechnician"])
async def rations_list(
        request: Request,
        search: str | None = Query(default=None)
):

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    sql = """
        SELECT r."IDРациона" AS id,
               r."ВидЖивотного" AS species,
               k."Наименование" AS feed_name,
               r."Количество" AS amount,
               r."ЧастотаКормления" AS frequency
        FROM "Рацион" r
        JOIN "Корм" k ON r."IDКорма" = k."IDКорма"
    """

    params = []

    if search:
        sql += ' WHERE r."ВидЖивотного" ILIKE %s'
        params.append(f"%{search}%")

    sql += ' ORDER BY r."ВидЖивотного"'

    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()

    return templates.TemplateResponse(
        "rations.html",
        {"request": request, "rows": rows, "search": search or ""}
    )


# ============================================================
#  ФОРМА ДОБАВЛЕНИЯ
# ============================================================

@router.get("/rations/add", response_class=HTMLResponse)
@role_required(["manager", "zootechnician"])
async def rations_add_form(request: Request):

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute('SELECT "IDКорма", "Наименование" FROM "Корм" ORDER BY "Наименование"')
    feeds = cursor.fetchall()

    conn.close()

    return templates.TemplateResponse(
        "rations_add.html",
        {"request": request, "feeds": feeds, "error": None}
    )


# ============================================================
#  ДОБАВЛЕНИЕ
# ============================================================

@router.post("/rations/add")
@role_required(["manager", "zootechnician"])
async def rations_add(
        request: Request,
        feed_id: int = Form(...),
        species: str = Form(...),
        amount: int = Form(...),
        frequency: str = Form(...)
):

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Проверка количества
    if amount <= 0:
        return templates.TemplateResponse(
            "rations_add.html",
            {"request": request, "feeds": [], "error": "Количество должно быть положительным целым числом"}
        )

    # Проверка уникальности вида
    cursor.execute('SELECT 1 FROM "Рацион" WHERE "ВидЖивотного" = %s', (species,))
    if cursor.fetchone():
        return templates.TemplateResponse(
            "rations_add.html",
            {"request": request, "feeds": [], "error": "Такой рацион уже существует"}
        )

    cursor.execute("""
        INSERT INTO "Рацион"
        ("IDКорма", "ВидЖивотного", "Количество", "ЧастотаКормления")
        VALUES (%s, %s, %s, %s)
    """, (feed_id, species, amount, frequency))

    conn.commit()
    conn.close()
    return RedirectResponse("/rations", status_code=303)


# ============================================================
#  ФОРМА РЕДАКТИРОВАНИЯ
# ============================================================

@router.get("/rations/edit/{ration_id}", response_class=HTMLResponse)
@role_required(["manager", "zootechnician"])
async def rations_edit_form(request: Request, ration_id: int):

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute('SELECT * FROM "Рацион" WHERE "IDРациона" = %s', (ration_id,))
    ration = cursor.fetchone()

    cursor.execute('SELECT "IDКорма", "Наименование" FROM "Корм" ORDER BY "Наименование"')
    feeds = cursor.fetchall()

    conn.close()

    return templates.TemplateResponse(
        "rations_edit.html",
        {"request": request, "ration": ration, "feeds": feeds}
    )


# ============================================================
#  ОБНОВЛЕНИЕ
# ============================================================

@router.post("/rations/edit/{ration_id}")
@role_required(["manager", "zootechnician"])
async def rations_edit(
        request: Request,
        ration_id: int,
        feed_id: int = Form(...),
        amount: int = Form(...),
        frequency: str = Form(...)
):

    if amount <= 0:
        return HTMLResponse("Количество должно быть положительным целым числом")

    conn = get_connection()
    cursor = conn.cursor()

    # Вид животного НЕ меняем
    cursor.execute("""
        UPDATE "Рацион"
        SET "IDКорма"=%s,
            "Количество"=%s,
            "ЧастотаКормления"=%s
        WHERE "IDРациона"=%s
    """, (feed_id, amount, frequency, ration_id))

    conn.commit()
    conn.close()
    return RedirectResponse("/rations", status_code=303)