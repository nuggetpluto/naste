from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from db import get_connection

router = APIRouter(
    prefix="/medical",
    tags=["medical"]
)

templates = Jinja2Templates(directory="templates")


# ================================
# Список медосмотров
# ================================
@router.get("", response_class=HTMLResponse)
async def medical_list(request: Request):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT m.id,
               a.name || ' (' || a.species || ')' AS animal_full,
               e.full_name AS employee_name,
               m.diagnosis,
               m.treatment,
               m.exam_date
        FROM medical m
        JOIN animals a ON m.animal_id = a.id
        JOIN employees e ON m.employee_id = e.id
        ORDER BY m.id DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    return templates.TemplateResponse(
        "medical.html",
        {"request": request, "rows": rows}
    )


# ================================
# Форма добавления
# ================================
@router.get("/add", response_class=HTMLResponse)
async def medical_add_form(request: Request):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, name, species FROM animals ORDER BY name")
    animals = cursor.fetchall()

    cursor.execute("SELECT id, full_name FROM employees WHERE status='active'")
    employees = cursor.fetchall()

    conn.close()

    return templates.TemplateResponse(
        "medical_add.html",
        {"request": request, "animals": animals, "employees": employees}
    )


# ================================
# POST — добавление медосмотра
# ================================
@router.post("/add", response_class=HTMLResponse)
async def medical_add(
        request: Request,
        animal_id: int = Form(...),
        employee_id: int = Form(...),
        diagnosis: str = Form(...),
        treatment: str = Form(""),
        exam_date: str = Form(...)
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO medical (animal_id, employee_id, diagnosis, treatment, exam_date)
        VALUES (?, ?, ?, ?, ?)
    """, (animal_id, employee_id, diagnosis, treatment if diagnosis != "Здоров" else None, exam_date))

    conn.commit()
    conn.close()

    return RedirectResponse("/medical", status_code=303)