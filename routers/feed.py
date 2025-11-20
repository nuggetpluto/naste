from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from db import get_connection
from permissions import role_required

templates = Jinja2Templates(directory="templates")
router = APIRouter()


# -------------------------------------------------------
# Список кормов — только admin
# -------------------------------------------------------
@router.get("/feed", response_class=HTMLResponse)
@role_required(["admin"])
async def feed_list(request: Request):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM feed")
    feed = cursor.fetchall()
    conn.close()
    return templates.TemplateResponse("feed.html", {"request": request, "feed": feed})


# -------------------------------------------------------
# Форма добавления — только admin
# -------------------------------------------------------
@router.get("/feed/add", response_class=HTMLResponse)
@role_required(["admin"])
async def add_feed_form(request: Request):
    return templates.TemplateResponse("add_feed.html", {"request": request})


# -------------------------------------------------------
# Добавление корма — только admin
# -------------------------------------------------------
@router.post("/feed/add", response_class=HTMLResponse)
@role_required(["admin"])
async def add_feed(
    request: Request,
    name: str = Form(...),
    type: str = Form("Сухой"),
    unit: str = Form("кг"),
    quantity: float = Form(0)
):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO feed (name, type, unit, quantity) VALUES (?, ?, ?, ?)",
        (name, type, unit, quantity)
    )
    conn.commit()
    conn.close()
    return RedirectResponse(url="/feed", status_code=303)