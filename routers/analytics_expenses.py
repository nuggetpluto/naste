from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
import psycopg2.extras
import io
import csv
from fastapi.responses import StreamingResponse
from db import get_connection
from permissions import role_required
from app import templates

router = APIRouter(
    prefix="/analytics",
    tags=["analytics"]
)


# ============================================================
# АНАЛИТИКА РАСХОДОВ КОРМА
# Только для директора
# ============================================================
@router.get("", response_class=HTMLResponse)
@role_required(["director"])
async def analytics_expenses(request: Request):
    """
    Страница аналитики расходов корма.
    Период фильтрации: ?period=day / month / all
    """
    period = request.query_params.get("period", "month")

    # Строим кусок WHERE в зависимости от периода
    where_sql = ""
    if period == "day":
        where_sql = 'WHERE r."Дата" = CURRENT_DATE'
    elif period == "month":
        where_sql = 'WHERE DATE_TRUNC(\'month\', r."Дата") = DATE_TRUNC(\'month\', CURRENT_DATE)'
    else:
        period = "all"  # на всякий случай, если пришло что-то другое

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # --------------------------------------------------------
    # 1. Расход по сотрудникам (для таблицы)
    # --------------------------------------------------------
    cursor.execute(
        f'''
        SELECT
            s."ФИО"                         AS employee_name,
            SUM(r."Количество")             AS total_amount
        FROM "Расход" r
        JOIN "Сотрудник" s
          ON s."IDСотрудника" = r."IDСотрудника"
        {where_sql}
        GROUP BY s."ФИО"
        ORDER BY total_amount DESC
        '''
    )
    by_employees = cursor.fetchall()

    # --------------------------------------------------------
    # 2. Расход по видам корма (для таблицы + Pie chart)
    # --------------------------------------------------------
    cursor.execute(
        f'''
        SELECT
            k."Наименование"                AS feed_name,
            SUM(r."Количество")             AS total_amount
        FROM "Расход" r
        JOIN "Корм" k
          ON k."IDКорма" = r."IDКорма"
        {where_sql}
        GROUP BY k."Наименование"
        ORDER BY total_amount DESC
        '''
    )
    by_feeds = cursor.fetchall()

    # данные для графика
    chart_labels = [row["feed_name"] for row in by_feeds]
    chart_data = [int(row["total_amount"]) for row in by_feeds]

    # --------------------------------------------------------
    # 3. Детальная таблица расходов
    # --------------------------------------------------------
    cursor.execute(
        f'''
        SELECT
            r."IDРасхода"                   AS id,
            r."Дата"                        AS date,
            s."ФИО"                         AS employee_name,
            k."Наименование"                AS feed_name,
            r."Количество"                  AS amount
        FROM "Расход" r
        JOIN "Сотрудник" s
          ON s."IDСотрудника" = r."IDСотрудника"
        JOIN "Корм" k
          ON k."IDКорма" = r."IDКорма"
        {where_sql}
        ORDER BY r."Дата" DESC, r."IDРасхода" DESC
        '''
    )
    details = cursor.fetchall()

    conn.close()

    return templates.TemplateResponse(
        "analytics_expenses.html",
        {
            "request": request,
            "user": request.state.user,
            "period": period,
            "by_employees": by_employees,
            "by_feeds": by_feeds,
            "details": details,
            "chart_labels": chart_labels,
            "chart_data": chart_data,
        },
    )

@router.get("/export/csv")
@role_required(["director"])
async def export_expenses_csv(
        request: Request,
        period: str = "month"
):
    """
    Экспорт детальной таблицы расходов в CSV
    """

    # --- WHERE по периоду ---
    where_sql = ""
    if period == "day":
        where_sql = 'WHERE r."Дата" = CURRENT_DATE'
    elif period == "month":
        where_sql = 'WHERE DATE_TRUNC(\'month\', r."Дата") = DATE_TRUNC(\'month\', CURRENT_DATE)'
    else:
        period = "all"

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # --- запрос детальной таблицы (как в интерфейсе) ---
    cursor.execute(
        f'''
        SELECT
            r."IDРасхода"                   AS id,
            r."Дата"                        AS date,
            s."ФИО"                         AS employee_name,
            k."Наименование"                AS feed_name,
            r."Количество"                  AS amount
        FROM "Расход" r
        JOIN "Сотрудник" s
          ON s."IDСотрудника" = r."IDСотрудника"
        JOIN "Корм" k
          ON k."IDКорма" = r."IDКорма"
        {where_sql}
        ORDER BY r."Дата" DESC, r."IDРасхода" DESC
        '''
    )
    rows = cursor.fetchall()
    conn.close()

    # --- создаём CSV ---
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')

    headers = ["ID", "Дата", "Сотрудник", "Корм", "Количество (кг)"]
    writer.writerow(headers)

    for r in rows:
        writer.writerow([
            r["id"],
            r["date"].strftime("%d.%m.%Y"),
            r["employee_name"],
            r["feed_name"],
            r["amount"]
        ])

    output.seek(0)

    filename = f"expenses_{period}.csv"

    return StreamingResponse(
        output,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename}"
        }
    )