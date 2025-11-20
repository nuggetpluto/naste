from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from db import get_connection
from permissions import role_required

router = APIRouter()
templates = Jinja2Templates(directory="templates")


# ============================================================
# 👥 СПИСОК СОТРУДНИКОВ — Только admin, director
# ============================================================

@router.get("/employees", response_class=HTMLResponse)
@role_required(["admin", "director"])
async def employees_list(request: Request):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, full_name, username, phone, role, status
        FROM employees
        ORDER BY id ASC
    """)
    employees = cursor.fetchall()

    conn.close()

    return templates.TemplateResponse(
        "employees.html",
        {
            "request": request,
            "employees": employees
        }
    )


# ============================================================
# ❗ ФОРМА ПОДТВЕРЖДЕНИЯ УВОЛЬНЕНИЯ — Только admin, director
# ============================================================

@router.get("/employees/fire/{employee_id}", response_class=HTMLResponse)
@role_required(["admin", "director"])
async def fire_confirm(request: Request, employee_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, full_name
        FROM employees
        WHERE id=?
    """, (employee_id,))
    employee = cursor.fetchone()

    conn.close()

    return templates.TemplateResponse(
        "employee_confirm_fire.html",
        {
            "request": request,
            "employee": employee
        }
    )


# ============================================================
# 🔥 УВОЛЬНЕНИЕ СОТРУДНИКА — Только admin, director
# ============================================================

@router.post("/employees/fire/{employee_id}", response_class=HTMLResponse)
@role_required(["admin", "director"])
async def fire_employee(request: Request, employee_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE employees
        SET status='inactive'
        WHERE id=?
    """, (employee_id,))

    conn.commit()
    conn.close()

    return RedirectResponse(url="/employees", status_code=303)