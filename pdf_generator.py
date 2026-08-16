import os
import io
import base64
import logging
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

import pricing
import config

logger = logging.getLogger(__name__)

# Кирилиця в PDF: шрифт DejaVu Sans вбудований прямо в код (font_data.py,
# base64) — так надійніше, ніж окремий .ttf-файл, який легко забути
# скопіювати при оновленні проєкту. Якщо з якоїсь причини font_data.py
# відсутній — пробуємо резервні варіанти (папка fonts/ або системні шрифти).
FONT_NAME = "Helvetica"
FONT_BOLD = "Helvetica-Bold"

try:
    from font_data import DEJAVU_SANS_REGULAR_B64, DEJAVU_SANS_BOLD_B64

    pdfmetrics.registerFont(TTFont(
        "DejaVuSans", io.BytesIO(base64.b64decode(DEJAVU_SANS_REGULAR_B64)),
    ))
    pdfmetrics.registerFont(TTFont(
        "DejaVuSans-Bold", io.BytesIO(base64.b64decode(DEJAVU_SANS_BOLD_B64)),
    ))
    FONT_NAME = "DejaVuSans"
    FONT_BOLD = "DejaVuSans-Bold"
except Exception:
    logger.warning("font_data.py не знайдено або пошкоджено — пробую резервні шрифти", exc_info=True)

    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    _FONT_CANDIDATES = [
        os.path.join(_BASE_DIR, "fonts", "DejaVuSans.ttf"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",  # macOS
        "C:\\Windows\\Fonts\\arial.ttf",  # Windows
    ]
    _FONT_BOLD_CANDIDATES = [
        os.path.join(_BASE_DIR, "fonts", "DejaVuSans-Bold.ttf"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
        "C:\\Windows\\Fonts\\arialbd.ttf",
    ]

    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            pdfmetrics.registerFont(TTFont("DejaVuSans", path))
            FONT_NAME = "DejaVuSans"
            break

    for path in _FONT_BOLD_CANDIDATES:
        if os.path.exists(path):
            pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", path))
            FONT_BOLD = "DejaVuSans-Bold"
            break

if FONT_NAME == "Helvetica":
    # Кирилиця не відобразиться коректно без вбудованого шрифту.
    import logging
    logging.warning(
        "Файл шрифту fonts/DejaVuSans.ttf не знайдено поруч зі скриптом — "
        "текст кирилицею в PDF може відображатись некоректно."
    )


def generate_act(order: dict, dents: list[dict], out_path: str) -> str:
    doc = SimpleDocTemplate(
        out_path, pagesize=A4,
        topMargin=15 * mm, bottomMargin=15 * mm,
        leftMargin=18 * mm, rightMargin=18 * mm,
    )
    styles = getSampleStyleSheet()
    normal = ParagraphStyle("normal", parent=styles["Normal"], fontName=FONT_NAME, fontSize=10, leading=14)
    title = ParagraphStyle("title", parent=styles["Title"], fontName=FONT_BOLD, fontSize=14, leading=18)
    bold = ParagraphStyle("bold", parent=normal, fontName=FONT_BOLD)

    story = []
    act_number = f"АКТ-{datetime.now().strftime('%Y%m%d')}-{order['id']:04d}"
    today = datetime.now().strftime("%d.%m.%Y")

    story.append(Paragraph(f"Акт виконаних робіт № {act_number} від {today} р.", title))
    story.append(Spacer(1, 8 * mm))

    exec_lines = [config.COMPANY_NAME]
    if config.COMPANY_TAX_ID:
        exec_lines.append(f"ІПН/ЄДРПОУ: {config.COMPANY_TAX_ID}")
    if config.COMPANY_ADDRESS:
        exec_lines.append(config.COMPANY_ADDRESS)
    if config.COMPANY_PHONE:
        exec_lines.append(f"тел. {config.COMPANY_PHONE}")

    story.append(Paragraph(f"<b>Виконавець:</b> {', '.join(exec_lines)}", normal))
    client_line = order["client_name"] or "—"
    if order["client_phone"]:
        client_line += f", тел. {order['client_phone']}"
    story.append(Paragraph(f"<b>Замовник:</b> {client_line}", normal))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph(f"<b>Марка:</b> {order['car_make'] or '—'}", normal))
    story.append(Paragraph(f"<b>Модель:</b> {order['car_model'] or '—'}", normal))
    story.append(Paragraph(f"<b>Держномер:</b> {order['car_plate'] or '—'}", normal))
    story.append(Spacer(1, 6 * mm))

    cell_style = ParagraphStyle("cell", parent=normal, fontSize=9, leading=11)
    header_style = ParagraphStyle("cellHeader", parent=cell_style, fontName=FONT_BOLD)

    data = [[
        Paragraph("№", header_style), Paragraph("Послуга", header_style),
        Paragraph("Розмір", header_style),
        Paragraph("К-сть", header_style), Paragraph("Од.", header_style),
        Paragraph("Ціна", header_style), Paragraph("Сума", header_style),
    ]]
    total = 0
    for i, d in enumerate(dents, start=1):
        elem_name = pricing.ELEMENTS[d["element"]][0]
        tech_name = pricing.TECHNOLOGY[d["technology"]][0]
        service_desc = f"Видалення вм'ятини {i} — {elem_name} ({tech_name})"
        width = d.get("width_cm") or 0
        length = d.get("length_cm") or 0
        size_text = f"{width:g}×{length:g} см" if (width or length) else "—"
        price = d["price"]
        total += price
        data.append([
            Paragraph(str(i), cell_style), Paragraph(service_desc, cell_style),
            Paragraph(size_text, cell_style),
            Paragraph("1", cell_style), Paragraph("шт", cell_style),
            Paragraph(f"{price} грн", cell_style), Paragraph(f"{price} грн", cell_style),
        ])

    table = Table(data, colWidths=[8 * mm, 60 * mm, 20 * mm, 11 * mm, 10 * mm, 20 * mm, 22 * mm])
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
        ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6e6e6")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(table)
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph(f"<b>Разом до сплати: {total} грн</b>", bold))
    story.append(Spacer(1, 10 * mm))

    story.append(Paragraph(
        "Вищезазначені послуги надані в повному обсязі та у встановлений строк. "
        "Замовник претензій щодо якості, строків і обсягу наданих послуг не має.",
        normal,
    ))
    story.append(Spacer(1, 14 * mm))

    sign_data = [["Виконавець: ____________________", "Замовник: ____________________"]]
    sign_table = Table(sign_data, colWidths=[85 * mm, 85 * mm])
    sign_table.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), FONT_NAME), ("FONTSIZE", (0, 0), (-1, -1), 10)]))
    story.append(sign_table)

    doc.build(story)
    return out_path
