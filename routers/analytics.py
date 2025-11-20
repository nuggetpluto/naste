from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from db import get_connection
from permissions import role_required

import io
import csv

templates = Jinja2Templates(directory="templates")

router = APIRouter(
    prefix="/analytics",
    tags=["analytics"]
)


# ========= СТРАНИЦА АНАЛИТИКИ =========

@router.get("", response_class=HTMLResponse)
@role_required(["admin", "director"])
async def analytics_page(request: Request):
    """
    Главная страница аналитики. Все данные загружаются по API.
    """
    return templates.TemplateResponse(
        "analytics.html",
        {
            "request": request,
            "title": "Аналитика"
        }
    )


# =============================================================================
# API: ЗАКУПКИ
# =============================================================================

@router.get("/api/purchases_status")
@role_required(["admin", "director"])
async def purchases_status(request: Request, month: str | None = Query(default=None)):
    """
    Данные для графика "Заявки на закупку по статусам"
    """
    conn = get_connection()
    cursor = conn.cursor()

    base_sql = """
        SELECT status, COUNT(*) AS cnt
        FROM purchases
    """
    params = []

    if month:
        base_sql += " WHERE strftime('%Y-%m', request_date) = ?"
        params.append(month)

    base_sql += " GROUP BY status"

    cursor.execute(base_sql, params)
    rows = cursor.fetchall()
    conn.close()

    labels = [r["status"] for r in rows]
    data = [r["cnt"] for r in rows]

    return JSONResponse({"labels": labels, "data": data})


@router.get("/api/purchases_table")
@role_required(["admin", "director"])
async def purchases_table(request: Request, month: str | None = Query(default=None)):
    """
    Таблица заявок на закупку
    """
    conn = get_connection()
    cursor = conn.cursor()

    base_sql = """
        SELECT p.id,
               e.full_name AS employee_name,
               p.status,
               p.request_date
        FROM purchases p
        JOIN employees e ON p.employee_id = e.id
    """
    params = []

    if month:
        base_sql += " WHERE strftime('%Y-%m', p.request_date) = ?"
        params.append(month)

    base_sql += " ORDER BY p.id DESC"

    cursor.execute(base_sql, params)
    rows = cursor.fetchall()
    conn.close()

    data = [
        {
            "id": r["id"],
            "employee": r["employee_name"],
            "status": r["status"],
            "date": r["request_date"]
        }
        for r in rows
    ]

    return JSONResponse({"rows": data})


# =============================================================================
# API: НЕИСПРАВНОСТИ
# =============================================================================

@router.get("/api/malfunctions_by_place")
@role_required(["admin", "director"])
async def malfunctions_by_place(request: Request, month: str | None = Query(default=None)):
    """
    Данные для графика "Количество неисправностей по местам"
    """
    conn = get_connection()
    cursor = conn.cursor()

    base_sql = """
        SELECT place, COUNT(*) AS cnt
        FROM malfunctions
    """
    params = []

    if month:
        base_sql += " WHERE strftime('%Y-%m', created_at) = ?"
        params.append(month)

    base_sql += " GROUP BY place ORDER BY cnt DESC"

    cursor.execute(base_sql, params)
    rows = cursor.fetchall()
    conn.close()

    labels = [r["place"] for r in rows]
    data = [r["cnt"] for r in rows]

    return JSONResponse({"labels": labels, "data": data})


@router.get("/api/malfunctions_table")
@role_required(["admin", "director"])
async def malfunctions_table(request: Request, month: str | None = Query(default=None)):
    """
    Детальная таблица неисправностей
    """
    conn = get_connection()
    cursor = conn.cursor()

    base_sql = """
        SELECT m.id,
               m.place,
               m.description,
               m.status,
               m.created_at,
               m.resolved_at,
               e.full_name AS employee_name
        FROM malfunctions m
        LEFT JOIN employees e ON m.employee_id = e.id
    """
    params = []

    if month:
        base_sql += " WHERE strftime('%Y-%m', m.created_at) = ?"
        params.append(month)

    base_sql += " ORDER BY m.id DESC"

    cursor.execute(base_sql, params)
    rows = cursor.fetchall()
    conn.close()

    data = [
        {
            "id": r["id"],
            "place": r["place"],
            "description": r["description"],
            "status": r["status"],
            "created_at": r["created_at"],
            "resolved_at": r["resolved_at"],
            "employee": r["employee_name"]
        }
        for r in rows
    ]

    return JSONResponse({"rows": data})


# =============================================================================
# API: КОРМЛЕНИЯ
# =============================================================================

@router.get("/api/feedings_top")
@role_required(["admin", "director"])
async def feedings_top(request: Request, month: str | None = Query(default=None)):
    """
    ТОП-5 животных по количеству кормлений
    """
    conn = get_connection()
    cursor = conn.cursor()

    base_sql = """
        SELECT a.name || ' (' || a.species || ')' AS animal_full,
               COUNT(*) AS cnt
        FROM feedings f
        JOIN animals a ON f.animal_id = a.id
    """
    params = []

    if month:
        base_sql += " WHERE strftime('%Y-%m', f.feeding_time) = ?"
        params.append(month)

    base_sql += """
        GROUP BY f.animal_id
        ORDER BY cnt DESC
        LIMIT 5
    """

    cursor.execute(base_sql, params)
    rows = cursor.fetchall()
    conn.close()

    labels = [r["animal_full"] for r in rows]
    data = [r["cnt"] for r in rows]

    return JSONResponse({"labels": labels, "data": data})


@router.get("/api/feedings_table")
@role_required(["admin", "director"])
async def feedings_table(request: Request, month: str | None = Query(default=None)):
    """
    Полная таблица кормлений
    """
    conn = get_connection()
    cursor = conn.cursor()

    base_sql = """
        SELECT f.id,
               a.name || ' (' || a.species || ')' AS animal_full,
               fd.name AS feed_name,
               e.full_name AS employee_name,
               f.amount,
               f.feeding_time
        FROM feedings f
        JOIN animals a ON f.animal_id = a.id
        JOIN feed fd ON f.feed_id = fd.id
        JOIN employees e ON f.employee_id = e.id
    """
    params = []

    if month:
        base_sql += " WHERE strftime('%Y-%m', f.feeding_time) = ?"
        params.append(month)

    base_sql += " ORDER BY f.id DESC"

    cursor.execute(base_sql, params)
    rows = cursor.fetchall()
    conn.close()

    data = [
        {
            "id": r["id"],
            "animal": r["animal_full"],
            "feed": r["feed_name"],
            "employee": r["employee_name"],
            "amount": r["amount"],
            "time": r["feeding_time"]
        }
        for r in rows
    ]

    return JSONResponse({"rows": data})


# =============================================================================
# ЭКСПОРТ В EXCEL (CSV)
# =============================================================================

def _csv_response(filename: str, headers: list[str], rows: list[list]):
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(headers)
    for r in rows:
        writer.writerow(r)
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@router.get("/export/purchases/excel")
@role_required(["admin", "director"])
async def export_purchases_excel(request: Request, month: str | None = Query(default=None)):
    conn = get_connection()
    cursor = conn.cursor()

    base_sql = """
        SELECT p.id,
               e.full_name AS employee_name,
               p.status,
               p.request_date
        FROM purchases p
        JOIN employees e ON p.employee_id = e.id
    """
    params = []
    if month:
        base_sql += " WHERE strftime('%Y-%m', p.request_date) = ?"
        params.append(month)

    base_sql += " ORDER BY p.id DESC"

    cursor.execute(base_sql, params)
    rows = cursor.fetchall()
    conn.close()

    headers = ["ID", "Сотрудник", "Статус", "Дата заявки"]
    data = [
        [r["id"], r["employee_name"], r["status"], r["request_date"]]
        for r in rows
    ]

    return _csv_response("purchases.csv", headers, data)


@router.get("/export/malfunctions/excel")
@role_required(["admin", "director"])
async def export_malfunctions_excel(request: Request, month: str | None = Query(default=None)):
    conn = get_connection()
    cursor = conn.cursor()

    base_sql = """
        SELECT m.id,
               m.place,
               m.description,
               m.status,
               m.created_at,
               m.resolved_at,
               e.full_name AS employee_name
        FROM malfunctions m
        LEFT JOIN employees e ON m.employee_id = e.id
    """
    params = []

    if month:
        base_sql += " WHERE strftime('%Y-%m', m.created_at) = ?"
        params.append(month)

    base_sql += " ORDER BY m.id DESC"

    cursor.execute(base_sql, params)
    rows = cursor.fetchall()
    conn.close()

    headers = ["ID", "Место", "Описание", "Статус", "Дата фиксации", "Дата устранения", "Ответственный"]
    data = [
        [
            r["id"],
            r["place"],
            r["description"],
            r["status"],
            r["created_at"],
            r["resolved_at"],
            r["employee_name"]
        ]
        for r in rows
    ]

    return _csv_response("malfunctions.csv", headers, data)


@router.get("/export/feedings/excel")
@role_required(["admin", "director"])
async def export_feedings_excel(request: Request, month: str | None = Query(default=None)):
    conn = get_connection()
    cursor = conn.cursor()

    base_sql = """
        SELECT f.id,
               a.name || ' (' || a.species || ')' AS animal_full,
               fd.name AS feed_name,
               e.full_name AS employee_name,
               f.amount,
               f.feeding_time
        FROM feedings f
        JOIN animals a ON f.animal_id = a.id
        JOIN feed fd ON f.feed_id = fd.id
        JOIN employees e ON f.employee_id = e.id
    """
    params = []

    if month:
        base_sql += " WHERE strftime('%Y-%m', f.feeding_time) = ?"
        params.append(month)

    base_sql += " ORDER BY f.id DESC"

    cursor.execute(base_sql, params)
    rows = cursor.fetchall()
    conn.close()

    headers = ["ID", "Животное", "Корм", "Сотрудник", "Количество", "Дата/время"]
    data = [
        [
            r["id"],
            r["animal_full"],
            r["feed_name"],
            r["employee_name"],
            r["amount"],
            r["feeding_time"]
        ]
        for r in rows
    ]

    return _csv_response("feedings.csv", headers, data)


# =============================================================================
# PDF (заглушка)
# =============================================================================

@router.get("/export/{section}/pdf")
@role_required(["admin", "director"])
async def export_pdf_placeholder(request: Request, section: str):
    return HTMLResponse(
        f"<h3>Экспорт PDF для '{section}' пока не реализован.</h3>",
        status_code=501
    )