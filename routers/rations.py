from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from permissions import role_required
from db import get_connection

router = APIRouter()
templates = Jinja2Templates(directory="templates")


# ============================================================
#  Список рационов
# ============================================================

@router.get("/rations", response_class=HTMLResponse)
@role_required(["admin", "zootechnician"])
async def rations_list(request: Request):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT r.id,
               r.species,
               f.name AS feed_name,
               r.amount,
               r.frequency,
               r.schedule
        FROM rations r
        JOIN feed f ON r.feed_id = f.id
        ORDER BY r.species ASC
    """)

    rows = cursor.fetchall()
    conn.close()

    return templates.TemplateResponse(
        "rations.html",
        {"request": request, "rows": rows}
    )


# ============================================================
#  Страница добавления
# ============================================================

@router.get("/rations/add", response_class=HTMLResponse)
@role_required(["admin", "zootechnician"])
async def rations_add_form(request: Request):

    conn = get_connection()
    cursor = conn.cursor()

    # список кормов
    cursor.execute("SELECT id, name FROM feed ORDER BY name")
    feeds = cursor.fetchall()

    # уникальные виды животных
    cursor.execute("SELECT DISTINCT species FROM animals ORDER BY species")
    species_list = [row["species"] for row in cursor.fetchall()]

    conn.close()

    return templates.TemplateResponse(
        "rations_add.html",
        {"request": request, "feeds": feeds, "species_list": species_list}
    )


# ============================================================
#  Обработка добавления
# ============================================================

@router.post("/rations/add")
@role_required(["admin", "zootechnician"])
async def rations_add(
        request: Request,
        feed_id: int = Form(...),
        species: str = Form(...),
        amount: float = Form(...),
        frequency: str = Form(...),
        schedule: str = Form("2 раза в день")
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO rations (feed_id, species, amount, frequency, schedule)
        VALUES (?, ?, ?, ?, ?)
    """, (feed_id, species, amount, frequency, schedule))

    conn.commit()
    conn.close()
    return RedirectResponse("/rations", status_code=303)


# ============================================================
#  Страница редактирования
# ============================================================

@router.get("/rations/edit/{ration_id}", response_class=HTMLResponse)
@role_required(["admin", "zootechnician"])
async def rations_edit_form(request: Request, ration_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM rations WHERE id=?", (ration_id,))
    ration = cursor.fetchone()

    # корма
    cursor.execute("SELECT id, name FROM feed ORDER BY name")
    feeds = cursor.fetchall()

    # виды
    cursor.execute("SELECT DISTINCT species FROM animals ORDER BY species")
    species_list = [row["species"] for row in cursor.fetchall()]

    conn.close()

    return templates.TemplateResponse(
        "rations_edit.html",
        {"request": request, "ration": ration, "feeds": feeds, "species_list": species_list}
    )


# ============================================================
#  Обновление
# ============================================================

@router.post("/rations/edit/{ration_id}")
@role_required(["admin", "zootechnician"])
async def rations_edit(
        request: Request,
        ration_id: int,
        feed_id: int = Form(...),
        species: str = Form(...),
        amount: float = Form(...),
        frequency: str = Form(...),
        schedule: str = Form("2 раза в день")
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE rations
        SET feed_id=?, species=?, amount=?, frequency=?, schedule=?
        WHERE id=?
    """, (feed_id, species, amount, frequency, schedule, ration_id))

    conn.commit()
    conn.close()
    return RedirectResponse("/rations", status_code=303)


# ============================================================
#  Удаление
# ============================================================

@router.get("/rations/delete/{ration_id}")
@role_required(["admin", "zootechnician"])
async def rations_delete(request: Request, ration_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM rations WHERE id=?", (ration_id,))
    conn.commit()
    conn.close()

    return RedirectResponse("/rations", status_code=303)