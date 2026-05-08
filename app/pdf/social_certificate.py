"""Generate a social-media certificate PNG (1080×1920) using Pillow."""
import io
import os
from PIL import Image, ImageDraw, ImageFont

SOCIAL_W = 1080
SOCIAL_H = 1920

POSITION_SOCIAL = {1: 'Winner', 2: 'Runner Up', 3: 'Second Runner Up'}

_BOLD_FONT_PATHS = [
    '/Library/Fonts/Arial Bold.ttf',
    '/System/Library/Fonts/Supplemental/Arial Bold.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
    '/usr/share/fonts/truetype/freefont/FreeSansBold.ttf',
    '/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf',
]
_REGULAR_FONT_PATHS = [
    '/Library/Fonts/Arial.ttf',
    '/System/Library/Fonts/Supplemental/Arial.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
    '/usr/share/fonts/truetype/freefont/FreeSans.ttf',
    '/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf',
]


def _find_font(size, bold=False):
    paths = _BOLD_FONT_PATHS if bold else _REGULAR_FONT_PATHS
    for path in paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    # Pillow 10.x load_default accepts a size parameter
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _text_width(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def _text_height(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[3] - bbox[1]


def _draw_centred(draw, y, text, font, fill, canvas_w, shadow=True):
    """Draw text horizontally centred; return text height."""
    tw = _text_width(draw, text, font)
    x = (canvas_w - tw) // 2
    if shadow:
        draw.text((x + 3, y + 3), text, font=font, fill=(0, 0, 0, 140))
    draw.text((x, y), text, font=font, fill=fill)
    return _text_height(draw, text, font)


def _wrap_text(draw, text, font, max_width):
    """Simple word-wrap; returns list of lines."""
    words = text.split()
    lines = []
    current = ''
    for word in words:
        test = (current + ' ' + word).strip()
        if _text_width(draw, test, font) <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def generate_social_certificate(
        event_name, participant_name, item_name, category,
        position, logo_path=None, bg_image_path=None):
    """
    Returns PNG bytes for a 1080×1920 social media certificate.
    position: int 1, 2, or 3
    """
    # ── Background ─────────────────────────────────────────────────────────
    if bg_image_path and os.path.exists(bg_image_path):
        bg = Image.open(bg_image_path).convert('RGBA')
        bg_ratio = bg.width / bg.height
        target_ratio = SOCIAL_W / SOCIAL_H
        if bg_ratio > target_ratio:
            new_h = SOCIAL_H
            new_w = int(SOCIAL_H * bg_ratio)
        else:
            new_w = SOCIAL_W
            new_h = int(SOCIAL_W / bg_ratio)
        bg = bg.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - SOCIAL_W) // 2
        top = (new_h - SOCIAL_H) // 2
        bg = bg.crop((left, top, left + SOCIAL_W, top + SOCIAL_H))
    else:
        bg = Image.new('RGBA', (SOCIAL_W, SOCIAL_H), (26, 26, 46, 255))

    # Dark overlay for readability
    overlay = Image.new('RGBA', (SOCIAL_W, SOCIAL_H), (0, 0, 0, 170))
    canvas = Image.alpha_composite(bg, overlay)
    draw = ImageDraw.Draw(canvas)

    gold    = (212, 175, 55, 255)
    white   = (255, 255, 255, 255)
    silver  = (210, 210, 210, 255)
    dark_bg = (26, 26, 46, 255)

    y = 100

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
    draw.rectangle([(160, y), (920, y + 5)], fill=gold)
    y += 55

    # ── Position label ──────────────────────────────────────────────────────
    position_label = POSITION_SOCIAL.get(position, f'Position {position}')
    font_pos = _find_font(96, bold=True)
    h = _draw_centred(draw, y, position_label, font_pos, gold, SOCIAL_W)
    y += h + 55

    # ── Item name ───────────────────────────────────────────────────────────
    font_item = _find_font(56)
    max_w = SOCIAL_W - 120
    lines = _wrap_text(draw, item_name, font_item, max_w)
    for line in lines:
        h = _draw_centred(draw, y, line, font_item, white, SOCIAL_W)
        y += h + 12
    y += 10

    # Category badge
    font_cat = _find_font(40)
    h = _draw_centred(draw, y, category, font_cat, silver, SOCIAL_W, shadow=False)
    y += h + 80

    # ── Divider ─────────────────────────────────────────────────────────────
    draw.rectangle([(280, y), (800, y + 2)], fill=(255, 255, 255, 80))
    y += 50

    # ── "This certifies that" ───────────────────────────────────────────────
    font_label = _find_font(42)
    h = _draw_centred(draw, y, 'This certifies that', font_label, silver, SOCIAL_W, shadow=False)
    y += h + 40

    # ── Participant Name ─────────────────────────────────────────────────────
    font_name = _find_font(82, bold=True)
    name_lines = _wrap_text(draw, participant_name, font_name, max_w)
    for line in name_lines:
        h = _draw_centred(draw, y, line, font_name, white, SOCIAL_W)
        y += h + 16
    y += 60

    # ── "at [EventName]" ────────────────────────────────────────────────────
    font_event = _find_font(46)
    at_lines = _wrap_text(draw, f'at {event_name}', font_event, max_w)
    for line in at_lines:
        h = _draw_centred(draw, y, line, font_event, gold, SOCIAL_W)
        y += h + 14
    y += 30

    # ── Bottom bar ───────────────────────────────────────────────────────────
    bar_h = 90
    draw.rectangle([(0, SOCIAL_H - bar_h), (SOCIAL_W, SOCIAL_H)], fill=gold)
    font_footer = _find_font(34)
    footer_text = 'Leicester Kerala Community'
    th = _text_height(draw, footer_text, font_footer)
    _draw_centred(draw, SOCIAL_H - bar_h + (bar_h - th) // 2,
                  footer_text, font_footer, dark_bg, SOCIAL_W, shadow=False)

    # ── Convert and return ───────────────────────────────────────────────────
    final = canvas.convert('RGB')
    buf = io.BytesIO()
    final.save(buf, 'PNG', optimize=True)
    buf.seek(0)
    return buf.read()
