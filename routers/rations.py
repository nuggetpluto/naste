from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from db import get_connection
from permissions import role_required
from datetime import datetime

router = APIRouter()
templates = Jinja2Templates(directory="templates")


# ============================================================
# 📋 СПИСОК РАЦИОНОВ (admin, zootechnician)
# ============================================================

@router.get("/rations", response_class=HTMLResponse)
@role_required(["admin", "zootechnician"])
async def rations_list(request: Request):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            r.id,
            a.name || ' (' || a.species || ')' AS animal_full,
            f.name AS feed_name,
            r.amount,
            r.created_at
        FROM rations r
        JOIN animals a ON r.animal_id = a.id
        JOIN feed f ON r.feed_id = f.id
        ORDER BY r.id DESC
    """)

    rations = cursor.fetchall()
    conn.close()

    return templates.TemplateResponse(
        "rations.html",
        {"request": request, "rations": rations}
    )


# ============================================================
# ✚ ФОРМА ДОБАВЛЕНИЯ
# ============================================================

@router.get("/rations/add", response_class=HTMLResponse)
@role_required(["admin", "zootechnician"])
async def add_ration_form(request: Request):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, name || ' (' || species || ')' AS animal_full FROM animals WHERE status='Активен'")
    animals = cursor.fetchall()

    cursor.execute("SELECT id, name FROM feed")
    feeds = cursor.fetchall()

    conn.close()

    return templates.TemplateResponse(
        "rations_add.html",
        {"request": request, "animals": animals, "feeds": feeds}
    )


# ============================================================
# ➕ ДОБАВЛЕНИЕ РАЦИОНА
# ============================================================

@router.post("/rations/add", response_class=HTMLResponse)
@role_required(["admin", "zootechnician"])
async def add_ration(
        request: Request,
        animal_id: int = Form(...),
        feed_id: int = Form(...),
        amount: float = Form(...)
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO rations (animal_id, feed_id, amount, created_at)
        VALUES (?, ?, ?, ?)
    """, (
        animal_id,
        feed_id,
        amount,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()
    conn.close()

    return RedirectResponse("/rations", status_code=303)


# ============================================================
# ✏️ ФОРМА РЕДАКТИРОВАНИЯ
# ============================================================

@router.get("/rations/edit/{ration_id}", response_class=HTMLResponse)
@role_required(["admin", "zootechnician"])
async def edit_ration_form(request: Request, ration_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM rations WHERE id=?", (ration_id,))
    ration = cursor.fetchone()

    cursor.execute("SELECT id, name || ' (' || species || ')' AS animal_full FROM animals WHERE status='Активен'")
    animals = cursor.fetchall()

    cursor.execute("SELECT id, name FROM feed")
    feeds = cursor.fetchall()

    conn.close()

    return templates.TemplateResponse(
        "rations_edit.html",
        {
            "request": request,
            "ration": ration,
            "animals": animals,
            "feeds": feeds,
        }
    )


# ============================================================
# 💾 СОХРАНЕНИЕ РЕДАКТИРОВАНИЯ
# ============================================================

@router.post("/rations/edit/{ration_id}", response_class=HTMLResponse)
@role_required(["admin", "zootechnician"])
async def edit_ration(
        request: Request,
        ration_id: int,
        animal_id: int = Form(...),
        feed_id: int = Form(...),
        amount: float = Form(...)
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE rations
        SET animal_id=?, feed_id=?, amount=?
        WHERE id=?
    """, (animal_id, feed_id, amount, ration_id))

    conn.commit()
    conn.close()

    return RedirectResponse("/rations", status_code=303)


# ============================================================
# ❌ УДАЛЕНИЕ РАЦИОНА
# ============================================================

@router.get("/rations/delete/{ration_id}", response_class=HTMLResponse)
@role_required(["admin", "zootechnician"])
async def delete_ration(ration_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM rations WHERE id=?", (ration_id,))
    conn.commit()
    conn.close()

    return RedirectResponse("/rations", status_code=303)