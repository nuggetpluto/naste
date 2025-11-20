from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from db import get_connection
from permissions import role_required

templates = Jinja2Templates(directory="templates")
router = APIRouter()


# -------------------------------------------------------
# СПИСОК РАСХОДОВ — admin + zootechnician
# -------------------------------------------------------
@router.get("/expenses", response_class=HTMLResponse)
@role_required(["admin", "zootechnician"])
async def expenses_list(request: Request):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT e.id,
               f.name AS feed_name,
               em.full_name AS employee_name,
               e.quantity,
               e.expense_date
        FROM expenses e
        JOIN feed f ON e.feed_id = f.id
        JOIN employees em ON e.employee_id = em.id
        ORDER BY e.expense_date DESC
    """)

    expenses = cursor.fetchall()
    conn.close()

    return templates.TemplateResponse(
        "expenses.html",
        {
            "request": request,
            "expenses": expenses
        }
    )


# -------------------------------------------------------
# ФОРМА ДОБАВЛЕНИЯ — admin + zootechnician
# -------------------------------------------------------
@router.get("/expenses/add", response_class=HTMLResponse)
@role_required(["admin", "zootechnician"])
async def add_expense_form(request: Request):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, name FROM feed")
    feeds = cursor.fetchall()

    cursor.execute("SELECT id, full_name FROM employees WHERE status='active'")
    employees = cursor.fetchall()

    conn.close()

    return templates.TemplateResponse(
        "add_expense.html",
        {
            "request": request,
            "feeds": feeds,
            "employees": employees
        }
    )


# -------------------------------------------------------
# ДОБАВЛЕНИЕ РАСХОДА — admin + zootechnician
# -------------------------------------------------------
@router.post("/expenses/add", response_class=HTMLResponse)
@role_required(["admin", "zootechnician"])
async def add_expense(
        request: Request,
        feed_id: int = Form(...),
        employee_id: int = Form(...),
        quantity: float = Form(...)
):
    conn = get_connection()
    cursor = conn.cursor()

    # уменьшаем остаток корма
    cursor.execute(
        "UPDATE feed SET quantity = quantity - ? WHERE id=?",
        (quantity, feed_id)
    )

    # добавляем запись о расходе
    cursor.execute("""
        INSERT INTO expenses (feed_id, employee_id, quantity)
        VALUES (?, ?, ?)
    """, (feed_id, employee_id, quantity))

    conn.commit()
    conn.close()

    return RedirectResponse(url="/expenses", status_code=303)