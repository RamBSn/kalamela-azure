"""Generate a social-media certificate PNG (1080×1920) using Pillow.

Stamps three text lines (Name, Position, Item · Category) at configurable
% positions over a background image.
"""
import io
import os
from PIL import Image, ImageDraw

SOCIAL_W = 1080
SOCIAL_H = 1920

POSITION_LABELS = {1: 'First Prize', 2: 'Second Prize', 3: 'Third Prize'}


def _hex_to_rgba(hex_colour, alpha=255):
    h = hex_colour.lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha)


def _wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ''
    for w in words:
        test = (cur + ' ' + w).strip()
        if draw.textbbox((0, 0), test, font=font)[2] <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [text]


def _draw_centred(draw, y_centre, lines, font, fill, line_gap=16, shadow=True):
    """Draw lines centred horizontally, vertically centred around y_centre."""
    heights = []
    for line in lines:
        bb = draw.textbbox((0, 0), line, font=font)
        heights.append(bb[3] - bb[1])
    total_h = sum(heights) + line_gap * (len(lines) - 1)
    y = y_centre - total_h // 2
    for i, (line, h) in enumerate(zip(lines, heights)):
        bb = draw.textbbox((0, 0), line, font=font)
        tw = bb[2] - bb[0]
        x  = (SOCIAL_W - tw) // 2
        if shadow:
            draw.text((x + 3, y + 3), line, font=font, fill=(0, 0, 0, 140))
        draw.text((x, y), line, font=font, fill=fill)
        y += h + (line_gap if i < len(lines) - 1 else 0)


def generate_social_certificate(
    participant_name,
    item_name,
    category,
    position,
    bg_image_path=None,
    pos_colour='#d4af37',
    name_colour='#ffffff',
    item_colour='#ffffff',
    name_y_pct=45.0,
    pos_y_pct=55.0,
    item_y_pct=65.0,
    # Legacy / unused params kept so existing callers don't break
    event_name=None,
    logo_path=None,
    font_value=None,
    evt_colour=None,
    overlay_opacity=None,
    footer_text=None,
    show_footer=None,
):
    """Returns PNG bytes for a 1080×1920 social media certificate."""
    from app.pdf.fonts import resolve_pillow_font

    # ── Background ────────────────────────────────────────────────────────────
    col_dark = (26, 26, 46, 255)
    if bg_image_path and os.path.exists(bg_image_path):
        bg   = Image.open(bg_image_path).convert('RGBA')
        bg_r = bg.width / bg.height
        tr   = SOCIAL_W / SOCIAL_H
        if bg_r > tr:
            nw, nh = int(SOCIAL_H * bg_r), SOCIAL_H
        else:
            nw, nh = SOCIAL_W, int(SOCIAL_W / bg_r)
        bg = bg.resize((nw, nh), Image.LANCZOS)
        bg = bg.crop(((nw - SOCIAL_W) // 2, (nh - SOCIAL_H) // 2,
                      (nw - SOCIAL_W) // 2 + SOCIAL_W,
                      (nh - SOCIAL_H) // 2 + SOCIAL_H))
    else:
        bg = Image.new('RGBA', (SOCIAL_W, SOCIAL_H), col_dark)

    canvas = bg.copy()
    draw   = ImageDraw.Draw(canvas)
    max_w  = SOCIAL_W - 120

    # ── Fonts ─────────────────────────────────────────────────────────────────
    f_name = resolve_pillow_font(font_value, 90, bold=True)
    f_pos  = resolve_pillow_font(font_value, 80, bold=True)
    f_item = resolve_pillow_font(font_value, 60, bold=False)

    # ── Text content ──────────────────────────────────────────────────────────
    position_label = POSITION_LABELS.get(position, str(position))
    item_text      = f'{item_name}  ·  {category}'

    name_lines = _wrap(draw, participant_name, f_name, max_w)
    pos_lines  = _wrap(draw, position_label,   f_pos,  max_w)
    item_lines = _wrap(draw, item_text,        f_item, max_w)

    # ── Draw at configured % positions ───────────────────────────────────────
    _draw_centred(draw, int(SOCIAL_H * name_y_pct / 100),
                  name_lines, f_name, _hex_to_rgba(name_colour or '#ffffff'))
    _draw_centred(draw, int(SOCIAL_H * pos_y_pct  / 100),
                  pos_lines,  f_pos,  _hex_to_rgba(pos_colour  or '#d4af37'))
    _draw_centred(draw, int(SOCIAL_H * item_y_pct / 100),
                  item_lines, f_item, _hex_to_rgba(item_colour or '#ffffff'))

    # ── Output ────────────────────────────────────────────────────────────────
    buf = io.BytesIO()
    canvas.convert('RGB').save(buf, 'PNG', optimize=True)
    buf.seek(0)
    return buf.read()
