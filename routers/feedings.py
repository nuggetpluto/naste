from fastapi import APIRouter, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
import psycopg2.extras

from db import get_connection
from permissions import role_required
from app import templates

router = APIRouter()


# ======================================================
# 📌 СПИСОК КОРМЛЕНИЙ — только для зоотехника
# ======================================================
@router.get("/feedings", response_class=HTMLResponse)
@role_required(["zootechnician"])
async def feedings_list(
   request: Request,
   search: str | None = Query(default=None)   # <-- поиск по виду
):
   user = request.state.user
   employee_id = user["id"]

   conn = get_connection()
   cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

   base_sql = """
       SELECT
           f."IDКормления" AS id,
           f."ДатаИВремя"  AS feeding_time,
           j."Кличка"      AS animal_name,
           j."Вид"         AS animal_species,
           s."ФИО"         AS employee_name
       FROM "Кормление" f
       JOIN "Животное" j  ON f."IDЖивотного"  = j."IDЖивотного"
       JOIN "Сотрудник" s ON f."IDСотрудника" = s."IDСотрудника"
       WHERE f."IDСотрудника" = %s
   """

   params = [employee_id]

   # 🔸 Фильтр по виду животного
   if search:
       base_sql += ' AND j."Вид" ILIKE %s'
       params.append(f"%{search}%")

   base_sql += ' ORDER BY f."IDКормления" DESC'

   cursor.execute(base_sql, params)
   feedings = cursor.fetchall()
   conn.close()

   return templates.TemplateResponse(
       "feedings.html",
       {
           "request": request,
           "user": user,
           "feedings": feedings,
           "search_value": search or "",
       }
   )


# ======================================================
# 📌 ФОРМА ДОБАВЛЕНИЯ — зоотехник
# ======================================================
@router.get("/feedings/add", response_class=HTMLResponse)
@role_required(["zootechnician"])
async def feeding_add_form(request: Request, error: str | None = None):
    user = request.state.user
    employee_id = user["id"]

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute(
        """
        SELECT
            "IDЖивотного" AS id,
            "Кличка"      AS name,
            "Вид"        AS species
        FROM "Животное"
        WHERE "IDСотрудника" = %s
        ORDER BY "Кличка"
        """,
        (employee_id,)
    )

    animals = cursor.fetchall()
    conn.close()

    return templates.TemplateResponse(
        "feeding_add.html",
        {
            "request": request,
            "user": user,
            "animals": animals,
            "error": error,
        }
    )


# ======================================================
# 📌 POST — добавление кормления
# ======================================================
@router.post("/feedings/add", response_class=HTMLResponse)
@role_required(["zootechnician"])
async def feeding_add(
        request: Request,
        animal_id: int = Form(...),
):
    user = request.state.user
    employee_id = user["id"]

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # 1. Находим рацион
    cursor.execute(
        """
        SELECT
            r."IDКорма"    AS feed_id,
            r."Количество" AS ration_quantity
        FROM "Рацион" r
        JOIN "Животное" j
          ON r."ВидЖивотного" = j."Вид"
        WHERE j."IDЖивотного" = %s
        """,
        (animal_id,)
    )
    ration = cursor.fetchone()

    if not ration:
        conn.close()
        return await feeding_add_form(
            request,
            error="Для этого животного не задан рацион."
        )

    feed_id = ration["feed_id"]
    need_qty = ration["ration_quantity"]

    # 2. Проверяем остаток
    cursor.execute(
        """
        SELECT "ОстатокНаСкладе" AS stock
        FROM "Корм"
        WHERE "IDКорма" = %s
        """,
        (feed_id,)
    )
    stock = cursor.fetchone()["stock"]

    if stock < need_qty:
        conn.close()
        return await feeding_add_form(
            request,
            error=f"❌ Недостаточно корма! Нужно {need_qty}, доступно {stock}"
        )

    # 3. Проводим кормление
    cursor.execute(
        """
        INSERT INTO "Кормление"
            ("IDЖивотного", "IDСотрудника", "ДатаИВремя")
        VALUES (%s, %s, NOW())
        RETURNING "IDКормления"
        """,
        (animal_id, employee_id)
    )
    feeding_id = cursor.fetchone()["IDКормления"]

    cursor.execute(
        """
        UPDATE "Корм"
        SET "ОстатокНаСкладе" = "ОстатокНаСкладе" - %s
        WHERE "IDКорма" = %s
        """,
        (need_qty, feed_id)
    )

    cursor.execute('SELECT COALESCE(MAX("IDРасхода"), 0) + 1 AS new_id FROM "Расход"')
    exp_id = cursor.fetchone()["new_id"]

    cursor.execute(
        """
        INSERT INTO "Расход"
            ("IDРасхода", "IDКорма", "IDСотрудника", "Дата", "Количество")
        VALUES (%s, %s, %s, CURRENT_DATE, %s)
        """,
        (exp_id, feed_id, employee_id, need_qty)
    )

    conn.commit()
    conn.close()

    return RedirectResponse("/feedings", status_code=303)