"""Generate a social-media certificate PNG (1080×1920) using Pillow.

Layout strategy: pre-measure every element, then distribute the remaining
whitespace evenly as gaps so content fills the full canvas height.
"""
import io
import os
from PIL import Image, ImageDraw

SOCIAL_W = 1080
SOCIAL_H = 1920
BAR_H    = 90   # gold footer bar height (fixed)

POSITION_SOCIAL = {1: 'Winner', 2: 'Runner Up', 3: 'Second Runner Up'}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _hex_to_rgba(hex_colour, alpha=255):
    h = hex_colour.lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha)


def _block_h(draw, lines, font, line_gap):
    """Total pixel height for a list of text lines with internal gaps."""
    if not lines:
        return 0
    heights = [draw.textbbox((0, 0), l, font=font)[3] - draw.textbbox((0, 0), l, font=font)[1]
               for l in lines]
    return sum(heights) + line_gap * (len(lines) - 1)


def _draw_lines(draw, y, lines, font, fill, line_gap, canvas_w, shadow=True):
    """Draw centred multi-line text; return total height used."""
    total = 0
    for i, line in enumerate(lines):
        bb  = draw.textbbox((0, 0), line, font=font)
        tw  = bb[2] - bb[0]
        th  = bb[3] - bb[1]
        x   = (canvas_w - tw) // 2
        if shadow:
            draw.text((x + 3, y + 3), line, font=font, fill=(0, 0, 0, 130))
        draw.text((x, y), line, font=font, fill=fill)
        y     += th + (line_gap if i < len(lines) - 1 else 0)
        total += th + (line_gap if i < len(lines) - 1 else 0)
    return total


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


# ── Generator ────────────────────────────────────────────────────────────────

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
    Content is pre-measured and gaps distributed evenly to fill the canvas.
    """
    from app.pdf.fonts import resolve_pillow_font

    # ── Colours ───────────────────────────────────────────────────────────────
    col_pos    = _hex_to_rgba(pos_colour  or '#d4af37')
    col_name   = _hex_to_rgba(name_colour or '#ffffff')
    col_item   = _hex_to_rgba(item_colour or '#ffffff')
    col_evt    = _hex_to_rgba(evt_colour  or '#d4af37')
    col_silver = (210, 210, 210, 255)
    col_dark   = (26,  26,  46,  255)

    # ── Background ─────────────────────────────────────────────────────────
    if bg_image_path and os.path.exists(bg_image_path):
        bg = Image.open(bg_image_path).convert('RGBA')
        bg_r = bg.width / bg.height
        tr   = SOCIAL_W / SOCIAL_H
        if bg_r > tr:
            nw, nh = int(SOCIAL_H * bg_r), SOCIAL_H
        else:
            nw, nh = SOCIAL_W, int(SOCIAL_W / bg_r)
        bg   = bg.resize((nw, nh), Image.LANCZOS)
        bg   = bg.crop(((nw - SOCIAL_W) // 2, (nh - SOCIAL_H) // 2,
                        (nw - SOCIAL_W) // 2 + SOCIAL_W,
                        (nh - SOCIAL_H) // 2 + SOCIAL_H))
    else:
        bg = Image.new('RGBA', (SOCIAL_W, SOCIAL_H), col_dark)

    opa     = max(0, min(255, int(overlay_opacity or 170)))
    overlay = Image.new('RGBA', (SOCIAL_W, SOCIAL_H), (0, 0, 0, opa))
    canvas  = Image.alpha_composite(bg, overlay)
    draw    = ImageDraw.Draw(canvas)

    max_w = SOCIAL_W - 120

    # ── Load logo ─────────────────────────────────────────────────────────────
    logo_img = None
    if logo_path and os.path.exists(logo_path):
        try:
            logo_img = Image.open(logo_path).convert('RGBA')
            logo_img.thumbnail((700, 240), Image.LANCZOS)
        except Exception:
            pass

    # ── Fonts ─────────────────────────────────────────────────────────────────
    f_pos    = resolve_pillow_font(font_value, 96, bold=True)
    f_item   = resolve_pillow_font(font_value, 56)
    f_cat    = resolve_pillow_font(font_value, 38)
    f_label  = resolve_pillow_font(font_value, 40)
    f_name   = resolve_pillow_font(font_value, 82, bold=True)
    f_evt    = resolve_pillow_font(font_value, 46)
    f_footer = resolve_pillow_font(font_value, 34)

    # ── Pre-measure every block ───────────────────────────────────────────────
    # Use a tiny scratch image for measurement only
    _td = ImageDraw.Draw(Image.new('RGBA', (10, 10)))

    def th(text, font):
        bb = _td.textbbox((0, 0), text, font=font)
        return bb[3] - bb[1]

    position_label = POSITION_SOCIAL.get(position, f'Position {position}')
    item_lines     = _wrap(_td, item_name,        f_item, max_w)
    name_lines     = _wrap(_td, participant_name,  f_name, max_w)
    evt_lines      = _wrap(_td, f'at {event_name}', f_evt, max_w)

    DIVIDER_H  = 6    # thick gold divider
    THIN_DIV_H = 2    # thin mid divider

    h_logo   = logo_img.height if logo_img else 0
    h_div    = DIVIDER_H
    h_pos    = th(position_label, f_pos)
    h_item   = _block_h(_td, item_lines, f_item, 12)
    h_cat    = th(category, f_cat)
    h_thin   = THIN_DIV_H
    h_label  = th('This certifies that', f_label)
    h_name   = _block_h(_td, name_lines,  f_name, 16)
    h_evt    = _block_h(_td, evt_lines,   f_evt,  14)

    # Nine content blocks → 10 gaps (before first block + between each pair + after last)
    TOTAL_CONTENT = h_logo + h_div + h_pos + h_item + h_cat + h_thin + h_label + h_name + h_evt
    USABLE        = SOCIAL_H - BAR_H - TOTAL_CONTENT
    N_GAPS        = 10   # gap before logo + 8 between blocks + gap after last block
    gap           = max(20, USABLE // N_GAPS)

    # ── Draw ──────────────────────────────────────────────────────────────────
    y = gap   # first gap before logo

    # 1 · Logo
    if logo_img:
        lx = (SOCIAL_W - logo_img.width) // 2
        canvas.paste(logo_img, (lx, y), logo_img)
    y += h_logo + gap

    # 2 · Gold top divider
    draw.rectangle([(140, y), (940, y + DIVIDER_H)], fill=col_pos)
    y += DIVIDER_H + gap

    # 3 · Position label  ("Winner" / "Runner Up" / "Second Runner Up")
    _draw_lines(draw, y, [position_label], f_pos, col_pos, 0, SOCIAL_W)
    y += h_pos + gap

    # 4 · Item name (multi-line)
    _draw_lines(draw, y, item_lines, f_item, col_item, 12, SOCIAL_W)
    y += h_item + gap

    # 5 · Category
    _draw_lines(draw, y, [category], f_cat, col_silver, 0, SOCIAL_W, shadow=False)
    y += h_cat + gap

    # 6 · Thin mid-divider
    draw.rectangle([(300, y), (780, y + THIN_DIV_H)], fill=(255, 255, 255, 70))
    y += THIN_DIV_H + gap

    # 7 · "This certifies that"
    _draw_lines(draw, y, ['This certifies that'], f_label, col_silver, 0, SOCIAL_W, shadow=False)
    y += h_label + gap

    # 8 · Participant name (multi-line)
    _draw_lines(draw, y, name_lines, f_name, col_name, 16, SOCIAL_W)
    y += h_name + gap

    # 9 · "at [EventName]" (multi-line)
    _draw_lines(draw, y, evt_lines, f_evt, col_evt, 14, SOCIAL_W)

    # ── Footer bar (pinned to bottom) ─────────────────────────────────────────
    draw.rectangle([(0, SOCIAL_H - BAR_H), (SOCIAL_W, SOCIAL_H)], fill=col_pos)
    footer  = 'Leicester Kerala Community'
    fb      = draw.textbbox((0, 0), footer, font=f_footer)
    fw, fh  = fb[2] - fb[0], fb[3] - fb[1]
    draw.text(((SOCIAL_W - fw) // 2, SOCIAL_H - BAR_H + (BAR_H - fh) // 2),
              footer, font=f_footer, fill=col_dark)

    # ── Convert and return ────────────────────────────────────────────────────
    buf = io.BytesIO()
    canvas.convert('RGB').save(buf, 'PNG', optimize=True)
    buf.seek(0)
    return buf.read()
