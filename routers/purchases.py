from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from db import get_connection
from permissions import role_required

templates = Jinja2Templates(directory="templates")
router = APIRouter()


# ============================================================
# 📦 СПИСОК ЗАКУПОК — admin, director, manager
# ============================================================

@router.get("/purchases", response_class=HTMLResponse)
@role_required(["admin", "director", "manager"])
async def purchases_list(request: Request):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT p.id,
               e.full_name AS employee_name,
               p.status,
               p.request_date
        FROM purchases p
        JOIN employees e ON p.employee_id = e.id
        ORDER BY p.id DESC
    """)
    purchases = cursor.fetchall()
    conn.close()

    return templates.TemplateResponse(
        "purchases.html",
        {"request": request, "purchases": purchases}
    )


# ============================================================
# 📥 ФОРМА ДОБАВЛЕНИЯ ЗАКУПКИ — admin, director
# ============================================================

@router.get("/purchases/add", response_class=HTMLResponse)
@role_required(["admin", "director"])
async def add_purchase_form(request: Request):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, full_name FROM employees WHERE status='active'")
    employees = cursor.fetchall()

    conn.close()

    return templates.TemplateResponse(
        "add_purchase.html",
        {"request": request, "employees": employees}
    )


# ============================================================
# ➕ ДОБАВЛЕНИЕ НОВОЙ ЗАКУПКИ — admin, director
# ============================================================

@router.post("/purchases/add", response_class=HTMLResponse)
@role_required(["admin", "director"])
async def add_purchase(request: Request, employee_id: int = Form(...)):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO purchases (employee_id) VALUES (?)",
        (employee_id,)
    )

    conn.commit()
    conn.close()

    return RedirectResponse(url="/purchases", status_code=303)


# ============================================================
# 🔍 ПРОСМОТР СОСТАВА ЗАКУПКИ — admin, director, manager
# ============================================================

@router.get("/purchases/{purchase_id}", response_class=HTMLResponse)
@role_required(["admin", "director", "manager"])
async def purchase_detail(request: Request, purchase_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    # данные закупки
    cursor.execute("""
        SELECT p.id, e.full_name AS employee_name,
               p.status, p.request_date
        FROM purchases p
        JOIN employees e ON p.employee_id = e.id
        WHERE p.id=?
    """, (purchase_id,))
    purchase = cursor.fetchone()

    # состав закупки
    cursor.execute("""
        SELECT i.id, f.name AS feed_name, i.quantity
        FROM purchase_items i
        JOIN feed f ON i.feed_id = f.id
        WHERE i.purchase_id=?
    """, (purchase_id,))
    items = cursor.fetchall()

    # для admin/director показываем список кормов — для manager скрываем
    feeds = []
    if request.state.user["role"] in ("admin", "director"):
        cursor.execute("SELECT id, name FROM feed")
        feeds = cursor.fetchall()

    conn.close()

    return templates.TemplateResponse(
        "purchase_detail.html",
        {
            "request": request,
            "purchase": purchase,
            "items": items,
            "feeds": feeds
        }
    )


# ============================================================
# ➕ ДОБАВЛЕНИЕ ПОЗИЦИЙ В СОСТАВ — admin, director
# ============================================================

@router.post("/purchases/{purchase_id}/add_item", response_class=HTMLResponse)
@role_required(["admin", "director"])
async def add_purchase_item(
        request: Request,
        purchase_id: int,
        feed_id: int = Form(...),
        quantity: float = Form(...)
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO purchase_items (purchase_id, feed_id, quantity)
        VALUES (?, ?, ?)
    """, (purchase_id, feed_id, quantity))

    conn.commit()
    conn.close()

    return RedirectResponse(url=f"/purchases/{purchase_id}", status_code=303)


# ============================================================
# 🔄 ИЗМЕНЕНИЕ СТАТУСА ЗАКУПКИ — admin, director
# ============================================================

@router.get("/purchases/{purchase_id}/status_update", response_class=HTMLResponse)
@role_required(["admin", "director"])
async def change_status(purchase_id: int, status: str):
    conn = get_connection()
    cursor = conn.cursor()

    # Если заказ доставлен → пополняем склад
    if status == "Доставлено":
        cursor.execute("""
            SELECT feed_id, quantity
            FROM purchase_items
            WHERE purchase_id=?
        """, (purchase_id,))
        items = cursor.fetchall()

        for item in items:
            cursor.execute("""
                UPDATE feed
                SET quantity = quantity + ?
                WHERE id=?
            """, (item["quantity"], item["feed_id"]))

    # изменяем статус
    cursor.execute("""
        UPDATE purchases
        SET status=?
        WHERE id=?
    """, (status, purchase_id))

    conn.commit()
    conn.close()

    return RedirectResponse(url="/purchases", status_code=303)