from fastapi import APIRouter, Request, Query, Form
from fastapi.responses import HTMLResponse, RedirectResponse
import psycopg2.extras

from db import get_connection
from permissions import role_required
from app import templates

router = APIRouter()


# ============================================================
# 📋 СПИСОК КОРМОВ (с фильтрами)
# ============================================================
@router.get("/feeds", response_class=HTMLResponse)
@role_required(["admin", "director", "manager", "zootechnician"])
async def feeds_list(
    request: Request,
    feed_type: str | None = Query(default=None),      # фильтр по типу
    low_only: str | None = Query(default=None)        # фильтр "только на исходе"
):
    """
    Раздел «Корм» с фильтрами:
    - feed_type = "Сухой" / "Влажный" / "Комбикорм" / None (все)
    - low_only = "1" → показывать только те, что на исходе
    """

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    sql = """
        SELECT
            k."IDКорма"          AS id,
            k."Наименование"     AS name,
            k."Тип"              AS feed_type,
            k."ОстатокНаСкладе"  AS stock,

            COALESCE(r.avg_qty, 0) AS avg_qty,

            CASE
                WHEN r.avg_qty IS NULL OR r.avg_qty = 0 THEN FALSE
                WHEN k."ОстатокНаСкладе" < r.avg_qty THEN TRUE
                ELSE FALSE
            END AS is_low
        FROM "Корм" k
        LEFT JOIN (
            SELECT
                "IDКорма",
                AVG("Количество") AS avg_qty
            FROM "Рацион"
            GROUP BY "IDКорма"
        ) r ON r."IDКорма" = k."IDКорма"
        WHERE 1 = 1
    """

    params = []

    # -------------------------
    # ФИЛЬТР ПО ТИПУ КОРМА
    # -------------------------
    if feed_type:
        sql += ' AND k."Тип" = %s'
        params.append(feed_type)

    # -------------------------
    # ФИЛЬТР ТОЛЬКО "НА ИСХОДЕ"
    # -------------------------
    if low_only == "1":
        sql += " AND (CASE WHEN r.avg_qty IS NULL OR r.avg_qty = 0 THEN FALSE WHEN k.\"ОстатокНаСкладе\" < r.avg_qty THEN TRUE ELSE FALSE END) = TRUE"

    sql += ' ORDER BY k."Наименование"'

    cursor.execute(sql, params)
    feeds = cursor.fetchall()

    # Получаем список всех типов корма
    cursor.execute('SELECT DISTINCT "Тип" AS type FROM "Корм" ORDER BY "Тип"')
    feed_types = cursor.fetchall()

    conn.close()

    return templates.TemplateResponse(
        "feeds.html",
        {
            "request": request,
            "feeds": feeds,
            "feed_types": [t["type"] for t in feed_types],
            "selected_type": feed_type or "",
            "low_only": low_only,
            "user": request.state.user,
        },
    )


# ============================================================
# ➕ ДОБАВЛЕНИЕ
# ============================================================
@router.get("/feeds/add", response_class=HTMLResponse)
@role_required(["admin", "director", "manager"])
async def feed_add_form(request: Request):

    return templates.TemplateResponse(
        "feeds_add.html",
        {
            "request": request,
            "user": request.state.user,
        },
    )


@router.post("/feeds/add")
@role_required(["admin", "director", "manager"])
async def feed_add(
    request: Request,
    name: str = Form(...),
    feed_type: str = Form(...)
):
    name = name.strip()
    feed_type = feed_type.strip()

    if not name:
        return HTMLResponse("Наименование не может быть пустым", status_code=400)

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute('SELECT COALESCE(MAX("IDКорма"), 0) + 1 AS new_id FROM "Корм"')
    new_id = cursor.fetchone()["new_id"]

    cursor.execute(
        """
        INSERT INTO "Корм"
        ("IDКорма", "Наименование", "Тип", "ЕдиницаИзмерения", "ОстатокНаСкладе")
        VALUES (%s, %s, %s, 'кг', 0)
        """,
        (new_id, name, feed_type),
    )

    conn.commit()
    conn.close()

    return RedirectResponse("/feeds", status_code=303)