from fastapi import APIRouter, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
import psycopg2.extras

from db import get_connection
from permissions import role_required

router = APIRouter()
templates = Jinja2Templates(directory="templates")


# ============================================================
# 👥 СПИСОК СОТРУДНИКОВ — Директор (+ при желании Админ)
# ============================================================

@router.get("/employees", response_class=HTMLResponse)
@role_required(["director", "admin"])
async def employees_list(
    request: Request,
    search: str | None = None,
    role: str | None = None
):
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    sql = """
        SELECT 
            "IDСотрудника"   AS id,
            "ФИО"            AS full_name,
            "Должность"      AS role,
            "КонтактныеДанные" AS phone,
            "ГрафикРаботы"   AS schedule,
            "Статус"         AS status
        FROM "Сотрудник"
        WHERE 1=1
    """

    params: list = []

    if search:
        sql += ' AND "ФИО" ILIKE %s'
        params.append(f"%{search}%")

    if role:
        sql += ' AND "Должность" = %s'
        params.append(role)

    sql += ' ORDER BY "IDСотрудника"'

    cursor.execute(sql, params)
    employees = cursor.fetchall()
    conn.close()

    return templates.TemplateResponse(
        "employees.html",
        {
            "request": request,
            "employees": employees,
            "search": search or "",
            "selected_role": role or ""
        }
    )


# ============================================================
# ➕ ФОРМА ДОБАВЛЕНИЯ СОТРУДНИКА
# ============================================================

@router.get("/employees/add", response_class=HTMLResponse)
@role_required(["director", "admin"])
async def add_employee_form(request: Request):
    return templates.TemplateResponse(
        "employee_add.html",
        {
            "request": request,
            "error": None,
            "form": {}
        }
    )


# ============================================================
# ➕ ДОБАВЛЕНИЕ СОТРУДНИКА (POST)
# ============================================================

@router.post("/employees/add", response_class=HTMLResponse)
@role_required(["director", "admin"])
async def add_employee(
    request: Request,
    full_name: str = Form(...),
    role: str = Form(...),
    phone: str = Form(...),
    schedule: str = Form(""),
    password: str = Form(...)
):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO "Сотрудник"
                ("ФИО", "Должность", "КонтактныеДанные", "ГрафикРаботы", "Пароль", "Статус")
            VALUES (%s, %s, %s, %s, %s, 'Активен')
            """,
            (full_name, role, phone, schedule, password)
        )
        conn.commit()

    except psycopg2.Error as e:
        conn.rollback()

        msg = str(e)

        # -----------------------------
        # 🔥 Ловим уникальный телефон
        # -----------------------------
        if "КонтактныеДанные" in msg and "already exists" in msg:
            error_text = "Сотрудник с таким номером телефона уже существует."
        else:
            error_text = "Ошибка при добавлении сотрудника."

        return templates.TemplateResponse(
            "employee_add.html",
            {
                "request": request,
                "error": error_text,
                "form": {
                    "full_name": full_name,
                    "role": role,
                    "phone": phone,
                    "schedule": schedule
                }
            }
        )

    conn.close()
    return RedirectResponse(url="/employees", status_code=303)

# ============================================================
# ✏ РЕДАКТИРОВАНИЕ СОТРУДНИКА (форма)
# ============================================================

@router.get("/employees/edit/{employee_id}", response_class=HTMLResponse)
@role_required(["director", "admin"])
async def edit_employee_form(request: Request, employee_id: int):
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute(
        """
        SELECT 
            "IDСотрудника"   AS id,
            "ФИО"            AS full_name,
            "Должность"      AS role,
            "КонтактныеДанные" AS phone,
            "ГрафикРаботы"   AS schedule
        FROM "Сотрудник"
        WHERE "IDСотрудника" = %s
        """,
        (employee_id,)
    )
    employee = cursor.fetchone()
    conn.close()

    if not employee:
        return HTMLResponse("Сотрудник не найден", status_code=404)

    return templates.TemplateResponse(
        "employee_edit.html",
        {
            "request": request,
            "employee": employee,
            "error": None
        }
    )


# ============================================================
# ✏ РЕДАКТИРОВАНИЕ (POST)
# ============================================================

@router.post("/employees/edit/{employee_id}", response_class=HTMLResponse)
@role_required(["director", "admin"])
async def edit_employee(
    request: Request,
    employee_id: int,
    full_name: str = Form(...),
    phone: str = Form(""),
    schedule: str = Form("")
):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            UPDATE "Сотрудник"
            SET 
                "ФИО" = %s,
                "КонтактныеДанные" = %s,
                "ГрафикРаботы" = %s
            WHERE "IDСотрудника" = %s
            """,
            (full_name, phone, schedule, employee_id)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()

        # Перечитаем сотрудника для формы
        conn2 = get_connection()
        c2 = conn2.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        c2.execute(
            """
            SELECT 
                "IDСотрудника"   AS id,
                "ФИО"            AS full_name,
                "Должность"      AS role,
                "КонтактныеДанные" AS phone,
                "ГрафикРаботы"   AS schedule
            FROM "Сотрудник"
            WHERE "IDСотрудника" = %s
            """,
            (employee_id,)
        )
        employee = c2.fetchone()
        conn2.close()

        return templates.TemplateResponse(
            "employee_edit.html",
            {
                "request": request,
                "employee": employee,
                "error": str(e)
            }
        )

    conn.close()
    return RedirectResponse(url="/employees", status_code=303)


# ============================================================
# 🔥 УВОЛЬНЕНИЕ (Статус = 'Уволен', без восстановления)
# ============================================================

@router.get("/employees/fire/{employee_id}", response_class=HTMLResponse)
@role_required(["director", "admin"])
async def fire_confirm(request: Request, employee_id: int):
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute(
        '''
        SELECT "IDСотрудника" AS id,
               "ФИО"          AS full_name,
               "Должность"    AS role
        FROM "Сотрудник"
        WHERE "IDСотрудника" = %s
        ''',
        (employee_id,)
    )
    employee = cursor.fetchone()
    conn.close()

    if not employee:
        return HTMLResponse("Сотрудник не найден", status_code=404)

    # Руководителя увольнять нельзя
    if employee["role"] == "Руководитель":
        return HTMLResponse("Руководителя нельзя уволить", status_code=400)

    return templates.TemplateResponse(
        "employee_confirm_fire.html",
        {"request": request, "employee": employee}
    )


@router.post("/employees/fire/{employee_id}", response_class=HTMLResponse)
@role_required(["director", "admin"])
async def fire_employee(request: Request, employee_id: int):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # 1. Увольняем сотрудника
        cursor.execute(
            '''
            UPDATE "Сотрудник"
            SET "Статус" = 'Неактивен'
            WHERE "IDСотрудника" = %s
            ''',
            (employee_id,)
        )

        # 2. Переназначаем животных другому зоотехнику
        cursor.execute(
            '''
            SELECT "ПереназначитьЖивотныхПриУвольнении_fn"(%s)
            ''',
            (employee_id,)
        )

        conn.commit()

    except Exception as e:
        conn.rollback()

        # Загружаем сотрудника заново для шаблона
        cursor.execute(
            '''
            SELECT "IDСотрудника" AS id, "ФИО" AS full_name
            FROM "Сотрудник"
            WHERE "IDСотрудника" = %s
            ''',
            (employee_id,)
        )
        employee = cursor.fetchone()

        conn.close()

        return templates.TemplateResponse(
            "employee_confirm_fire.html",
            {
                "request": request,
                "employee": employee,
                "error": str(e)
            }
        )

    conn.close()
    return RedirectResponse(url="/employees", status_code=303)