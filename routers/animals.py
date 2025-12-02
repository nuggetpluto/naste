from fastapi import APIRouter, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

import psycopg2.extras
from psycopg2 import errors

from db import get_connection
from permissions import role_required

router = APIRouter()
templates = Jinja2Templates(directory="templates")



# ======================================================
# 📌 СПИСОК ЖИВОТНЫХ — менеджер + зоотехник
#   Фильтр по виду + фильтр по полу
# ======================================================
@router.get("/animals", response_class=HTMLResponse)
@role_required(["manager", "zootechnician"])
async def animals_list(
    request: Request,
    species: str | None = Query(default=None),
    gender: str | None = Query(default=None)   # << новый параметр
):
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    base_sql = """
        SELECT
            j."IDЖивотного"       AS id,
            j."Вид"               AS species,
            j."Кличка"            AS name,
            j."Возраст"           AS age,
            j."Пол"               AS gender,
            j."ДатаПоступления"   AS admission_date,
            j."СостояниеЗдоровья" AS health_status,
            s."ФИО"               AS employee_name,
            r."IDРациона"         AS ration_id,
            r."ВидЖивотного"      AS ration_species,
            r."Количество"        AS ration_amount,
            r."ЧастотаКормления"  AS ration_frequency,
            k."Наименование"      AS feed_name,
            k."ЕдиницаИзмерения"  AS feed_unit
        FROM "Животное" j
        LEFT JOIN "Сотрудник" s ON j."IDСотрудника" = s."IDСотрудника"
        LEFT JOIN "Рацион"   r ON j."IDРациона"     = r."IDРациона"
        LEFT JOIN "Корм"     k ON r."IDКорма"       = k."IDКорма"
    """

    conditions = []
    params = []

    # Фильтр по виду
    if species:
        conditions.append('j."Вид" ILIKE %s')
        params.append(f"%{species}%")

    # Фильтр по полу (м / ж)
    if gender in ["м", "ж"]:
        conditions.append('j."Пол" = %s')
        params.append(gender)

    # Применяем WHERE, если есть условия
    if conditions:
        base_sql += " WHERE " + " AND ".join(conditions)

    base_sql += ' ORDER BY j."IDЖивотного" ASC'

    cursor.execute(base_sql, params)
    rows = cursor.fetchall()
    conn.close()

    animals = []
    for row in rows:
        ration_text = "-"
        if row["ration_id"] is not None:
            parts = []
            if row["feed_name"]:
                parts.append(row["feed_name"])
            if row["ration_amount"] is not None and row["feed_unit"]:
                parts.append(f'{row["ration_amount"]} {row["feed_unit"]}')
            if row["ration_frequency"]:
                parts.append(row["ration_frequency"])
            ration_text = ", ".join(parts) if parts else f'Рацион #{row["ration_id"]}'

        animals.append(
            {
                "id": row["id"],
                "species": row["species"],
                "name": row["name"],
                "age": row["age"],
                "gender": row["gender"],
                "admission_date": row["admission_date"],
                "health_status": row["health_status"],
                "employee_name": row["employee_name"],
                "ration": ration_text,
            }
        )

    return templates.TemplateResponse(
        "animals.html",
        {
            "request": request,
            "animals": animals,
            "filter_species": species or "",
            "filter_gender": gender or "",        # << передаём в шаблон
        },
    )


# ======================================================
# 📌 ФОРМА ДОБАВЛЕНИЯ — только менеджер
#   Менеджер выбирает:
#       ✔ зоотехника
#       ✔ рацион
#   Процедура сама делает:
#       ✔ вставку животного
#       ✔ первичную медкарту
# ======================================================
@router.get("/animals/add", response_class=HTMLResponse)
@role_required(["manager"])
async def add_animal_form(request: Request):
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Только зоотехники
    cursor.execute(
        """
        SELECT
            "IDСотрудника" AS id,
            "ФИО"          AS full_name
        FROM "Сотрудник"
        WHERE "Должность" = 'Зоотехник'
        ORDER BY "ФИО"
        """
    )
    employees = cursor.fetchall()

    # Все рационы
    cursor.execute(
        """
        SELECT
            r."IDРациона"        AS id,
            r."ВидЖивотного"     AS species,
            r."Количество"       AS amount,
            r."ЧастотаКормления" AS frequency,
            k."Наименование"     AS feed_name,
            k."ЕдиницаИзмерения" AS feed_unit
        FROM "Рацион" r
        JOIN "Корм" k ON r."IDКорма" = k."IDКорма"
        ORDER BY r."ВидЖивотного", r."IDРациона"
        """
    )
    rations = cursor.fetchall()

    conn.close()

    return templates.TemplateResponse(
        "add_animal.html",
        {
            "request": request,
            "employees": employees,
            "rations": rations,
            "error": None,
        },
    )


# ======================================================
# 📌 ДОБАВЛЕНИЕ ЖИВОТНОГО — менеджер вызывает процедуру
# ======================================================
@router.post("/animals/add", response_class=HTMLResponse)
@role_required(["manager"])
async def add_animal(
    request: Request,
    species: str = Form(...),
    name: str = Form(...),
    age: int = Form(...),
    gender: str = Form(...),
    zootechnician_fio: str = Form(...),
    ration_id: int = Form(...),
):
    # ФИО менеджера из сессии
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse("/", status_code=303)

    manager_fio = user.get("full_name") or user.get("ФИО")

    # Значения для медкарты
    diag = "Здоров"
    treatment = None
    vaccines = None
    result = "Первичный осмотр"

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    try:
        cursor.execute(
            'SELECT "ДобавитьЖивотноеИМедкарту"(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
            (
                manager_fio,  # 1
                zootechnician_fio,  # 2
                species,  # 3
                age,  # 4
                name,  # 5
                gender,  # 6
                ration_id,  # 7
                diag,  # 8
                treatment,  # 9
                vaccines,  # 10
                result  # 11
            )
        )

        conn.commit()

    except errors.RaiseException as e:
        conn.rollback()

        # Красивое сообщение
        raw = str(e)
        msg = raw.split("CONTEXT:")[0].split("ERROR:", 1)[-1].strip()

        cursor.execute(
            """
            SELECT "IDСотрудника" AS id, "ФИО" AS full_name
            FROM "Сотрудник"
            WHERE "Должность" = 'Зоотехник'
            ORDER BY "ФИО"
            """
        )
        employees = cursor.fetchall()

        cursor.execute(
            """
            SELECT r."IDРациона" AS id, r."ВидЖивотного" AS species,
                   r."Количество" AS amount, r."ЧастотаКормления" AS frequency,
                   k."Наименование" AS feed_name, k."ЕдиницаИзмерения" AS feed_unit
            FROM "Рацион" r
            JOIN "Корм" k ON r."IDКорма" = k."IDКорма"
            ORDER BY r."ВидЖивотного"
            """
        )
        rations = cursor.fetchall()

        conn.close()
        return templates.TemplateResponse(
            "add_animal.html",
            {
                "request": request,
                "employees": employees,
                "rations": rations,
                "error": msg,
            },
        )

    except Exception as e:
        conn.rollback()
        print("Ошибка:", e)

        cursor.execute(
            """
            SELECT "IDСотрудника" AS id, "ФИО" AS full_name
            FROM "Сотрудник"
            WHERE "Должность" = 'Зоотехник'
            ORDER BY "ФИО"
            """
        )
        employees = cursor.fetchall()

        cursor.execute(
            """
            SELECT r."IDРациона" AS id, r."ВидЖивотного" AS species,
                   r."Количество" AS amount, r."ЧастотаКормления" AS frequency,
                   k."Наименование" AS feed_name, k."ЕдиницаИзмерения" AS feed_unit
            FROM "Рацион" r
            JOIN "Корм" k ON r."IDКорма" = k."IDКорма"
            ORDER BY r."ВидЖивотного"
            """
        )
        rations = cursor.fetchall()

        conn.close()
        return templates.TemplateResponse(
            "add_animal.html",
            {
                "request": request,
                "employees": employees,
                "rations": rations,
                "error": "Ошибка при добавлении животного.",
            }
        )

    conn.close()
    return RedirectResponse(url="/animals", status_code=303)


# ======================================================
# 📌 AJAX обновление состояния здоровья — менеджер
# ======================================================

from fastapi.responses import JSONResponse
from fastapi import Request

from fastapi.responses import JSONResponse
from fastapi import Request

@router.post("/animals/update_health_ajax/{animal_id}")
@role_required(["manager"])
async def update_health_ajax(request: Request, animal_id: int, status: str = Form(...)):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Проверяем текущее состояние
        cursor.execute(
            'SELECT "СостояниеЗдоровья" FROM "Животное" WHERE "IDЖивотного" = %s',
            (animal_id,)
        )
        current_status = cursor.fetchone()[0]

        # НЕЛЬЗЯ менять умершего
        if current_status == "Умер":
            conn.close()
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Нельзя изменять состояние умершего животного"}
            )

        # Обновление состояния
        cursor.execute(
            '''
            UPDATE "Животное"
            SET "СостояниеЗдоровья" = %s
            WHERE "IDЖивотного" = %s
            ''',
            (status, animal_id)
        )
        conn.commit()

    except Exception as e:
        conn.rollback()
        conn.close()
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

    conn.close()
    return JSONResponse(
        status_code=200,
        content={"success": True, "new_status": status}
    )


# ======================================================
# 📌 ОТМЕТИТЬ «УМЕР» — только зоотехник
# ======================================================
@router.get("/animals/mark_dead/{animal_id}", response_class=HTMLResponse)
@role_required(["zootechnician"])
async def mark_animal_dead(request: Request, animal_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        '''
        UPDATE "Животное"
        SET "СостояниеЗдоровья" = 'Умер'
        WHERE "IDЖивотного" = %s
        ''',
        (animal_id,),
    )

    conn.commit()
    conn.close()

    return RedirectResponse(url="/animals", status_code=303)

