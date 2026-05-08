"""
Font discovery for certificate generators.
Scans common system TTF directories and returns font choices for form selects.
"""
import os

# ReportLab built-in fonts — no TTF file needed
BUILTIN_FONTS = [
    {'label': 'Helvetica (Built-in)',       'value': 'Helvetica',   'bold': 'Helvetica-Bold',  'builtin': True,  'css': 'Helvetica, Arial, sans-serif'},
    {'label': 'Times New Roman (Built-in)', 'value': 'Times-Roman', 'bold': 'Times-Bold',       'builtin': True,  'css': '"Times New Roman", Times, serif'},
    {'label': 'Courier (Built-in)',          'value': 'Courier',     'bold': 'Courier-Bold',     'builtin': True,  'css': '"Courier New", Courier, monospace'},
]

_SCAN_DIRS = [
    '/System/Library/Fonts/Supplemental',   # macOS system fonts
    '/Library/Fonts',                        # macOS user fonts
    '/usr/share/fonts/truetype/dejavu',
    '/usr/share/fonts/truetype/liberation',
    '/usr/share/fonts/truetype/ubuntu',
    '/usr/share/fonts/truetype/freefont',
]

# Keywords in filename stem that indicate bold/italic/other weights — skip these
_WEIGHT_KEYWORDS = {
    'bold', 'italic', 'oblique', 'light', 'thin', 'medium', 'black',
    'heavy', 'condensed', 'narrow', 'semibold', 'demi', 'extrabold',
    'ultrabold', 'hairline',
}

# Filename prefixes we don't want (script-specific/symbol fonts)
_SKIP_PREFIXES = (
    'Noto', 'NISC', 'KefaIII', 'Diwan', 'Farisi', 'Gurmukhi',
    'Khmer', 'Kokonor', 'Plantagenet', 'PartyLET', 'Mishafi',
    'AppleMyungjo', 'AppleGothic', 'Ayuthaya', 'Sathu', 'Silom',
    'Krungthep', 'Lao ', 'AppleMyungjo',
)

# Substrings in the filename that indicate symbol/ornament fonts
_SKIP_CONTAINS = ('dingbat', 'webding', 'wingding', 'symbol', 'ornament')


def _is_usable(filename):
    """Return True if this font file should appear in the picker."""
    stem = filename.rsplit('.', 1)[0]
    low  = stem.lower()

    # Skip by prefix
    for prefix in _SKIP_PREFIXES:
        if stem.startswith(prefix):
            return False

    # Skip symbol/ornament fonts
    if any(kw in low for kw in _SKIP_CONTAINS):
        return False

    # Skip weight variants (bold, italic, etc.)
    words = set(low.replace('-', ' ').replace('_', ' ').split())
    if words & _WEIGHT_KEYWORDS:
        return False

    return True


def _find_bold(directory, stem):
    """Try to locate a bold variant of a font file in the same directory."""
    for suffix in (' Bold', 'Bold', '-Bold', '_Bold', 'bd', 'b'):
        for ext in ('.ttf', '.TTF'):
            p = os.path.join(directory, stem + suffix + ext)
            if os.path.exists(p):
                return p
    return None


def _css_family(label):
    """Approximate CSS font-family for browser preview."""
    low = label.lower()
    if 'georgia'        in low: return 'Georgia, serif'
    if 'times'          in low: return '"Times New Roman", Times, serif'
    if 'arial'          in low: return 'Arial, sans-serif'
    if 'verdana'        in low: return 'Verdana, sans-serif'
    if 'tahoma'         in low: return 'Tahoma, sans-serif'
    if 'trebuchet'      in low: return '"Trebuchet MS", sans-serif'
    if 'impact'         in low: return 'Impact, sans-serif'
    if 'courier'        in low: return '"Courier New", monospace'
    if 'comic sans'     in low: return '"Comic Sans MS", cursive'
    if 'luminari'       in low: return 'Georgia, serif'
    if 'caslon'         in low: return '"Big Caslon", Georgia, serif'
    if 'brush script'   in low: return '"Brush Script MT", cursive'
    if 'chancery'       in low: return '"Apple Chancery", cursive'
    if 'zapfino'        in low: return 'Zapfino, cursive'
    if 'herculanum'     in low: return 'Impact, fantasy'
    if 'chalkduster'    in low: return 'cursive'
    if 'trattatello'    in low: return 'cursive'
    if 'andale'         in low: return '"Andale Mono", monospace'
    if 'microsoft sans' in low: return '"Microsoft Sans Serif", sans-serif'
    if 'skia'           in low: return 'sans-serif'
    if 'stix'           in low: return '"STIX Two Text", serif'
    return 'sans-serif'


def scan_system_fonts():
    """Return list of font dicts for TTF fonts found on the system."""
    seen    = set()
    results = []
    for d in _SCAN_DIRS:
        if not os.path.isdir(d):
            continue
        try:
            files = sorted(os.listdir(d))
        except OSError:
            continue
        for fn in files:
            if not fn.lower().endswith('.ttf'):
                continue
            if not _is_usable(fn):
                continue
            path = os.path.join(d, fn)
            if path in seen:
                continue
            seen.add(path)
            stem    = fn.rsplit('.', 1)[0]
            bold    = _find_bold(d, stem)
            display = stem.replace('-', ' ').replace('_', ' ')
            results.append({
                'label':   display,
                'value':   path,
                'bold':    bold,
                'builtin': False,
                'css':     _css_family(display),
            })
    return results


def get_font_choices():
    """All fonts for a form <select>: built-ins first, then system TTFs."""
    return BUILTIN_FONTS + scan_system_fonts()


def resolve_pdf_fonts(cert_font):
    """
    Given cert_font (built-in name or TTF path), return
    (base_font_name, bold_font_name) ready for ReportLab's setFont().
    Registers the TTF with ReportLab if a file path is supplied.
    """
    if cert_font and cert_font.startswith('/') and os.path.exists(cert_font):
        d    = os.path.dirname(cert_font)
        stem = os.path.basename(cert_font).rsplit('.', 1)[0]
        bold_path = _find_bold(d, stem) or cert_font
        try:
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            pdfmetrics.registerFont(TTFont('CertFont',      cert_font))
            pdfmetrics.registerFont(TTFont('CertFont-Bold', bold_path))
            return 'CertFont', 'CertFont-Bold'
        except Exception:
            pass   # fall through to built-in

    # Built-in ReportLab fonts
    name = (cert_font or 'Times-Roman')
    if 'Helvetica' in name:
        return 'Helvetica',   'Helvetica-Bold'
    if 'Courier' in name:
        return 'Courier',     'Courier-Bold'
    return 'Times-Roman', 'Times-Bold'


def resolve_pillow_font(font_value, size, bold=False):
    """
    Return an ImageFont for Pillow. font_value is either a TTF path or
    a built-in name (Helvetica / Times-Roman / Courier).
    Falls back through system paths then PIL default.
    """
    from PIL import ImageFont

    # If it's a concrete TTF path
    if font_value and font_value.startswith('/') and os.path.exists(font_value):
        # For bold, try to find bold variant
        if bold:
            d    = os.path.dirname(font_value)
            stem = os.path.basename(font_value).rsplit('.', 1)[0]
            bold_path = _find_bold(d, stem)
            if bold_path:
                try:
                    return ImageFont.truetype(bold_path, size)
                except Exception:
                    pass
        try:
            return ImageFont.truetype(font_value, size)
        except Exception:
            pass

    # Fall back to common system TTF locations
    bold_candidates = [
        '/System/Library/Fonts/Supplemental/Arial Bold.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
    ]
    regular_candidates = [
        '/System/Library/Fonts/Supplemental/Arial.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
    ]
    for path in (bold_candidates if bold else regular_candidates):
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue

    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()
