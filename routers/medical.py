from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

import psycopg2.extras

from db import get_connection
from permissions import role_required
from app import templates

router = APIRouter()


# ======================================================
# 📌 /medical — список животных + фильтр по виду
# ======================================================
@router.get("/medical", response_class=HTMLResponse)
@role_required(["manager", "zootechnician"])
async def medical_animals_list(request: Request, species: str | None = None):

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    base_sql = '''
        SELECT
            j."IDЖивотного" AS id,
            j."Вид"         AS species,
            j."Кличка"      AS name,
            s."ФИО"         AS employee_name
        FROM "Животное" j
        LEFT JOIN "Сотрудник" s
               ON j."IDСотрудника" = s."IDСотрудника"
    '''

    params = []
    if species:
        base_sql += ' WHERE j."Вид" ILIKE %s'
        params.append(f"%{species}%")

    base_sql += ' ORDER BY j."IDЖивотного"'

    cursor.execute(base_sql, params)
    animals = cursor.fetchall()
    conn.close()

    return templates.TemplateResponse(
        "medical_index.html",
        {
            "request": request,
            "animals": animals,
            "filter_species": species or "",
        }
    )


# ======================================================
# 📌 Медкарта конкретного животного
# ======================================================
@router.get("/animals/{animal_id}/medical", response_class=HTMLResponse)
@role_required(["manager", "zootechnician"])
async def medical_list(request: Request, animal_id: int):

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute(
        '''
        SELECT "IDЖивотного" AS id,
               "Вид"         AS species,
               "Кличка"      AS name
        FROM "Животное"
        WHERE "IDЖивотного" = %s
        ''',
        (animal_id,)
    )
    animal = cursor.fetchone()

    if not animal:
        conn.close()
        return HTMLResponse("Животное не найдено", status_code=404)

    cursor.execute(
        '''
        SELECT 
            m."IDМедкарты"         AS id,
            m."ДатаОсмотра"        AS date,
            s."ФИО"                AS employee,
            m."Диагноз"            AS diagnosis,
            m."НазначенноеЛечение" AS treatment,
            m."Прививки"           AS vaccines,
            m."РезультатПроцедуры" AS result
        FROM "Медкарта" m
        JOIN "Сотрудник" s ON m."IDСотрудника" = s."IDСотрудника"
        WHERE m."IDЖивотного" = %s
        ORDER BY m."IDМедкарты" DESC
        ''',
        (animal_id,)
    )
    records = cursor.fetchall()

    conn.close()

    return templates.TemplateResponse(
        "medical.html",
        {
            "request": request,
            "animal": animal,
            "records": records,
        }
    )


# ======================================================
# 📌 Форма добавления медосмотра
# ======================================================
@router.get("/animals/{animal_id}/medical/add", response_class=HTMLResponse)
@role_required(["zootechnician"])
async def medical_add_form(request: Request, animal_id: int):

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute(
        '''
        SELECT "IDЖивотного" AS id,
               "Вид"         AS species,
               "Кличка"      AS name
        FROM "Животное"
        WHERE "IDЖивотного" = %s
        ''',
        (animal_id,)
    )
    animal = cursor.fetchone()
    conn.close()

    if not animal:
        return HTMLResponse("Животное не найдено", status_code=404)

    return templates.TemplateResponse(
        "medical_add.html",
        {
            "request": request,
            "animal": animal,
            "error": None,
            "form": None
        }
    )


# ======================================================
# 📌 POST — добавление медосмотра (с обработкой ошибок)
# ======================================================
@router.post("/animals/{animal_id}/medical/add", response_class=HTMLResponse)
@role_required(["zootechnician"])
async def medical_add(
    request: Request,
    animal_id: int,
    diagnosis: str = Form(...),   # делаем обязательным
    treatment: str = Form(""),
    vaccines: str = Form(""),
    result: str = Form(...),
):
    # Функция для красивой капитализации
    def capitalize(s: str | None):
        if not s or s.strip() == "":
            return ""
        s = s.strip()
        return s[0].upper() + s[1:]

    # Узнаём сотрудника (текущего зоотехника)
    user = request.state.user
    employee_fio = user.get("full_name") or user.get("ФИО")

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Получаем ID сотрудника
    cursor.execute(
        'SELECT "IDСотрудника" FROM "Сотрудник" WHERE "ФИО" = %s',
        (employee_fio,)
    )
    emp = cursor.fetchone()

    if not emp:
        conn.close()
        return HTMLResponse("Сотрудник не найден", status_code=400)

    employee_id = emp["IDСотрудника"]

    # Обработка полей
    diagnosis = capitalize(diagnosis)
    treatment_value = capitalize(treatment) or None
    vaccines = capitalize(vaccines) or None
    result = capitalize(result)

    # Загружаем животное (нужно для ошибок)
    cursor.execute(
        'SELECT "IDЖивотного" AS id, "Вид" AS species, "Кличка" AS name FROM "Животное" WHERE "IDЖивотного" = %s',
        (animal_id,)
    )
    animal = cursor.fetchone()

    if not animal:
        conn.close()
        return HTMLResponse("Животное не найдено", status_code=404)

    # Пытаемся сохранить
    try:
        cursor.execute(
            '''
            INSERT INTO "Медкарта"
                ("IDСотрудника", "IDЖивотного", "ДатаОсмотра",
                 "Диагноз", "НазначенноеЛечение", "Прививки", "РезультатПроцедуры")
            VALUES (%s, %s, CURRENT_DATE, %s, %s, %s, %s)
            ''',
            (employee_id, animal_id, diagnosis, treatment_value, vaccines, result)
        )
        conn.commit()

    except Exception as e:
        conn.rollback()
        raw = str(e)

        msg = raw.split("CONTEXT:", 1)[0]
        if "ERROR:" in msg:
            msg = msg.split("ERROR:", 1)[1].strip()

        conn.close()

        # Возвращаем страницу с ошибкой и заполненными полями
        return templates.TemplateResponse(
            "medical_add.html",
            {
                "request": request,
                "animal": animal,
                "error": msg,
                "form": {
                    "diagnosis": diagnosis or "",
                    "treatment": treatment or "",
                    "vaccines": vaccines or "",
                    "result": result or "",
                }
            }
        )

    conn.close()
    return RedirectResponse(url=f"/animals/{animal_id}/medical", status_code=303)