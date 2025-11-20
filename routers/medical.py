from fastapi import APIRouter, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from db import get_connection
from permissions import role_required

router = APIRouter()
templates = Jinja2Templates(directory="templates")


# ============================================================
# 📋 СПИСОК МЕДИЦИНСКИХ ОСМОТРОВ (admin, zootechnician)
# ============================================================

@router.get("/medical", response_class=HTMLResponse)
@role_required(["admin", "zootechnician"])
async def medical_list(request: Request):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            m.id,
            a.name || ' (' || a.species || ')' AS animal_full,
            e.full_name AS employee_full,
            m.check_date,
            m.diagnosis,
            m.notes
        FROM medical_checks m
        JOIN animals a ON m.animal_id = a.id
        JOIN employees e ON m.employee_id = e.id
        ORDER BY m.id DESC
    """)

    checks = cursor.fetchall()
    conn.close()

    return templates.TemplateResponse(
        "medical.html",
        {"request": request, "checks": checks}
    )


# ============================================================
# 📌 ФОРМА ДОБАВЛЕНИЯ ОСМОТРА (admin, zootechnician)
# ============================================================

@router.get("/medical/add", response_class=HTMLResponse)
@role_required(["admin", "zootechnician"])
async def add_medical_form(request: Request):

    conn = get_connection()
    cursor = conn.cursor()

    # только активные животные
    cursor.execute("SELECT id, name || ' (' || species || ')' AS animal_full FROM animals WHERE status='Активен'")
    animals = cursor.fetchall()

    # только активные сотрудники
    cursor.execute("SELECT id, full_name FROM employees WHERE status='active'")
    employees = cursor.fetchall()

    conn.close()

    return templates.TemplateResponse(
        "medical_add.html",
        {
            "request": request,
            "animals": animals,
            "employees": employees
        }
    )


# ============================================================
# ➕ ДОБАВЛЕНИЕ ОСМОТРА (admin, zootechnician)
# ============================================================

@router.post("/medical/add", response_class=HTMLResponse)
@role_required(["admin", "zootechnician"])
async def add_medical(
        request: Request,
        animal_id: int = Form(...),
        employee_id: int = Form(...),
        check_date: str = Form(...),
        diagnosis: str = Form(...),
        notes: str = Form("")
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO medical_checks (animal_id, employee_id, check_date, diagnosis, notes)
        VALUES (?, ?, ?, ?, ?)
    """, (animal_id, employee_id, check_date, diagnosis, notes))

    conn.commit()
    conn.close()

    return RedirectResponse(url="/medical", status_code=303)