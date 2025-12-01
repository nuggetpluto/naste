from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
import psycopg2.extras
import io
import csv

from db import get_connection
from permissions import role_required
from app import templates

router = APIRouter(
    prefix="/analytics",
    tags=["analytics"]
)

# ============================================================
# СТРАНИЦА АНАЛИТИКИ ПО НЕИСПРАВНОСТЯМ
# ============================================================
@router.get("/faults", response_class=HTMLResponse)
@role_required(["admin", "director"])
async def faults_analytics_page(request: Request):
    """
    Страница аналитики по неисправностям.
    Фильтры и графики грузятся через JS.
    """
    return templates.TemplateResponse(
        "analytics_faults.html",
        {
            "request": request,
            "user": request.state.user,
        }
    )


# ============================================================
# API: ДАННЫЕ ДЛЯ ГИСТОГРАММЫ
# ============================================================
@router.get("/faults/chart")
@role_required(["admin", "director"])
async def faults_chart_data(
        request: Request,
        place: str = Query(..., description="Вольер или Участок"),
        date_from: str | None = Query(default=None),
        date_to: str | None = Query(default=None),
):
    """
    Возвращает количество неисправностей по статусам для выбранного места
    и периода.
    """

    if place not in ("Вольер", "Участок"):
        return JSONResponse({"error": "Некорректное значение поля 'place'."}, status_code=400)

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    sql = """
        SELECT
            n."СтатусУстранения"      AS status,
            COUNT(*)        AS cnt
        FROM "Неисправность" n
        WHERE n."Место" = %s
    """
    params = [place]

    if date_from:
        sql += ' AND n."ДатаФиксации" >= %s'
        params.append(date_from)

    if date_to:
        sql += ' AND n."ДатаФиксации" <= %s'
        params.append(date_to)

    sql += ' GROUP BY n."СтатусУстранения" ORDER BY n."СтатусУстранения"'

    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()

    # Приводим к фиксированному набору статусов
    statuses_order = ["Зафиксировано", "В процессе", "Устранено"]
    counts_map = {r["status"]: r["cnt"] for r in rows}

    labels = statuses_order
    data = [counts_map.get(s, 0) for s in statuses_order]

    return JSONResponse({"labels": labels, "data": data})


# ============================================================
# API: ТАБЛИЦА НЕИСПРАВНОСТЕЙ
# ============================================================
@router.get("/faults/table")
@role_required(["admin", "director"])
async def faults_table_data(
        request: Request,
        place: str = Query(..., description="Вольер или Участок"),
        date_from: str | None = Query(default=None),
        date_to: str | None = Query(default=None),
):
    """
    Возвращает детальную таблицу неисправностей для выбранного места и периода.
    """

    if place not in ("Вольер", "Участок"):
        return JSONResponse({"error": "Некорректное значение поля 'place'."}, status_code=400)

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    sql = """
        SELECT
            n."IDНеисправности" AS id,
            n."Место"            AS place,
            n."ОписаниеПроблемы"         AS description,
            n."СтатусУстранения" AS status,
            n."ДатаФиксации"     AS created_at,
            n."ДатаРешения"   AS resolved_at,
            s."ФИО"              AS employee_name
        FROM "Неисправность" n
        LEFT JOIN "Сотрудник" s
          ON n."IDСотрудника" = s."IDСотрудника"
        WHERE n."Место" = %s
    """
    params = [place]

    if date_from:
        sql += ' AND n."ДатаФиксации" >= %s'
        params.append(date_from)

    if date_to:
        sql += ' AND n."ДатаФиксации" <= %s'
        params.append(date_to)

    sql += ' ORDER BY n."IDНеисправности" DESC'

    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()

    # Приводим данные к удобному JSON
    data = [
        {
            "id": r["id"],
            "place": r["place"],
            "description": r["description"],
            "status": r["status"],
            "created_at": r["created_at"].strftime("%d.%m.%Y"),
            "resolved_at": r["resolved_at"].strftime("%d.%m.%Y") if r["resolved_at"] else "—",
            "employee": r["employee_name"] or "—",
        }
        for r in rows
    ]

    return JSONResponse({"rows": data})


# ============================================================
# ЭКСПОРТ В CSV
# ============================================================
@router.get("/faults/export/csv")
@role_required(["admin", "director"])
async def faults_export_csv(
        request: Request,
        place: str = Query(..., description="Вольер или Участок"),
        date_from: str | None = Query(default=None),
        date_to: str | None = Query(default=None),
):
    """
    Экспорт таблицы неисправностей в CSV с теми же фильтрами.
    """

    if place not in ("Вольер", "Участок"):
        return HTMLResponse("Некорректное значение поля 'place'.", status_code=400)

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # SQL-запрос с правильными именами колонок
    sql = """
        SELECT
            n."IDНеисправности" AS id,
            n."Место"            AS place,
            n."ОписаниеПроблемы" AS description,
            n."СтатусУстранения" AS status,
            n."ДатаФиксации"     AS created_at,
            n."ДатаРешения"      AS resolved_at,
            s."ФИО"              AS employee_name
        FROM "Неисправность" n
        LEFT JOIN "Сотрудник" s
            ON n."IDСотрудника" = s."IDСотрудника"
        WHERE n."Место" = %s
    """
    params = [place]

    if date_from:
        sql += ' AND n."ДатаФиксации" >= %s'
        params.append(date_from)

    if date_to:
        sql += ' AND n."ДатаФиксации" <= %s'
        params.append(date_to)

    sql += ' ORDER BY n."IDНеисправности" DESC'

    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()

    # --- Готовим CSV ---
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')

    headers = [
        "ID",
        "Место",
        "ОписаниеПроблемы",
        "СтатусУстранения",
        "Дата фиксации",
        "Дата решения",
        "Сотрудник",
    ]
    writer.writerow(headers)

    for r in rows:
        writer.writerow([
            r["id"],
            r["place"],
            r["description"],
            r["status"],
            r["created_at"].strftime("%d.%m.%Y"),
            r["resolved_at"].strftime("%d.%m.%Y") if r["resolved_at"] else "",
            r["employee_name"] or "",
        ])

    output.seek(0)

    # --- Исправляем Unicode в имени файла ---
    import unicodedata

    def to_ascii(text: str) -> str:
        return (
            unicodedata
            .normalize("NFKD", text)
            .encode("ascii", "ignore")
            .decode()
            .replace(" ", "_")
        )

    safe_place = to_ascii(place) or "export"
    filename = f"faults_{safe_place}.csv"

    # --- Отправляем файл ---
    return StreamingResponse(
        output,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )