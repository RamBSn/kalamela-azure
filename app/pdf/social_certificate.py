"""Generate a social-media certificate PNG (1080×1920) using Pillow."""
import io
import os
from PIL import Image, ImageDraw

SOCIAL_W = 1080
SOCIAL_H = 1920

POSITION_SOCIAL = {1: 'Winner', 2: 'Runner Up', 3: 'Second Runner Up'}


def _hex_to_rgba(hex_colour, alpha=255):
    """Convert '#rrggbb' → (r, g, b, a)."""
    h = hex_colour.lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (r, g, b, alpha)


def _draw_centred(draw, y, text, font, fill, canvas_w, shadow=True):
    """Draw text centred horizontally; return text height."""
    bbox = draw.textbbox((0, 0), text, font=font)
    tw   = bbox[2] - bbox[0]
    th   = bbox[3] - bbox[1]
    x    = (canvas_w - tw) // 2
    if shadow:
        draw.text((x + 3, y + 3), text, font=font, fill=(0, 0, 0, 130))
    draw.text((x, y), text, font=font, fill=fill)
    return th


def _wrap_text(draw, text, font, max_width):
    """Word-wrap text to fit within max_width; returns list of lines."""
    words   = text.split()
    lines   = []
    current = ''
    for word in words:
        test = (current + ' ' + word).strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [text]


def generate_social_certificate(
        event_name,
        participant_name,
        item_name,
        category,
        position,
        logo_path=None,
        bg_image_path=None,
        font_value=None,
        pos_colour='#d4af37',
        name_colour='#ffffff',
        item_colour='#ffffff',
        evt_colour='#d4af37',
        overlay_opacity=170,
):
    """
    Returns PNG bytes for a 1080×1920 social media certificate.
    position : int 1, 2, or 3
    font_value: TTF file path or built-in name (None = system default)
    """
    from app.pdf.fonts import resolve_pillow_font

    # ── Colours ───────────────────────────────────────────────────────────────
    col_pos    = _hex_to_rgba(pos_colour  or '#d4af37')
    col_name   = _hex_to_rgba(name_colour or '#ffffff')
    col_item   = _hex_to_rgba(item_colour or '#ffffff')
    col_evt    = _hex_to_rgba(evt_colour  or '#d4af37')
    col_silver = (210, 210, 210, 255)
    col_dark   = (26,  26,  46,  255)
    col_gold   = _hex_to_rgba(pos_colour or '#d4af37')  # reuse for decorative elements

    # ── Background ─────────────────────────────────────────────────────────
    if bg_image_path and os.path.exists(bg_image_path):
        bg = Image.open(bg_image_path).convert('RGBA')
        bg_ratio     = bg.width / bg.height
        target_ratio = SOCIAL_W / SOCIAL_H
        if bg_ratio > target_ratio:
            new_h = SOCIAL_H
            new_w = int(SOCIAL_H * bg_ratio)
        else:
            new_w = SOCIAL_W
            new_h = int(SOCIAL_W / bg_ratio)
        bg   = bg.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - SOCIAL_W) // 2
        top  = (new_h - SOCIAL_H) // 2
        bg   = bg.crop((left, top, left + SOCIAL_W, top + SOCIAL_H))
    else:
        bg = Image.new('RGBA', (SOCIAL_W, SOCIAL_H), col_dark)

    # Dark overlay for readability
    opa     = max(0, min(255, int(overlay_opacity or 170)))
    overlay = Image.new('RGBA', (SOCIAL_W, SOCIAL_H), (0, 0, 0, opa))
    canvas  = Image.alpha_composite(bg, overlay)
    draw    = ImageDraw.Draw(canvas)

    max_w = SOCIAL_W - 120
    y     = 100

    # ── LKC Logo ────────────────────────────────────────────────────────────
    if logo_path and os.path.exists(logo_path):
        try:
            logo = Image.open(logo_path).convert('RGBA')
            logo.thumbnail((600, 220), Image.LANCZOS)
            lx = (SOCIAL_W - logo.width) // 2
            canvas.paste(logo, (lx, y), logo)
            y += logo.height + 70
        except Exception:
            y += 120
    else:
        y += 80

    # ── Gold top divider ────────────────────────────────────────────────────
    draw.rectangle([(160, y), (920, y + 5)], fill=col_gold)
    y += 55

    # ── Position label ──────────────────────────────────────────────────────
    position_label = POSITION_SOCIAL.get(position, f'Position {position}')
    f_pos = resolve_pillow_font(font_value, 96, bold=True)
    h = _draw_centred(draw, y, position_label, f_pos, col_pos, SOCIAL_W)
    y += h + 55

    # ── Item name ───────────────────────────────────────────────────────────
    f_item = resolve_pillow_font(font_value, 56)
    for line in _wrap_text(draw, item_name, f_item, max_w):
        h = _draw_centred(draw, y, line, f_item, col_item, SOCIAL_W)
        y += h + 12
    y += 10

    # Category sub-line
    f_cat = resolve_pillow_font(font_value, 40)
    h = _draw_centred(draw, y, category, f_cat, col_silver, SOCIAL_W, shadow=False)
    y += h + 80

    # ── Divider ─────────────────────────────────────────────────────────────
    draw.rectangle([(280, y), (800, y + 2)], fill=(255, 255, 255, 80))
    y += 50

    # ── "This certifies that" ───────────────────────────────────────────────
    f_label = resolve_pillow_font(font_value, 42)
    h = _draw_centred(draw, y, 'This certifies that', f_label, col_silver, SOCIAL_W, shadow=False)
    y += h + 40

    # ── Participant Name ─────────────────────────────────────────────────────
    f_name = resolve_pillow_font(font_value, 82, bold=True)
    for line in _wrap_text(draw, participant_name, f_name, max_w):
        h = _draw_centred(draw, y, line, f_name, col_name, SOCIAL_W)
        y += h + 16
    y += 60

    # ── "at [EventName]" ────────────────────────────────────────────────────
    f_evt = resolve_pillow_font(font_value, 46)
    for line in _wrap_text(draw, f'at {event_name}', f_evt, max_w):
        h = _draw_centred(draw, y, line, f_evt, col_evt, SOCIAL_W)
        y += h + 14

    # ── Bottom bar ───────────────────────────────────────────────────────────
    bar_h = 90
    draw.rectangle([(0, SOCIAL_H - bar_h), (SOCIAL_W, SOCIAL_H)], fill=col_gold)
    f_footer  = resolve_pillow_font(font_value, 34)
    footer    = 'Leicester Kerala Community'
    ft_bbox   = draw.textbbox((0, 0), footer, font=f_footer)
    ft_h      = ft_bbox[3] - ft_bbox[1]
    ft_w      = ft_bbox[2] - ft_bbox[0]
    draw.text(((SOCIAL_W - ft_w) // 2, SOCIAL_H - bar_h + (bar_h - ft_h) // 2),
              footer, font=f_footer, fill=col_dark)

    # ── Convert and return ───────────────────────────────────────────────────
    final = canvas.convert('RGB')
    buf   = io.BytesIO()
    final.save(buf, 'PNG', optimize=True)
    buf.seek(0)
    return buf.read()
