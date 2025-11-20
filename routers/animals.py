from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from db import get_connection
from permissions import role_required

templates = Jinja2Templates(directory="templates")
router = APIRouter()


# -------------------------------------------------------
# Список животных — доступен admin + manager
# -------------------------------------------------------
@router.get("/animals", response_class=HTMLResponse)
@role_required(["admin", "manager"])
async def animals_list(request: Request):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.id, a.name, a.species, a.gender, a.health_status,
               a.birth_date, e.full_name AS employee_name, a.status
        FROM animals a
        LEFT JOIN employees e ON a.employee_id = e.id
    """)
    animals = cursor.fetchall()
    conn.close()
    return templates.TemplateResponse("animals.html", {"request": request, "animals": animals})


# -------------------------------------------------------
# Форма добавления животного — только admin
# -------------------------------------------------------
@router.get("/animals/add", response_class=HTMLResponse)
@role_required(["admin"])
async def add_animal_form(request: Request):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, full_name FROM employees WHERE status='active'")
    employees = cursor.fetchall()
    conn.close()
    return templates.TemplateResponse("add_animal.html", {"request": request, "employees": employees})


# -------------------------------------------------------
# Добавление животного — только admin
# -------------------------------------------------------
@router.post("/animals/add", response_class=HTMLResponse)
@role_required(["admin"])
async def add_animal(
    request: Request,
    name: str = Form(...),
    species: str = Form(...),
    gender: str = Form("Самец"),
    health_status: str = Form("Здоров"),
    birth_date: str = Form(""),
    employee_id: int = Form(None)
):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO animals (name, species, gender, health_status, birth_date, employee_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (name, species, gender, health_status, birth_date, employee_id))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/animals", status_code=303)


# -------------------------------------------------------
# Форма редактирования — только admin
# -------------------------------------------------------
@router.get("/animals/edit/{animal_id}", response_class=HTMLResponse)
@role_required(["admin"])
async def edit_animal_form(request: Request, animal_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM animals WHERE id=?", (animal_id,))
    animal = cursor.fetchone()

    cursor.execute("SELECT id, full_name FROM employees WHERE status='active'")
    employees = cursor.fetchall()
    conn.close()

    if not animal:
        return HTMLResponse("Животное не найдено", status_code=404)

    return templates.TemplateResponse("edit_animal.html", {
        "request": request,
        "animal": animal,
        "employees": employees
    })


# -------------------------------------------------------
# Редактирование животного — только admin
# -------------------------------------------------------
@router.post("/animals/edit/{animal_id}", response_class=HTMLResponse)
@role_required(["admin"])
async def edit_animal(
    request: Request,
    animal_id: int,
    name: str = Form(...),
    species: str = Form(...),
    gender: str = Form(...),
    health_status: str = Form(...),
    birth_date: str = Form(""),
    employee_id: int = Form(None),
):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE animals
        SET name=?, species=?, gender=?, health_status=?, birth_date=?, employee_id=?
        WHERE id=?
    """, (name, species, gender, health_status, birth_date, employee_id, animal_id))
    conn.commit()
    conn.close()

    return RedirectResponse(url="/animals", status_code=303)


# -------------------------------------------------------
# Деактивация (умер) — только admin
# -------------------------------------------------------
@router.get("/animals/deactivate/{animal_id}", response_class=HTMLResponse)
@role_required(["admin"])
async def deactivate_animal(animal_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE animals SET status='Умер' WHERE id=?", (animal_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/animals", status_code=303)