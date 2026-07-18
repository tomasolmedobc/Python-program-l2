"""
L2 Crest Maker  ·  v2.0
Creador de Crests para Lineage 2
  • Clan Crest   : 16x12 px, 256 colores BMP  (zona derecha)
  • Ally Crest   :  8x12 px, 256 colores BMP  (zona izquierda)
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
from PIL import Image, ImageTk, ImageDraw, ImageFont, ImageEnhance, ImageFilter
import os, sys, json, ctypes, io, winreg, colorsys, datetime
from functools import lru_cache

# Cuando este archivo se ejecuta directamente (python L2CrestMaker.py), Python
# lo registra en sys.modules como "__main__", no como "L2CrestMaker". Los
# módulos app_*.py hacen `import L2CrestMaker` para acceder a constantes que
# los tests parchean (PRESETS_FILE, _save_json, etc.) — sin este alias, ese
# import volvería a cargar y ejecutar este archivo desde cero como un segundo
# módulo distinto, rompiendo el ciclo de import circular a mitad de carga.
sys.modules.setdefault("L2CrestMaker", sys.modules[__name__])

try:
    from tkinterdnd2 import TkinterDnD as _TkDnD, DND_FILES as _DND_FILES
    _HAS_DND = True
except ImportError:
    _TkDnD = None
    _DND_FILES = None
    _HAS_DND = False

# ── Constantes ────────────────────────────────────────────────────────────────
CLAN_SIZE     = (16, 12)
ALLY_SIZE     = ( 8, 12)
COMBINED_W    = ALLY_SIZE[0] + CLAN_SIZE[0]   # 24 — canvas total ally+clan
PREVIEW_MULT  = 20
SOURCE_PREV_W = 480
SOURCE_PREV_H = 240
OUTPUT_DIR    = os.environ.get("L2CREST_OUTPUT_DIR", r"E:\L2CyA")
FONTS_DIR     = os.environ.get("L2CREST_FONTS_DIR", r"C:\Windows\Fonts")
SUPER_SAMPLE  = 16

# Empaquetado con PyInstaller: __file__ apunta a la carpeta temporal de
# extracción (_MEIPASS), que se borra al cerrar la app. Los datos del usuario
# (presets, sesión, overlays, plantillas) deben vivir junto al .exe real.
if getattr(sys, "frozen", False):
    _HERE = os.path.dirname(sys.executable)
else:
    _HERE = os.path.dirname(os.path.abspath(__file__))
RECENT_FILE  = os.path.join(_HERE, "l2crest_recent.json")
PRESETS_FILE = os.path.join(_HERE, "l2crest_presets.json")
SESSION_FILE = os.path.join(_HERE, "l2crest_session.json")
ERROR_LOG_FILE = os.path.join(_HERE, "l2crest_errors.log")
OVERLAYS_DIR  = os.environ.get("L2CREST_OVERLAYS_DIR",  os.path.join(_HERE, "overlays"))
TEMPLATES_DIR = os.environ.get("L2CREST_TEMPLATES_DIR", os.path.join(_HERE, "templates"))
MAX_RECENT   = 8
ZOOM_MULT    = 40   # factor zoom en popup de resultado
_split_ratio = 8 / 24  # Feature 8: draggable split ratio (ally fraction)

# ── Paleta de colores ─────────────────────────────────────────────────────────
BG0 = "#0d1117"   # fondo base
BG1 = "#161b22"   # fondo de secciones (cards)
BG2 = "#21262d"   # fondo de inputs / escalas
ACC = "#e6b84a"   # dorado (clan)
AC2 = "#58a6ff"   # azul (ally)
TXP = "#c9d1d9"   # texto principal
TXS = "#8b949e"   # texto secundario
GRN = "#3fb950"   # verde
RED = "#f85149"   # rojo

# ── Helpers del sistema ───────────────────────────────────────────────────────

def _get_system_fonts() -> list:
    user_fonts_dir = os.path.join(
        os.environ.get("LOCALAPPDATA", ""), r"Microsoft\Windows\Fonts"
    )
    search_dirs = [FONTS_DIR, user_fonts_dir]
    seen = {}
    reg_key = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            key = winreg.OpenKey(hive, reg_key)
            i = 0
            while True:
                try:
                    name, path, _ = winreg.EnumValue(key, i)
                    name = (name.replace(" (TrueType)", "")
                                .replace(" (OpenType)", "")
                                .replace(" (All res)", "")
                                .strip())
                    if not os.path.isabs(path):
                        for d in search_dirs:
                            candidate = os.path.join(d, path)
                            if os.path.isfile(candidate):
                                path = candidate
                                break
                    if os.path.isfile(path):
                        seen[name] = path
                    i += 1
                except OSError:
                    break
            winreg.CloseKey(key)
        except Exception:
            pass
    return sorted(seen.items(), key=lambda x: x[0].lower())


@lru_cache(maxsize=256)
def _font_from_path(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        if path:
            return ImageFont.truetype(path, size)
    except Exception:
        pass
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()


def _per_char_fonts(text: str, font_paths: list, size_pcts: list, y_offsets_pct: list,
                     base_size_pct: float, size_px, off_px, fallback_font):
    """Per-character (fonts, y_offsets_px) for `text` given optional per-char
    font paths/size%/y-offset% lists. Chars beyond the provided lists fall
    back to `fallback_font` at 0 offset. Returns (None, None) if font_paths
    is falsy. `size_px`/`off_px` convert a size%/offset% to pixels."""
    if not font_paths:
        return None, None
    fonts, y_offsets = [], []
    for j, p in enumerate(font_paths[:len(text)]):
        pct = size_pcts[j] if size_pcts and j < len(size_pcts) else base_size_pct
        fonts.append(_font_from_path(p, size_px(pct)))
        yo_pct = y_offsets_pct[j] if y_offsets_pct and j < len(y_offsets_pct) else 0
        y_offsets.append(off_px(yo_pct))
    while len(fonts) < len(text):
        fonts.append(fallback_font)
        y_offsets.append(0)
    return fonts, y_offsets


def _apply_italic(layer: Image.Image, shear_k: float = 0.30) -> Image.Image:
    w, h = layer.size
    matrix = (1, shear_k, -shear_k * h, 0, 1, 0)
    return layer.transform((w, h), Image.AFFINE, matrix, resample=Image.BICUBIC)


def _draw_chars(draw_obj, text: str, font, cx: int, cy: int,
                spacing_pct: int, fill: tuple, stroke_w: int = 0,
                fonts: list = None, y_offsets: list = None):
    if not text:
        return
    chars      = list(text)
    char_fonts = fonts if fonts and len(fonts) >= len(chars) else [font] * len(chars)
    boxes      = [draw_obj.textbbox((0, 0), c, font=f, stroke_width=stroke_w)
                  for c, f in zip(chars, char_fonts)]
    widths  = [b[2] - b[0] for b in boxes]
    heights = [b[3] - b[1] for b in boxes]
    avg_w   = sum(widths) / len(widths) if widths else 0
    gap     = int(avg_w * spacing_pct / 100)
    total_w = sum(widths) + gap * (len(chars) - 1)
    max_h   = max(heights) if heights else 0
    x = cx - total_w // 2
    y = cy - max_h  // 2
    for i, (c, f, w) in enumerate(zip(chars, char_fonts, widths)):
        yo = y_offsets[i] if y_offsets and i < len(y_offsets) else 0
        draw_obj.text((x, y + yo), c, font=f, fill=fill,
                      stroke_width=stroke_w, stroke_fill=fill)
        x += w + gap


def _hex_to_rgb(hex_color: str) -> tuple:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _make_gradient(w: int, h: int, color1: str, color2: str,
                   direction: str = "vertical") -> Image.Image:
    """Linear gradient image (RGB). color1 = top/left/center, color2 = bottom/right/edge."""
    r1, g1, b1 = _hex_to_rgb(color1)
    r2, g2, b2 = _hex_to_rgb(color2)
    pixels: list = []
    ww, hh = max(w - 1, 1), max(h - 1, 1)

    def _lerp(t):
        return (int(r1*(1-t)+r2*t), int(g1*(1-t)+g2*t), int(b1*(1-t)+b2*t))

    if direction == "horizontal":
        for _ in range(h):
            for x in range(w):
                pixels.append(_lerp(x / ww))
    elif direction == "diagonal ↘":   # top-left → bottom-right
        for y in range(h):
            for x in range(w):
                pixels.append(_lerp((x / ww + y / hh) / 2))
    elif direction == "diagonal ↗":   # bottom-left → top-right
        for y in range(h):
            for x in range(w):
                pixels.append(_lerp(((ww - x) / ww + y / hh) / 2))
    elif direction == "radial":            # color1 at center, color2 at corners
        cx, cy = ww / 2, hh / 2
        max_d = max(1.0, (cx**2 + cy**2) ** 0.5)
        for y in range(h):
            for x in range(w):
                t = min(1.0, ((x - cx)**2 + (y - cy)**2) ** 0.5 / max_d)
                pixels.append(_lerp(t))
    else:   # vertical (default)
        for y in range(h):
            t = y / hh
            pixels.extend([_lerp(t)] * w)
    img = Image.new("RGB", (w, h))
    img.putdata(pixels)
    return img


def _combined_base(src_w: int, src_h: int) -> tuple:
    """Crop fuente a ratio 24:12 (=2:1) centrado — base compartida ally+clan."""
    tr = COMBINED_W / ALLY_SIZE[1]   # 24/12 = 2.0
    sr = src_w / src_h
    if sr > tr:
        nw = src_h * tr
        ox = (src_w - nw) / 2
        return (ox, 0.0, ox + nw, float(src_h))
    elif sr < tr:
        nh = src_w / tr
        oy = (src_h - nh) / 2
        return (0.0, oy, float(src_w), oy + nh)
    return (0.0, 0.0, float(src_w), float(src_h))


def _crop_box(src_w: int, src_h: int, target_w: int, target_h: int,
              align: str = "center") -> tuple:
    if align in ("ally", "clan"):
        bx1, by1, bx2, by2 = _combined_base(src_w, src_h)
        bw = bx2 - bx1
        split = bx1 + bw * _split_ratio   # borde ally|clan (Feature 8: draggable)
        if align == "ally":
            return (bx1, by1, split, by2)
        else:
            return (split, by1, bx2, by2)
    tr = target_w / target_h
    sr = src_w / src_h
    if sr > tr:
        nw = src_h * tr
        if align == "left":
            ox = 0.0
        elif align == "right":
            ox = src_w - nw
        else:
            ox = (src_w - nw) / 2
        return (ox, 0.0, ox + nw, float(src_h))
    elif sr < tr:
        nh = src_w / tr
        oy = (src_h - nh) / 2
        return (0.0, oy, float(src_w), oy + nh)
    return (0.0, 0.0, float(src_w), float(src_h))


def _log_error(context: str, exc: Exception):
    """Best-effort trace of failures that would otherwise vanish silently.
    Never raises itself — a broken log is not worth crashing over."""
    try:
        with open(ERROR_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {context}: {exc}\n")
    except Exception:
        pass


def _load_json(path: str, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save_json(path: str, data) -> bool:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        _log_error(f"_save_json({path})", e)
        return False


def _copy_image_to_clipboard(img: Image.Image):
    output = io.BytesIO()
    img.convert("RGB").save(output, "BMP")
    data = output.getvalue()[14:]
    CF_DIB = 8
    GMEM_MOVEABLE = 0x0002
    hMem = ctypes.windll.kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
    pMem = ctypes.windll.kernel32.GlobalLock(hMem)
    ctypes.memmove(pMem, data, len(data))
    ctypes.windll.kernel32.GlobalUnlock(hMem)
    ctypes.windll.user32.OpenClipboard(None)
    ctypes.windll.user32.EmptyClipboard()
    ctypes.windll.user32.SetClipboardData(CF_DIB, hMem)
    ctypes.windll.user32.CloseClipboard()


# ── Conversión ────────────────────────────────────────────────────────────────

def _apply_hue_shift(img: Image.Image, hue_shift: int) -> Image.Image:
    """Rota el tono (hue) en -180..+180 grados. Blanco/negro/gris no cambian (S=0)."""
    if hue_shift == 0:
        return img
    hsv = img.convert("HSV")
    h, s, v = hsv.split()
    shift = round(hue_shift * 255 / 360) % 256
    h = h.point(lambda p: (p + shift) % 256)
    return Image.merge("HSV", (h, s, v)).convert("RGB")


def image_to_l2_bmp(src_path: str, dest_path, size: tuple,
                     align: str = "center",
                     texts: list = None,
                     text_color: str = "#ffffff",
                     font_path: str = None, text_spacing_pct: int = 0,
                     italic: bool = False,
                     brightness: float = 1.0, contrast: float = 1.0,
                     saturation: float = 1.0, sharpen: bool = False,
                     hue: int = 0,
                     rotation: int = 0, flip_h: bool = False, flip_v: bool = False,
                     shadow: bool = False, shadow_x: int = 1, shadow_y: int = 1,
                     shadow_color: str = "#000000",
                     dither: bool = True,
                     overlay_path: str = None,
                     text_outline: int = 2,
                     text_opacity: int = 100,
                     text_rotation: int = 0,
                     color_replacements: list = None,
                     text_gradient: bool = False,
                     gradient_color1: str = "#ffffff",
                     gradient_color2: str = "#000000",
                     gradient_dir: str = "vertical",
                     outline_color: str = None,
                     bold: bool = False,
                     char_font_paths: list = None,
                     char_size_pcts: list = None,
                     char_y_offsets_pct: list = None,
                     texts_are_crop_relative: bool = False) -> Image.Image:
    img = Image.open(src_path).convert("RGBA")

    # Compositar Fuente 2 (PNG overlay) sobre Fuente 1 antes de recortar
    if overlay_path and os.path.isfile(overlay_path):
        ov = Image.open(overlay_path).convert("RGBA")
        if ov.size != img.size:
            ov = ov.resize(img.size, Image.LANCZOS)
        img = Image.alpha_composite(img, ov)

    if rotation:
        img = img.rotate(-rotation, expand=True)
    if flip_h:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    if flip_v:
        img = img.transpose(Image.FLIP_TOP_BOTTOM)

    src_w, src_h = img.size

    x1, y1, x2, y2 = _crop_box(src_w, src_h, size[0], size[1], align)
    img = img.crop((int(x1), int(y1), int(x2), int(y2)))
    bg = Image.new("RGB", img.size, (0, 0, 0))
    bg.paste(img, mask=img.split()[3])

    if brightness != 1.0: bg = ImageEnhance.Brightness(bg).enhance(brightness)
    if contrast   != 1.0: bg = ImageEnhance.Contrast(bg).enhance(contrast)
    if saturation != 1.0: bg = ImageEnhance.Color(bg).enhance(saturation)
    if hue        != 0:   bg = _apply_hue_shift(bg, hue)
    if color_replacements:
        _arr = list(bg.getdata())
        _new = []
        for _px in _arr:
            _rp, _gp, _bp = _px[0], _px[1], _px[2]
            _ok = False
            for (_r1, _g1, _b1), (_nr, _ng, _nb), _tol in color_replacements:
                if abs(_rp-_r1) + abs(_gp-_g1) + abs(_bp-_b1) <= _tol * 3:
                    _new.append((_nr, _ng, _nb))
                    _ok = True
                    break
            if not _ok:
                _new.append((_rp, _gp, _bp))
        bg = Image.new("RGB", bg.size)
        bg.putdata(_new)

    img = bg.resize(size, Image.LANCZOS)
    if sharpen:
        img = img.filter(ImageFilter.UnsharpMask(radius=0.6, percent=180, threshold=1))

    active_texts = [t for t in (texts or []) if t[0]]
    if active_texts:
        sw = size[0] * SUPER_SAMPLE
        sh = size[1] * SUPER_SAMPLE
        text_layer = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
        td         = ImageDraw.Draw(text_layer)
        crop_w, crop_h = x2 - x1, y2 - y1
        r, g, b = _hex_to_rgb(text_color)
        if outline_color:
            cr, cg, cb = _hex_to_rgb(outline_color)
        else:
            cr, cg, cb = min(255, (255 - r) | 40), min(255, (255 - g) | 40), min(255, (255 - b) | 40)
        outline_step = text_outline

        # Bold: thicken strokes by drawing with a pixel-wide stroke in the
        # supersampled canvas; after LANCZOS downscale this gives a heavier weight.
        _bsw = max(1, SUPER_SAMPLE // 4) if bold else 0  # ≈4 px in 256-wide canvas

        # Pre-compute per-text geometry (reused in both passes)
        # char_font_paths/char_size_pcts/char_y_offsets_pct describe a single
        # string's per-character fonts — only meaningful when there's exactly
        # one active text; with several (e.g. smart layout) they don't map to
        # any particular entry, so they're ignored rather than misapplied to all.
        _per_char = bool(char_font_paths) and len(active_texts) == 1
        _size_px = lambda pct: max(4, int(sh * pct / 100))
        _off_px  = lambda pct: int(sh * pct / 100)
        _text_geom = []
        for t_str, text_pos, text_size_pct in active_texts:
            font_size = _size_px(text_size_pct)
            font      = _font_from_path(font_path, font_size)
            if _per_char:
                _cf, _cy_off = _per_char_fonts(
                    t_str, char_font_paths, char_size_pcts, char_y_offsets_pct,
                    text_size_pct, _size_px, _off_px, font)
            else:
                _cf, _cy_off = None, None
            if texts_are_crop_relative:
                tx = int(text_pos[0] * sw)
                ty = int(text_pos[1] * sh)
            else:
                tx = int((text_pos[0] * src_w - x1) / crop_w * sw)
                ty = int((text_pos[1] * src_h - y1) / crop_h * sh)
            _text_geom.append((t_str, font, tx, ty, _cf, _cy_off))

        # Pass 1: outline + shadow (always solid color)
        for t_str, font, tx, ty, _cf, _cy_off in _text_geom:
            if outline_step > 0:
                for odx, ody in [(-outline_step, 0), (outline_step, 0),
                                  (0, -outline_step), (0, outline_step),
                                  (-outline_step, -outline_step), (outline_step, -outline_step),
                                  (-outline_step,  outline_step), (outline_step,  outline_step)]:
                    _draw_chars(td, t_str, font, tx + odx, ty + ody,
                                text_spacing_pct, (cr, cg, cb, 220), stroke_w=_bsw,
                                fonts=_cf, y_offsets=_cy_off)
            if shadow:
                _sr, _sg, _sb = _hex_to_rgb(shadow_color)
                _draw_chars(td, t_str, font,
                            tx + shadow_x * SUPER_SAMPLE,
                            ty + shadow_y * SUPER_SAMPLE,
                            text_spacing_pct, (_sr, _sg, _sb, 200), stroke_w=_bsw,
                            fonts=_cf, y_offsets=_cy_off)

        # Pass 2: text fill — gradient or solid
        if text_gradient:
            fill_layer = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
            fd = ImageDraw.Draw(fill_layer)
            for t_str, font, tx, ty, _cf, _cy_off in _text_geom:
                _draw_chars(fd, t_str, font, tx, ty, text_spacing_pct,
                            (255, 255, 255, 255), stroke_w=_bsw, fonts=_cf, y_offsets=_cy_off)
            _, _, _, _fill_alpha = fill_layer.split()
            _bbox = _fill_alpha.getbbox()
            if _bbox:
                # Gradient spans only the text bounding box → full color range always visible
                _bx1, _by1, _bx2, _by2 = _bbox
                _bw, _bh = max(1, _bx2 - _bx1), max(1, _by2 - _by1)
                _grad_tile = _make_gradient(_bw, _bh, gradient_color1, gradient_color2, gradient_dir)
                _r2, _g2, _b2 = _hex_to_rgb(gradient_color2)
                _grad_full = Image.new("RGB", (sw, sh), (_r2, _g2, _b2))
                _grad_full.paste(_grad_tile, (_bx1, _by1))
                _grad_rgba = _grad_full.convert("RGBA")
                _grad_rgba.putalpha(_fill_alpha)
                text_layer = Image.alpha_composite(text_layer, _grad_rgba)
        else:
            for t_str, font, tx, ty, _cf, _cy_off in _text_geom:
                _draw_chars(td, t_str, font, tx, ty, text_spacing_pct,
                            (r, g, b, 255), stroke_w=_bsw, fonts=_cf, y_offsets=_cy_off)
        if text_rotation != 0:
            text_layer = text_layer.rotate(-text_rotation, expand=False, resample=Image.BICUBIC)
        if italic:
            text_layer = _apply_italic(text_layer)
        _rc, _gc, _bc, _ac = text_layer.split()
        _ac = _ac.filter(ImageFilter.MaxFilter(3))
        _ac = _ac.point(lambda v: 255 if v > 60 else 0)
        if text_opacity < 100:
            _ac = _ac.point(lambda v: int(v * text_opacity / 100))
        text_layer = Image.merge("RGBA", (_rc, _gc, _bc, _ac))
        text_out = text_layer.resize(size, Image.LANCZOS)
        img = Image.alpha_composite(img.convert("RGBA"), text_out).convert("RGB")

    img_p = img.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=1 if dither else 0)
    if dest_path is not None:
        img_p.save(dest_path, format="BMP")
    return img_p


def make_preview(img_p: Image.Image, mult: int) -> Image.Image:
    w, h = img_p.size
    return img_p.resize((w * mult, h * mult), Image.NEAREST)


def _make_app_icon() -> Image.Image:
    """Renderiza el icono a 1024px y devuelve 256px suavizado con LANCZOS."""
    SZ   = 1024   # render grande → downscale = anti-aliasing gratis
    img  = Image.new("RGBA", (SZ, SZ), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    m  = int(SZ * 0.09)
    sw = SZ - 2 * m
    sh = SZ - 2 * m
    bw = SZ // 18   # grosor del borde

    def _shield(ox, oy, w, h):
        return [
            (ox,           oy),
            (ox + w,       oy),
            (ox + w,       oy + h * 0.60),
            (ox + w * 0.5, oy + h),
            (ox,           oy + h * 0.60),
        ]

    outer = _shield(m, m, sw, sh)

    # Sombra del escudo (desplazada)
    shadow_pts = [(x + SZ*0.025, y + SZ*0.025) for x, y in outer]
    draw.polygon(shadow_pts, fill=(0, 0, 0, 90))

    # Relleno interior degradado simulado con dos polígonos
    draw.polygon(outer, fill=(28, 35, 46, 255))

    # Borde exterior dorado grueso
    draw.line(outer + [outer[0]], fill=(230, 184, 74, 255), width=bw)

    # Borde interior (filigrana dorada sutil)
    pad  = bw * 2
    inn  = _shield(m + pad, m + pad, sw - pad*2, sh - pad*2)
    draw.line(inn + [inn[0]], fill=(230, 184, 74, 110), width=max(4, bw // 4))

    # Texto "L2"
    font_size = SZ // 3
    fnt = None
    for face in ("arialbd.ttf", "calibrib.ttf", "verdanab.ttf", "arial.ttf"):
        try:
            fnt = ImageFont.truetype(os.path.join(FONTS_DIR, face), font_size)
            break
        except Exception:
            pass
    if fnt is None:
        fnt = ImageFont.load_default()

    text = "L2"
    bb   = draw.textbbox((0, 0), text, font=fnt)
    tx   = SZ // 2 - (bb[2] - bb[0]) // 2 - bb[0]
    ty   = int(SZ * 0.25)

    # Sombra del texto
    for ox, oy in [(-3,3),(3,3),(0,5)]:
        draw.text((tx + ox*4, ty + oy*4), text, font=fnt, fill=(0, 0, 0, 120))
    # Texto dorado principal
    draw.text((tx, ty), text, font=fnt, fill=(230, 184, 74, 255))
    # Highlight sutil
    draw.text((tx - 4, ty - 4), text, font=fnt, fill=(255, 225, 140, 60))

    # Downscale a 256 con LANCZOS → bordes suaves sin pixelado
    return img.resize((256, 256), Image.LANCZOS)


def _ensure_app_icon() -> str:
    """Crea/actualiza el .ico junto al .py, devuelve su path."""
    path = os.path.join(_HERE, "l2crest.ico")
    if os.path.exists(path):
        return path
    try:
        base = _make_app_icon()   # 256×256 suavizado (LANCZOS desde 1024)
        base.save(path, format="ICO",
                  sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
    except Exception:
        pass
    return path


# ── Aplicación ────────────────────────────────────────────────────────────────

from app_presets import PresetsMixin
from app_files import FilesMixin
from app_export import ExportMixin
from app_editing import EditingMixin
from app_text import TextMixin
from app_preview import PreviewMixin
from app_ui import UIBuilderMixin

_AppBase = _TkDnD.Tk if _HAS_DND else tk.Tk
class L2CrestApp(PresetsMixin, FilesMixin, ExportMixin, EditingMixin, TextMixin, PreviewMixin, UIBuilderMixin, _AppBase):
    def __init__(self):
        super().__init__()
        self.title("L2 Crest Maker  ·  v2.0")
        self.resizable(True, True)
        self.configure(bg=BG0)
        try:
            self.wm_iconbitmap(_ensure_app_icon())
        except Exception:
            pass
        self._fullscreen   = False
        self._resize_after = None
        self.src_prev_w    = SOURCE_PREV_W
        self.src_prev_h    = SOURCE_PREV_H

        # Rutas
        self.src_path  = tk.StringVar()   # Fuente 1: background
        self.src_path2 = tk.StringVar()   # Fuente 2: PNG overlay (opcional)
        self.clan_path = tk.StringVar()
        self.ally_path = tk.StringVar()

        # Texto unificado
        self.text_var          = tk.StringVar()
        self.text_size         = tk.IntVar(value=40)
        self.text_pos          = (0.5, 0.5)
        self.text_spacing      = tk.IntVar(value=0)
        self.italic_var        = tk.BooleanVar(value=False)
        self.bold_var          = tk.BooleanVar(value=False)
        self.text_color        = "#ffffff"
        self.outline_var       = tk.IntVar(value=2)
        self.text_opacity_var  = tk.IntVar(value=100)
        self.text_rotation_var = tk.IntVar(value=0)
        self._text_upd         = False
        self._src_disp_rect    = None
        self._src_img_size     = None   # (src_w, src_h) cached para constrainer drag
        self._color_btns       = {}
        self._drag_preview_after = None
        self._mf_preview_after = None
        self._nudge_pushed     = False

        # Undo / Redo
        self._undo_stack = []
        self._redo_stack = []

        # Font picker cache
        self._font_thumb_cache  = {}
        self._font_picker_open  = False

        # Asset gallery (overlays/plantillas) cache
        self._asset_thumb_cache = {}
        self._gallery_open      = False

        self._preview_error_logged = False

        # Sombra
        self.shadow_var   = tk.BooleanVar(value=False)
        self.shadow_x     = tk.IntVar(value=1)
        self.shadow_y     = tk.IntVar(value=1)
        self.shadow_color = "#000000"

        # Fuentes
        fonts = _get_system_fonts()
        self.font_names = [n for n, _ in fonts]
        self.font_paths = {n: p for n, p in fonts}
        default_font = next(
            (n for n in self.font_names if "faster" in n.lower() and "stroker" in n.lower()),
            self.font_names[0] if self.font_names else ""
        )
        self.selected_font  = tk.StringVar(value=default_font)
        self.multi_font_var = tk.BooleanVar(value=False)
        self.mf_chars = [tk.StringVar(value="") for _ in range(3)]
        self.mf_fonts = [tk.StringVar(value=default_font) for _ in range(3)]
        self.mf_sizes     = [tk.IntVar(value=60) for _ in range(3)]
        self.mf_offsets_y = [tk.IntVar(value=0)  for _ in range(3)]
        self._mf_upd  = False

        # Transformaciones
        self.rotation_var = tk.IntVar(value=0)
        self.flip_h_var   = tk.BooleanVar(value=False)
        self.flip_v_var   = tk.BooleanVar(value=False)

        # Ajustes de imagen
        self.hue_var        = tk.IntVar(value=0)
        self.brightness_var = tk.DoubleVar(value=1.0)
        self.contrast_var   = tk.DoubleVar(value=1.0)
        self.saturation_var = tk.DoubleVar(value=1.0)
        self.sharpen_var    = tk.BooleanVar(value=False)
        self.dither_var     = tk.BooleanVar(value=True)
        self.export_png_var = tk.BooleanVar(value=False)

        # Ruta del juego L2
        self.game_path = tk.StringVar(value=self._detect_l2_path())

        # Preview
        self.preview_bg_var  = tk.StringVar(value="black")
        self._tk_src         = None
        self._tk_clan        = None
        self._tk_ally        = None
        self._last_clan_img  = None
        self._last_ally_img  = None
        self._text_prev_after = None

        # Archivos recientes y presets
        self.recent_files = _load_json(RECENT_FILE, [])
        self.presets      = _load_json(PRESETS_FILE, {})
        self.preset_name  = tk.StringVar()

        # Feature 2: color replacements
        self._color_replacements = []
        # Feature 5: before/after mode
        self._before_after_mode = False
        # Feature 7: export history
        self._export_history = []
        HISTORY_MAX = 10
        # Feature 8: split drag
        self._dragging_split = False
        # Smart layout for initials
        self._smart_layout_active = False
        # Gradient text
        self.text_gradient_var  = tk.BooleanVar(value=False)
        self._gradient_color1   = "#e0b84a"   # dorado (top)
        self._gradient_color2   = "#7b3000"   # marrón oscuro (bottom)
        self.gradient_dir_var   = tk.StringVar(value="vertical")
        self._outline_color_val = None        # None = auto-invertido

        self._build_ui()
        self.text_var.trace_add("write", lambda *_: self._on_text_change())
        self.bind("<Control-p>", lambda _: self._preview())
        self.bind("<Control-Return>", lambda _: self._convert())
        self.bind("<Control-z>", self._undo)
        self.bind("<Control-y>", self._redo)
        self.bind("<F11>", self._toggle_fullscreen)
        self.bind("<Escape>", self._exit_fullscreen)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._load_session()

    # ── Sesión ────────────────────────────────────────────────────────────────

    def _common_kw(self) -> dict:
        return dict(
            text_color       = self.text_color,
            font_path        = self._current_font_path(),
            text_spacing_pct = self.text_spacing.get(),
            italic           = self.italic_var.get(),
            bold             = self.bold_var.get(),
            brightness       = self.brightness_var.get(),
            contrast         = self.contrast_var.get(),
            saturation       = self.saturation_var.get(),
            hue              = self.hue_var.get(),
            sharpen          = self.sharpen_var.get(),
            dither           = self.dither_var.get(),
            rotation         = self.rotation_var.get(),
            flip_h           = self.flip_h_var.get(),
            flip_v           = self.flip_v_var.get(),
            shadow           = self.shadow_var.get(),
            shadow_x         = self.shadow_x.get(),
            shadow_y         = self.shadow_y.get(),
            shadow_color     = self.shadow_color,
            text_outline         = self.outline_var.get(),
            text_opacity         = self.text_opacity_var.get(),
            text_rotation        = self.text_rotation_var.get(),
            color_replacements   = self._color_replacements or None,
            text_gradient        = self.text_gradient_var.get(),
            gradient_color1      = self._gradient_color1,
            gradient_color2      = self._gradient_color2,
            gradient_dir         = self.gradient_dir_var.get(),
            outline_color        = self._outline_color_val,
        )

    def _save_session(self):
        s = self._get_current_settings()
        s["src_path"]  = self.src_path.get()
        s["src_path2"] = self.src_path2.get()
        s["clan_path"] = self.clan_path.get()
        s["ally_path"] = self.ally_path.get()
        s["game_path"] = self.game_path.get()
        s["dither"]    = self.dither_var.get()
        _save_json(SESSION_FILE, s)

    def _load_session(self):
        s = _load_json(SESSION_FILE, {})
        if not s:
            return
        try:
            self._apply_settings(s)
            if s.get("src_path"):
                self.src_path.set(s["src_path"])
            if s.get("src_path2"):
                self.src_path2.set(s["src_path2"])
            if s.get("clan_path"):
                self.clan_path.set(s["clan_path"])
            if s.get("ally_path"):
                self.ally_path.set(s["ally_path"])
            if s.get("game_path"):
                self.game_path.set(s["game_path"])
            self.dither_var.set(s.get("dither", True))
            src = self.src_path.get()
            if src and os.path.isfile(src):
                self._update_source_preview(src)
        except Exception as e:
            _log_error("_load_session", e)

    def _on_close(self):
        self._save_session()
        self.destroy()

    # ── Restart ───────────────────────────────────────────────────────────────

    def _restart(self):
        self.destroy()
        os.execv(sys.executable, [sys.executable] + sys.argv)

    # ── Acceso directo en escritorio ──────────────────────────────────────────

    def _create_desktop_shortcut(self):
        ico  = os.path.join(_HERE, "l2crest.ico")
        if not os.path.isfile(ico):
            ico = _ensure_app_icon()
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        lnk     = os.path.join(desktop, "L2 Crest Maker.lnk")
        if getattr(sys, "frozen", False):
            target    = sys.executable
            arguments = ""
        else:
            script    = os.path.join(_HERE, "L2CrestMaker.py")
            pythonw   = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
            target    = pythonw if os.path.isfile(pythonw) else sys.executable
            arguments = f"\"{script}\""
        ps = (
            f"$s = New-Object -ComObject WScript.Shell;"
            f"$l = $s.CreateShortcut('{lnk}');"
            f"$l.TargetPath = '{target}';"
            f"$l.Arguments = '{arguments}';"
            f"$l.IconLocation = '{ico}';"
            f"$l.WorkingDirectory = '{_HERE}';"
            f"$l.Description = 'L2 Crest Maker';"
            f"$l.Save()"
        )
        try:
            import subprocess
            r = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                capture_output=True, timeout=10
            )
            if r.returncode == 0:
                messagebox.showinfo("Acceso directo",
                    f"✔ Acceso directo creado en el escritorio.\n\n{lnk}")
            else:
                raise RuntimeError(r.stderr.decode(errors="replace"))
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo crear el acceso directo:\n{e}")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = L2CrestApp()
    app.mainloop()
