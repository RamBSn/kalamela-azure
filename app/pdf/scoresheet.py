"""
Judge Score Sheet PDF generator.
Produces one PDF with 3 copies (pages) per event — one per judge.
"""
import io
import os
from app.models import CompetitionItem, Entry, EventConfig

_LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'static', 'lkc-logo.jpeg')


def _entry_gender(entry):
    """Return 'Male', 'Female', or None (mixed/unknown group)."""
    if entry.participant:
        return entry.participant.gender
    if entry.group_entry:
        genders = {m.gender for m in entry.group_entry.members}
        if len(genders) == 1:
            return list(genders)[0]
    return None


def generate_scoresheet(item_id: int, gender: str = None, num_judges: int = 3) -> bytes:
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            SimpleDocTemplate, Table, TableStyle, Paragraph,
            Spacer, PageBreak,
        )
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
    except ImportError:
        raise RuntimeError('reportlab is required: pip install reportlab')

    item = CompetitionItem.query.get_or_404(item_id)
    criteria = item.criteria
    cfg = EventConfig.query.first()
    event_name = cfg.event_name if cfg else 'Kalamela'
    blank_rows = cfg.scoresheet_blank_rows if cfg else 3

    all_entries = Entry.query.filter_by(item_id=item_id).order_by(Entry.id).all()
    if gender:
        entries = [e for e in all_entries if _entry_gender(e) == gender]
    else:
        entries = all_entries

    page_w, page_h = landscape(A4)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'title', parent=styles['Normal'],
        fontSize=14, fontName='Helvetica-Bold', alignment=TA_CENTER,
    )
    sub_style = ParagraphStyle(
        'sub', parent=styles['Normal'],
        fontSize=10, fontName='Helvetica', alignment=TA_CENTER,
    )
    small_style = ParagraphStyle(
        'small', parent=styles['Normal'],
        fontSize=8, fontName='Helvetica',
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        rightMargin=10 * mm,
        leftMargin=10 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
    )

    story = []

    def build_copy(judge_num):
        # Header: logo (left) + title (centre) + mirror spacer (right) to keep text centred
        title_para = Paragraph(
            '<b>Association Kalamela Management System</b><br/>' + event_name,
            ParagraphStyle('hdr', parent=styles['Normal'], fontSize=12,
                           fontName='Helvetica-Bold', alignment=TA_CENTER, leading=16),
        )
        logo_col_w = 22 * mm
        if os.path.exists(_LOGO_PATH):
            from reportlab.platypus import Image as RLImage
            logo_cell = RLImage(_LOGO_PATH, width=16 * mm, height=16 * mm)
        else:
            logo_cell = ''
        hdr_table = Table(
            [[logo_cell, title_para, '']],
            colWidths=[logo_col_w, page_w - logo_col_w * 2 - 20 * mm, logo_col_w],
        )
        hdr_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN',  (0, 0), (-1, -1), 'CENTER'),
        ]))
        story.append(hdr_table)
        story.append(Spacer(1, 4 * mm))

        # Header row
        if gender:
            gender_display = gender
        elif item.gender_restriction:
            gender_display = f'{item.gender_restriction} Only'
        else:
            gender_display = 'Open (Male & Female)'
        header_data = [
            [
                Paragraph(f'<b>Event:</b> {item.name}', small_style),
                Paragraph(f'<b>Category:</b> {item.category}', small_style),
                Paragraph(f'<b>Gender:</b> {gender_display}', small_style),
                Paragraph(f'<b>Duration:</b> {item.max_duration_mins} min', small_style),
            ],
            [
                Paragraph(f'<b>Judge {judge_num} Name:</b> ___________________________', small_style),
                Paragraph('<b>Signature:</b> ___________________________', small_style),
                Paragraph(f'<b>Max marks per judge:</b> {item.max_marks_per_judge}', small_style),
                Paragraph(f'<b>Sheet:</b> Judge {judge_num} of {num_judges}', small_style),
            ],
        ]
        header_table = Table(header_data, colWidths=[page_w * 0.28, page_w * 0.25,
                                                      page_w * 0.25, page_w * 0.18])
        header_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e8e8e8')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 4 * mm))

        # Score table
        # Columns: Chest # | Name | [criteria cols] | TOTAL
        criteria_headers = [
            Paragraph(f'{c.name}\n(/{c.max_marks})', small_style)
            for c in criteria
        ]
        header_row = (
            [Paragraph('<b>Chest #</b>', small_style),
             Paragraph('<b>Name</b>', small_style)]
            + criteria_headers
            + [Paragraph(f'<b>TOTAL\n(/{item.max_marks_per_judge})</b>', small_style)]
        )

        table_data = [header_row]

        for e in entries:
            row = [
                Paragraph(str(e.chest_number), small_style),
                Paragraph(e.display_name, small_style),
            ]
            row += [''] * len(criteria)
            row += ['']
            table_data.append(row)

        # Blank rows for late entries
        for _ in range(blank_rows):
            blank_row = ['', ''] + [''] * len(criteria) + ['']
            table_data.append(blank_row)

        # Column widths
        usable_w = page_w - 20 * mm
        chest_w = 15 * mm
        name_w = 45 * mm
        total_w = 18 * mm
        criteria_w = (usable_w - chest_w - name_w - total_w) / max(len(criteria), 1)
        col_widths = ([chest_w, name_w]
                      + [criteria_w] * len(criteria)
                      + [total_w])

        score_table = Table(table_data, colWidths=col_widths,
                            rowHeights=[10 * mm] + [8 * mm] * (len(entries) + blank_rows))
        score_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e8e8e8')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (2, 1), (-1, -1), 'CENTER'),
            # Alternate row shading
            *[('BACKGROUND', (0, i), (-1, i), colors.HexColor('#f9f9f9'))
              for i in range(2, len(entries) + blank_rows + 1, 2)],
            # Last column (TOTAL) highlight
            ('BACKGROUND', (-1, 1), (-1, -1), colors.HexColor('#fff9e6')),
            # Blank rows dashed style
            *[('BACKGROUND', (0, len(entries) + 1 + i), (-1, len(entries) + 1 + i),
               colors.HexColor('#f0f0f0'))
              for i in range(blank_rows)],
        ]))
        story.append(score_table)

    for judge_num in range(1, num_judges + 1):
        build_copy(judge_num)
        if judge_num < num_judges:
            story.append(PageBreak())

    doc.build(story)
    return buf.getvalue()
