from pathlib import Path
from decimal import Decimal
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from app.config import settings

OUT = Path("generated")
OUT.mkdir(exist_ok=True)

def _font():
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for p in candidates:
        if Path(p).exists():
            pdfmetrics.registerFont(TTFont("AppFont", p))
            return "AppFont"
    return "Helvetica"

def create_act(order, car, dents, paid):
    font = _font()
    path = OUT / f"act_order_{order.id}.pdf"
    doc = SimpleDocTemplate(str(path), pagesize=A4, rightMargin=35, leftMargin=35, topMargin=35, bottomMargin=35)
    styles = getSampleStyleSheet()
    styles["Normal"].fontName = font
    styles["Title"].fontName = font
    story = [
        Paragraph("АКТ ВИКОНАНИХ РОБІТ", styles["Title"]),
        Spacer(1, 12),
        Paragraph(f"Виконавець: {settings.business_name}", styles["Normal"]),
        Paragraph(f"Замовник: {order.customer_name or 'Не вказано'}", styles["Normal"]),
        Paragraph(f"Автомобіль: {car.brand} {car.model}", styles["Normal"]),
        Paragraph(f"Держномер: {car.plate}", styles["Normal"]),
        Spacer(1, 12),
    ]
    data = [["№", "Послуга", "Складність", "Матеріал", "Ціна"]]
    for d in dents:
        data.append([str(d.number), d.element, d.complexity, d.material, f"{d.price} грн"])
    data.append(["", "", "", "Разом", f"{order.total} грн"])
    table = Table(data, colWidths=[30, 180, 85, 75, 80])
    table.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.5, colors.black),
        ("FONTNAME", (0,0), (-1,-1), font),
        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
        ("ALIGN", (-1,1), (-1,-1), "RIGHT"),
    ]))
    story += [table, Spacer(1, 18),
              Paragraph(f"Оплачено: {paid} грн", styles["Normal"]),
              Paragraph(f"Залишок: {Decimal(order.total) - Decimal(paid)} грн", styles["Normal"]),
              Spacer(1, 30),
              Paragraph("Підпис виконавця: ____________________", styles["Normal"]),
              Spacer(1, 10),
              Paragraph("Підпис замовника: ____________________", styles["Normal"])]
    doc.build(story)
    return path
