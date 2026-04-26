"""
Planning Schedule PDF generator.
Produces a clean A4 schedule per stage, suitable for distributing to participants.
"""
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, HRFlowable, KeepTogether,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# Category colour map (light backgrounds for badges in the PDF)
CATEGORY_COLOURS = {
    'Kids':        colors.HexColor('#d1fae5'),  # green tint
    'Sub-Junior':  colors.HexColor('#dbeafe'),  # blue tint
    'Junior':      colors.HexColor('#ede9fe'),  # purple tint
    'Senior':      colors.HexColor('#fef3c7'),  # amber tint
    'Super Senior':colors.HexColor('#fee2e2'),  # red tint
    'Common':      colors.HexColor('#f3f4f6'),  # grey tint
}


def _entry_label(entry) -> str:
    """Short label: '#101 Alice' or '#G201 Group Name'."""
    return f'#{entry.chest_number} {entry.display_name}'


def generate_plan_pdf(stage, plan_data: list, event_name: str, event_date: str) -> bytes:
    """
    stage     : Stage model instance
    plan_data : list of dicts from planning._plan_data()
    Returns bytes of an A4 PDF planning schedule.
    """
    buf = io.BytesIO()
    page_w, page_h = A4
    margin = 15 * mm

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=margin, rightMargin=margin,
        topMargin=margin, bottomMargin=margin,
        title=f'{event_name} — {stage.name} Planning Schedule',
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'PlanTitle', parent=styles['Normal'],
        fontSize=16, fontName='Helvetica-Bold',
        alignment=TA_CENTER, spaceAfter=2 * mm,
    )
    sub_style = ParagraphStyle(
        'PlanSub', parent=styles['Normal'],
        fontSize=10, fontName='Helvetica',
        alignment=TA_CENTER, textColor=colors.HexColor('#555555'),
        spaceAfter=1 * mm,
    )
    stage_style = ParagraphStyle(
        'PlanStage', parent=styles['Normal'],
        fontSize=13, fontName='Helvetica-Bold',
        alignment=TA_CENTER, spaceAfter=4 * mm,
        textColor=colors.HexColor('#1a1a2e'),
    )
    cat_style = ParagraphStyle(
        'CatHeader', parent=styles['Normal'],
        fontSize=9, fontName='Helvetica-Bold',
        alignment=TA_LEFT, textColor=colors.HexColor('#374151'),
    )
    cell_style = ParagraphStyle(
        'Cell', parent=styles['Normal'],
        fontSize=9, fontName='Helvetica',
    )
    cell_bold = ParagraphStyle(
        'CellBold', parent=styles['Normal'],
        fontSize=9, fontName='Helvetica-Bold',
    )
    participant_style = ParagraphStyle(
        'Participant', parent=styles['Normal'],
        fontSize=8, fontName='Helvetica',
        textColor=colors.HexColor('#374151'),
        leading=11,
    )
    footer_style = ParagraphStyle(
        'Footer', parent=styles['Normal'],
        fontSize=7, fontName='Helvetica',
        alignment=TA_CENTER, textColor=colors.grey,
    )

    usable_w = page_w - 2 * margin

    story = []

    # ── Header ────────────────────────────────────────────────────────────────
    story.append(Paragraph(event_name, title_style))
    if event_date:
        story.append(Paragraph(event_date, sub_style))
    story.append(Paragraph(f'Performance Schedule — {stage.name}', stage_style))
    story.append(HRFlowable(width=usable_w, thickness=2,
                             color=colors.HexColor('#1a1a2e'), spaceAfter=5 * mm))

    if not plan_data:
        story.append(Paragraph('No events assigned to this stage.', cell_style))
        doc.build(story)
        return buf.getvalue()

    # ── Schedule table ─────────────────────────────────────────────────────────
    # Column widths: #  | Event name | Category | Participants
    col_w = [10*mm, 65*mm, 28*mm, usable_w - 10*mm - 65*mm - 28*mm]

    header_row = [
        Paragraph('<b>#</b>', cell_bold),
        Paragraph('<b>Event</b>', cell_bold),
        Paragraph('<b>Category</b>', cell_bold),
        Paragraph('<b>Participants (Chest #)</b>', cell_bold),
    ]
    table_data = [header_row]
    row_styles = []

    prev_category = None
    for row_idx, row in enumerate(plan_data, start=1):  # row_idx 1-based (0 = header)
        item    = row['item']
        entries = row['entries']
        seq     = row['seq']

        # Category header row when category changes
        if item.category != prev_category:
            cat_colour = CATEGORY_COLOURS.get(item.category, colors.HexColor('#f3f4f6'))
            cat_row = [
                Paragraph('', cat_style),
                Paragraph(item.category.upper(), cat_style),
                Paragraph('', cat_style),
                Paragraph('', cat_style),
            ]
            table_data.append(cat_row)
            row_styles.append(
                ('BACKGROUND', (0, len(table_data) - 1), (-1, len(table_data) - 1), cat_colour)
            )
            row_styles.append(
                ('SPAN', (1, len(table_data) - 1), (-1, len(table_data) - 1))
            )
            prev_category = item.category

        # Build participants cell — show on separate lines
        if entries:
            participant_lines = '<br/>'.join(_entry_label(e) for e in entries)
            count = f'({len(entries)})'
        else:
            participant_lines = '<i>No participants assigned</i>'
            count = ''

        data_row = [
            Paragraph(str(seq), cell_style),
            Paragraph(f'<b>{item.name}</b>', cell_bold),
            Paragraph(item.category, cell_style),
            Paragraph(participant_lines, participant_style),
        ]
        table_data.append(data_row)

        # Alternate row shading (skip category header rows)
        if seq % 2 == 0:
            row_styles.append(
                ('BACKGROUND', (0, len(table_data) - 1), (-1, len(table_data) - 1),
                 colors.HexColor('#f9fafb'))
            )

    table = Table(table_data, colWidths=col_w, repeatRows=1)
    base_style = [
        ('GRID',       (0, 0), (-1, -1), 0.4, colors.HexColor('#d1d5db')),
        ('BACKGROUND', (0, 0), (-1, 0),  colors.HexColor('#1a1a2e')),
        ('TEXTCOLOR',  (0, 0), (-1, 0),  colors.white),
        ('VALIGN',     (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING',   (0, 0), (-1, -1), 3),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 3),
        ('ALIGN',      (0, 0), (0, -1),  'CENTER'),   # # column centred
    ]
    table.setStyle(TableStyle(base_style + row_styles))
    story.append(table)

    # ── Summary ────────────────────────────────────────────────────────────────
    total_entries = sum(len(r['entries']) for r in plan_data)
    story.append(Spacer(1, 4 * mm))
    story.append(HRFlowable(width=usable_w, thickness=0.5,
                             color=colors.HexColor('#d1d5db'), spaceAfter=2 * mm))
    story.append(Paragraph(
        f'Total events: {len(plan_data)}  &nbsp;|&nbsp;  Total participants: {total_entries}',
        footer_style,
    ))
    from datetime import datetime
    story.append(Paragraph(
        f'Printed {datetime.now().strftime("%d %b %Y %H:%M")}',
        footer_style,
    ))

    doc.build(story)
    return buf.getvalue()
