from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
import psycopg2.extras

from db import get_connection
from permissions import role_required
from app import templates

router = APIRouter()


# ============================================================
# МОИ РАСХОДЫ — для зоотехника
# ============================================================
@router.get("/expenses/my", response_class=HTMLResponse)
@role_required(["zootechnician"])
async def my_expenses(request: Request):
    user = request.state.user
    employee_id = user["id"]

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute(
        """
        SELECT
            r."IDРасхода"     AS id,
            r."Дата"          AS date,
            k."Наименование"  AS feed_name,
            k."ЕдиницаИзмерения" AS unit,
            r."Количество"    AS quantity
        FROM "Расход" r
        JOIN "Корм" k ON k."IDКорма" = r."IDКорма"
        WHERE r."IDСотрудника" = %s
        ORDER BY r."Дата" DESC, r."IDРасхода" DESC
        """,
        (employee_id,)
    )

    expenses = cursor.fetchall()
    conn.close()

    return templates.TemplateResponse(
        "expenses_my.html",
        {
            "request": request,
            "user": user,
            "expenses": expenses,
        }
    )


# ============================================================
# ВСЕ РАСХОДЫ — для менеджера / директора / админа
# (простая версия, без аналитики, сделаем потом умнее)
# ============================================================
@router.get("/expenses", response_class=HTMLResponse)
@role_required(["manager", "director", "admin"])
async def all_expenses(request: Request):
    user = request.state.user

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute(
        """
        SELECT
            r."IDРасхода"     AS id,
            r."Дата"          AS date,
            s."ФИО"           AS employee_name,
            k."Наименование"  AS feed_name,
            k."ЕдиницаИзмерения" AS unit,
            r."Количество"    AS quantity
        FROM "Расход" r
        JOIN "Корм" k ON k."IDКорма" = r."IDКорма"
        JOIN "Сотрудник" s ON s."IDСотрудника" = r."IDСотрудника"
        ORDER BY r."Дата" DESC, r."IDРасхода" DESC
        """
    )

    expenses = cursor.fetchall()
    conn.close()

    return templates.TemplateResponse(
        "expenses_all.html",
        {
            "request": request,
            "user": user,
            "expenses": expenses,
        }
    )