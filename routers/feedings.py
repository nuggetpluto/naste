from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from db import get_connection
from permissions import role_required

templates = Jinja2Templates(directory="templates")
router = APIRouter()


# -------------------------------------------------------
# СПИСОК КОРМЛЕНИЙ — доступ admin + zootechnician
# -------------------------------------------------------
@router.get("/feedings", response_class=HTMLResponse)
@role_required(["admin", "zootechnician"])
async def feedings_list(request: Request):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            f.id,
            a.name || ' (' || a.species || ')' AS animal_full,
            fd.name AS feed_name,
            e.full_name AS employee_name,
            f.amount,
            f.feeding_time
        FROM feedings f
        JOIN animals a ON f.animal_id = a.id
        JOIN feed fd ON f.feed_id = fd.id
        JOIN employees e ON f.employee_id = e.id
        ORDER BY f.id DESC
    """)
    feedings = cursor.fetchall()
    conn.close()
    return templates.TemplateResponse("feedings.html", {"request": request, "feedings": feedings})


# -------------------------------------------------------
# ФОРМА ДОБАВЛЕНИЯ — admin + zootechnician
# -------------------------------------------------------
@router.get("/feedings/add", response_class=HTMLResponse)
@role_required(["admin", "zootechnician"])
async def add_feeding_form(request: Request):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, name || ' (' || species || ')' AS animal_full FROM animals WHERE status='Активен'")
    animals = cursor.fetchall()

    cursor.execute("SELECT id, name FROM feed")
    feeds = cursor.fetchall()

    cursor.execute("SELECT id, full_name FROM employees WHERE status='active'")
    employees = cursor.fetchall()

    conn.close()
    return templates.TemplateResponse(
        "add_feeding.html",
        {
            "request": request,
            "animals": animals,
            "feeds": feeds,
            "employees": employees
        }
    )


# -------------------------------------------------------
# ДОБАВЛЕНИЕ КОРМЛЕНИЯ — admin + zootechnician
# -------------------------------------------------------
@router.post("/feedings/add", response_class=HTMLResponse)
@role_required(["admin", "zootechnician"])
async def add_feeding(
        request: Request,
        animal_id: int = Form(...),
        feed_id: int = Form(...),
        employee_id: int = Form(...),
        amount: float = Form(...)
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT quantity FROM feed WHERE id=?", (feed_id,))
    feed = cursor.fetchone()

    if not feed or feed["quantity"] < amount:
        conn.close()
        return templates.TemplateResponse(
            "add_feeding.html",
            {
                "request": request,
                "error": "Недостаточно корма на складе!"
            }
        )

    cursor.execute("UPDATE feed SET quantity = quantity - ? WHERE id=?", (amount, feed_id))

    cursor.execute("""
        INSERT INTO feedings (animal_id, feed_id, employee_id, amount)
        VALUES (?, ?, ?, ?)
    """, (animal_id, feed_id, employee_id, amount))

    conn.commit()
    conn.close()

    return RedirectResponse(url="/feedings", status_code=303)