from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
import psycopg2.extras
from psycopg2 import errors

from db import get_connection
from permissions import role_required
from app import templates

router = APIRouter()


# ============================================================
# СПИСОК ЗАКУПОК
# ============================================================
from fastapi import APIRouter, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
import psycopg2.extras
from psycopg2 import errors

from db import get_connection
from permissions import role_required
from app import templates

router = APIRouter()


# ============================================================
# СПИСОК ЗАКУПОК + ФИЛЬТРЫ
# ============================================================
@router.get("/purchases", response_class=HTMLResponse)
@role_required(["admin", "director", "manager"])
async def purchases_list(
        request: Request,
        search: str = Query(default="", description="Поиск по ФИО"),
        supplier: str = Query(default="", description="Фильтр по поставщику"),
        status: str = Query(default="", description="Фильтр по статусу"),
        date_from: str = Query(default="", description="Дата от"),
        date_to: str = Query(default="", description="Дата до"),
):

    filters = []
    params = []

    # Поиск по ФИО
    if search:
        filters.append('LOWER(s."ФИО") LIKE LOWER(%s)')
        params.append(f"%{search}%")

    # Поставщик
    if supplier:
        filters.append('z."Поставщик" = %s')
        params.append(supplier)

    # Статус
    if status:
        filters.append('z."СтатусПоставки" = %s')
        params.append(status)

    # Дата от
    if date_from:
        filters.append('z."ДатаЗаявки" >= %s')
        params.append(date_from)

    # Дата до
    if date_to:
        filters.append('z."ДатаЗаявки" <= %s')
        params.append(date_to)

    # Сборка WHERE
    where_sql = ""
    if filters:
        where_sql = "WHERE " + " AND ".join(filters)

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute(f"""
        SELECT
            z."IDЗакупки"      AS id,
            s."ФИО"            AS employee_name,
            z."Поставщик"      AS supplier,
            z."ДатаЗаявки"     AS request_date,
            z."СтатусПоставки" AS status
        FROM "Закупка" z
        JOIN "Сотрудник" s ON z."IDСотрудника" = s."IDСотрудника"
        {where_sql}
        ORDER BY z."IDЗакупки" DESC
    """, params)

    purchases = cursor.fetchall()

    # Для фильтрации по поставщикам
    cursor.execute('SELECT DISTINCT "Поставщик" AS supplier FROM "Закупка" ORDER BY "Поставщик"')
    suppliers = cursor.fetchall()

    conn.close()

    return templates.TemplateResponse(
        "purchases.html",
        {
            "request": request,
            "purchases": purchases,
            "suppliers": suppliers,
            "search": search,
            "supplier_value": supplier,
            "status_value": status,
            "date_from": date_from,
            "date_to": date_to,
            "user": request.state.user
        }
    )


# ============================================================
# ШАГ 1 — ФОРМА ВВОДА ПОСТАВЩИКА
# ============================================================
@router.get("/purchases/add", response_class=HTMLResponse)
@role_required(["manager", "director"])
async def purchase_add_form(request: Request):
    return templates.TemplateResponse(
        "purchases_add.html",
        {"request": request, "user": request.state.user},
    )


@router.post("/purchases/add")
@role_required(["manager", "director"])
async def purchase_add_step2(request: Request, supplier: str = Form(...)):
    employee_id = request.state.user["id"]

    return RedirectResponse(
        f"/purchases/create?supplier={supplier.strip()}&employee_id={employee_id}",
        status_code=303
    )


# ============================================================
# ШАГ 2 — СТРАНИЦА ДО СОЗДАНИЯ ЗАКУПКИ
# ============================================================
@router.get("/purchases/create", response_class=HTMLResponse)
@role_required(["manager", "director"])
async def purchase_create_form(request: Request, supplier: str, employee_id: int):

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute('SELECT "IDКорма" AS id, "Наименование" AS name FROM "Корм" ORDER BY "Наименование"')
    feeds = cursor.fetchall()
    conn.close()

    purchase = {"supplier": supplier, "employee_id": employee_id}

    return templates.TemplateResponse(
        "purchases_create_items.html",
        {
            "request": request,
            "purchase": purchase,
            "feeds": feeds,
            "items": [],
            "error": None,
            "user": request.state.user
        },
    )


# ============================================================
# ШАГ 2 — ДОБАВЛЕНИЕ ПОЗИЦИИ (СОЗДАНИЕ ЗАКУПКИ)
# ============================================================
@router.post("/purchases/create/add_item")
@role_required(["manager", "director"])
async def purchase_create_add_item(
        request: Request,
        supplier: str = Form(...),
        employee_id: int = Form(...),
        feed_id: int = Form(...),
        quantity: int = Form(...)
):

    if quantity <= 0:
        return HTMLResponse("Количество должно быть > 0", status_code=400)

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Ищем закупку только со статусом Заявка отправлена
    cursor.execute("""
        SELECT "IDЗакупки" AS id
        FROM "Закупка"
        WHERE "Поставщик" = %s
          AND "IDСотрудника" = %s
          AND "СтатусПоставки" = 'Заявка отправлена'
        ORDER BY "IDЗакупки" DESC
        LIMIT 1
    """, (supplier, employee_id))

    existing = cursor.fetchone()

    # Если нет — создаём
    if not existing:
        cursor.execute('SELECT COALESCE(MAX("IDЗакупки"), 0) + 1 AS new_id FROM "Закупка"')
        purchase_id = cursor.fetchone()["new_id"]

        cursor.execute("""
            INSERT INTO "Закупка"
                ("IDЗакупки", "IDСотрудника", "ДатаЗаявки", "Поставщик", "СтатусПоставки")
            VALUES (%s, %s, CURRENT_DATE, %s, 'Заявка отправлена')
        """, (purchase_id, employee_id, supplier))

    else:
        purchase_id = existing["id"]

    # Добавляем позицию
    cursor.execute("""
        INSERT INTO "СоставЗакупки" ("IDЗакупки", "IDКорма", "Количество")
        VALUES (%s, %s, %s)
        ON CONFLICT ("IDЗакупки","IDКорма") DO UPDATE
            SET "Количество" = "СоставЗакупки"."Количество" + EXCLUDED."Количество"
    """, (purchase_id, feed_id, quantity))

    conn.commit()
    conn.close()

    return RedirectResponse(f"/purchases/{purchase_id}", status_code=303)


# ============================================================
# ИЗМЕНЕНИЕ СТАТУСА — СО СВОИМ ОТЛАВЛИВАНИЕМ ОШИБОК
# ============================================================
@router.post("/purchases/{purchase_id}/status_update")
@role_required(["manager", "director"])
async def purchase_change_status(
        request: Request,
        purchase_id: int,
        status: str = Form(...)
):
    allowed = ["Заявка отправлена", "Ожидание", "Доставлено"]

    if status not in allowed:
        return HTMLResponse("Недопустимый статус!", status_code=400)

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Проверяем существование закупки
    cursor.execute("""
        SELECT "СтатусПоставки" AS status
        FROM "Закупка"
        WHERE "IDЗакупки" = %s
    """, (purchase_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return HTMLResponse("Закупка не найдена", status_code=404)

    # Попробуем обновить статус, ловим ошибки триггера
    try:
        cursor.execute("""
            UPDATE "Закупка"
            SET "СтатусПоставки" = %s
            WHERE "IDЗакупки" = %s
        """, (status, purchase_id))

    except errors.RaiseException as e:
        # Ошибка из триггера Postgres — достаём текст и показываем пользователю
        conn.rollback()
        conn.close()

        error_text = str(e).split("\n")[0].replace('ERROR:  ', '')
        return await purchase_detail(request, purchase_id, error_message=error_text)

    # Если переход к Доставлено — пополняем склад
    old_status = row["status"]
    if old_status != "Доставлено" and status == "Доставлено":

        cursor.execute("""
            SELECT "IDКорма", "Количество"
            FROM "СоставЗакупки"
            WHERE "IDЗакупки" = %s
        """, (purchase_id,))
        items = cursor.fetchall()

        for item in items:
            cursor.execute("""
                UPDATE "Корм"
                SET "ОстатокНаСкладе" = "ОстатокНаСкладе" + %s
                WHERE "IDКорма" = %s
            """, (item["Количество"], item["IDКорма"]))

    conn.commit()
    conn.close()

    return RedirectResponse(f"/purchases/{purchase_id}", status_code=303)


# ============================================================
# ПРОСМОТР ЗАКУПКИ
# ============================================================
@router.get("/purchases/{purchase_id}", response_class=HTMLResponse)
@role_required(["admin", "director", "manager"])
async def purchase_detail(request: Request, purchase_id: int, error_message: str = None):

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT
            z."IDЗакупки"      AS id,
            z."ДатаЗаявки"     AS request_date,
            z."Поставщик"      AS supplier,
            z."СтатусПоставки" AS status,
            s."ФИО"            AS employee_name
        FROM "Закупка" z
        JOIN "Сотрудник" s ON z."IDСотрудника" = s."IDСотрудника"
        WHERE z."IDЗакупки" = %s
    """, (purchase_id,))

    purchase = cursor.fetchone()

    if not purchase:
        conn.close()
        return HTMLResponse("Закупка не найдена", status_code=404)

    cursor.execute("""
        SELECT
            k."Наименование" AS feed_name,
            sz."Количество"  AS quantity
        FROM "СоставЗакупки" sz
        JOIN "Корм" k ON k."IDКорма" = sz."IDКорма"
        WHERE sz."IDЗакупки" = %s
    """, (purchase_id,))

    items = cursor.fetchall()

    cursor.execute("""
        SELECT "IDКорма" AS id, "Наименование" AS name
        FROM "Корм"
        ORDER BY "Наименование"
    """)
    feeds = cursor.fetchall()

    conn.close()

    allow_add = (purchase["status"] == "Заявка отправлена")

    return templates.TemplateResponse(
        "purchase_detail.html",
        {
            "request": request,
            "purchase": purchase,
            "items": items,
            "feeds": feeds,
            "allow_add": allow_add,
            "error": error_message,
            "user": request.state.user,
        },
    )

# ============================================================
# ДОБАВЛЕНИЕ ПОЗИЦИИ В ГОТОВУЮ ЗАКУПКУ
# ============================================================
@router.post("/purchases/{purchase_id}/add_item")
@role_required(["manager", "director"])
async def purchase_add_item(
        request: Request,
        purchase_id: int,
        feed_id: int = Form(...),
        quantity: int = Form(...)
):

    if quantity <= 0:
        return HTMLResponse("Количество должно быть > 0", status_code=400)

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT "СтатусПоставки" AS status
        FROM "Закупка"
        WHERE "IDЗакупки" = %s
    """, (purchase_id,))

    row = cursor.fetchone()

    if not row:
        conn.close()
        return HTMLResponse("Закупка не найдена", status_code=404)

    if row["status"] != "Заявка отправлена":
        conn.close()
        return await purchase_detail(request, purchase_id, error_message="Добавление запрещено: закупка уже принята в работу")

    cursor.execute("""
        SELECT "Количество"
        FROM "СоставЗакупки"
        WHERE "IDЗакупки" = %s AND "IDКорма" = %s
    """, (purchase_id, feed_id))

    exist = cursor.fetchone()

    if exist:
        cursor.execute("""
            UPDATE "СоставЗакупки"
            SET "Количество" = "Количество" + %s
            WHERE "IDЗакупки" = %s AND "IDКорма" = %s
        """, (quantity, purchase_id, feed_id))
    else:
        cursor.execute("""
            INSERT INTO "СоставЗакупки" ("IDЗакупки", "IDКорма", "Количество")
            VALUES (%s, %s, %s)
        """, (purchase_id, feed_id, quantity))

    conn.commit()
    conn.close()

    return RedirectResponse(f"/purchases/{purchase_id}", status_code=303)