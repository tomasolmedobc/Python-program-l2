"""
L2 Crest Maker  ·  v2.0
Creador de Crests para Lineage 2
  • Clan Crest   : 16x12 px, 256 colores BMP  (zona derecha)
  • Ally Crest   :  8x12 px, 256 colores BMP  (zona izquierda)
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
from PIL import Image, ImageTk, ImageDraw, ImageFont, ImageEnhance, ImageFilter
import os, sys, json, ctypes, io, winreg, colorsys

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
OUTPUT_DIR    = r"E:\L2CyA"
FONTS_DIR     = r"C:\Windows\Fonts"
SUPER_SAMPLE  = 16

_HERE        = os.path.dirname(os.path.abspath(__file__))
RECENT_FILE  = os.path.join(_HERE, "l2crest_recent.json")
PRESETS_FILE = os.path.join(_HERE, "l2crest_presets.json")
SESSION_FILE = os.path.join(_HERE, "l2crest_session.json")
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


def _apply_italic(layer: Image.Image, shear_k: float = 0.30) -> Image.Image:
    w, h = layer.size
    matrix = (1, shear_k, -shear_k * h, 0, 1, 0)
    return layer.transform((w, h), Image.AFFINE, matrix, resample=Image.BICUBIC)


def _draw_chars(draw_obj, text: str, font, cx: int, cy: int,
                spacing_pct: int, fill: tuple, stroke_w: int = 0):
    if not text:
        return
    chars   = list(text)
    boxes   = [draw_obj.textbbox((0, 0), c, font=font, stroke_width=stroke_w) for c in chars]
    widths  = [b[2] - b[0] for b in boxes]
    heights = [b[3] - b[1] for b in boxes]
    avg_w   = sum(widths) / len(widths) if widths else 0
    gap     = int(avg_w * spacing_pct / 100)
    total_w = sum(widths) + gap * (len(chars) - 1)
    max_h   = max(heights) if heights else 0
    x = cx - total_w // 2
    y = cy - max_h  // 2
    for c, w in zip(chars, widths):
        draw_obj.text((x, y), c, font=font, fill=fill,
                      stroke_width=stroke_w, stroke_fill=fill)
        x += w + gap


def _hex_to_rgb(hex_color: str) -> tuple:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _make_gradient(w: int, h: int, color1: str, color2: str,
                   direction: str = "vertical") -> Image.Image:
    """Linear gradient image (RGB). color1 = top/left, color2 = bottom/right."""
    r1, g1, b1 = _hex_to_rgb(color1)
    r2, g2, b2 = _hex_to_rgb(color2)
    pixels: list = []
    if direction == "horizontal":
        for _ in range(h):
            for x in range(w):
                t = x / max(w - 1, 1)
                pixels.append((int(r1*(1-t)+r2*t), int(g1*(1-t)+g2*t), int(b1*(1-t)+b2*t)))
    else:   # vertical
        for y in range(h):
            t = y / max(h - 1, 1)
            c = (int(r1*(1-t)+r2*t), int(g1*(1-t)+g2*t), int(b1*(1-t)+b2*t))
            pixels.extend([c] * w)
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


def _load_json(path: str, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save_json(path: str, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


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
        _text_geom = []
        for t_str, text_pos, text_size_pct in active_texts:
            font_size = max(4, int(sh * text_size_pct / 100))
            font      = _font_from_path(font_path, font_size)
            if texts_are_crop_relative:
                tx = int(text_pos[0] * sw)
                ty = int(text_pos[1] * sh)
            else:
                tx = int((text_pos[0] * src_w - x1) / crop_w * sw)
                ty = int((text_pos[1] * src_h - y1) / crop_h * sh)
            _text_geom.append((t_str, font, tx, ty))

        # Pass 1: outline + shadow (always solid color)
        for t_str, font, tx, ty in _text_geom:
            if outline_step > 0:
                for odx, ody in [(-outline_step, 0), (outline_step, 0),
                                  (0, -outline_step), (0, outline_step),
                                  (-outline_step, -outline_step), (outline_step, -outline_step),
                                  (-outline_step,  outline_step), (outline_step,  outline_step)]:
                    _draw_chars(td, t_str, font, tx + odx, ty + ody,
                                text_spacing_pct, (cr, cg, cb, 220), stroke_w=_bsw)
            if shadow:
                _sr, _sg, _sb = _hex_to_rgb(shadow_color)
                _draw_chars(td, t_str, font,
                            tx + shadow_x * SUPER_SAMPLE,
                            ty + shadow_y * SUPER_SAMPLE,
                            text_spacing_pct, (_sr, _sg, _sb, 200), stroke_w=_bsw)

        # Pass 2: text fill — gradient or solid
        if text_gradient:
            fill_layer = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
            fd = ImageDraw.Draw(fill_layer)
            for t_str, font, tx, ty in _text_geom:
                _draw_chars(fd, t_str, font, tx, ty, text_spacing_pct,
                            (255, 255, 255, 255), stroke_w=_bsw)
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
            for t_str, font, tx, ty in _text_geom:
                _draw_chars(td, t_str, font, tx, ty, text_spacing_pct,
                            (r, g, b, 255), stroke_w=_bsw)
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

_AppBase = _TkDnD.Tk if _HAS_DND else tk.Tk
class L2CrestApp(_AppBase):
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
        self._nudge_pushed     = False

        # Undo / Redo
        self._undo_stack = []
        self._redo_stack = []

        # Font picker cache
        self._font_thumb_cache  = {}
        self._font_picker_open  = False

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
        self.selected_font = tk.StringVar(value=default_font)

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
        self._split_ratio = 8 / 24
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

    # ── Construcción UI ───────────────────────────────────────────────────────

    def _build_ui(self):
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # ── Columna izquierda: scrollable ────────────────────────────────────
        left_outer = tk.Frame(self, bg=BG0)
        left_outer.grid(row=0, column=0, sticky="nsew", padx=(12, 6), pady=12)
        left_outer.rowconfigure(0, weight=1)
        left_outer.columnconfigure(0, weight=1)

        self._left_canvas = tk.Canvas(left_outer, bg=BG0, highlightthickness=0)
        left_vsb = tk.Scrollbar(
            left_outer, orient="vertical", command=self._left_canvas.yview,
            bg=BG2, troughcolor=BG0, relief="flat", bd=0, width=8
        )
        self._left_canvas.configure(yscrollcommand=left_vsb.set)
        self._left_canvas.grid(row=0, column=0, sticky="nsew")
        left_vsb.grid(row=0, column=1, sticky="ns")

        left = tk.Frame(self._left_canvas, bg=BG0)
        self._left_inner = left
        self._left_win_id = self._left_canvas.create_window((0, 0), window=left, anchor="nw")

        # Solo actualizar scrollregion; el frame interior mantiene su ancho natural
        left.bind("<Configure>", lambda _: self._left_canvas.configure(
            scrollregion=self._left_canvas.bbox("all")))

        # Rueda del mouse desplaza el panel izquierdo
        def _scroll_left(event):
            self._left_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        left_outer.bind("<Enter>", lambda _: self.bind_all("<MouseWheel>", _scroll_left))
        left_outer.bind("<Leave>", lambda _: self.unbind_all("<MouseWheel>"))

        # ── Columna derecha ───────────────────────────────────────────────────
        right = tk.Frame(self, bg=BG0)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 12), pady=12)

        self._build_header(left)
        self._build_files_card(left)
        self._build_transform_card(left)
        self._build_adjust_card(left)
        self._build_text_card(left)
        self._build_presets_card(left)
        self._build_actions_card(left)

        self._build_source_preview(right)
        self._build_result_preview(right)

        # Status bar
        self.status_var = tk.StringVar(
            value="Listo.  |  Ctrl+P = preview  |  Ctrl+Enter = convertir  |  F11 = pantalla completa"
        )
        tk.Label(
            self, textvariable=self.status_var,
            font=("Segoe UI", 8), fg=TXS, bg=BG0, anchor="w", padx=12
        ).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 6))

        self._apply_styles()
        # Fijar ancho mínimo del panel izq y minsize de ventana tras layout inicial
        self.after_idle(self._lock_left_width)

    def _lock_left_width(self):
        self.update_idletasks()
        lw = self._left_inner.winfo_reqwidth() + 20   # ancho natural + scrollbar
        self._left_canvas.configure(width=lw)
        self.columnconfigure(0, weight=0, minsize=lw)
        self.minsize(lw + SOURCE_PREV_W // 2, 560)

    # ── Helpers de UI ─────────────────────────────────────────────────────────

    def _card(self, parent, title: str, accent=ACC) -> tk.Frame:
        lf = tk.LabelFrame(
            parent, text=f"  {title}  ",
            font=("Segoe UI", 9, "bold"),
            fg=accent, bg=BG1, bd=1, relief="solid", labelanchor="nw"
        )
        lf.pack(fill="x", pady=(0, 8))
        inner = tk.Frame(lf, bg=BG1)
        inner.pack(fill="x", padx=10, pady=8)
        return inner

    def _btn(self, parent, text, cmd, bg=BG2, fg=TXP, width=None):
        kw = {"width": width} if width else {}
        return tk.Button(
            parent, text=text, command=cmd,
            bg=bg, fg=fg,
            activebackground="#2d333b", activeforeground="#ffffff",
            relief="flat", cursor="hand2",
            font=("Segoe UI", 9), pady=5, padx=8, **kw
        )

    def _chk(self, parent, text, var, cmd=None):
        return tk.Checkbutton(
            parent, text=text, variable=var,
            command=cmd or self._refresh_text_preview,
            font=("Segoe UI", 9), fg=TXP, bg=BG1,
            selectcolor=BG2, activebackground=BG1,
            activeforeground=TXP, cursor="hand2"
        )

    def _scale(self, parent, var, from_, to, length=130, res=1, cmd=None):
        return tk.Scale(
            parent, variable=var, from_=from_, to=to, resolution=res,
            orient="horizontal", length=length,
            bg=BG1, fg=TXP, troughcolor=BG2,
            highlightthickness=0, bd=0, showvalue=1,
            command=cmd or (lambda _: self._refresh_text_preview())
        )

    def _lbl(self, parent, text, fg=TXS, w=None):
        kw = {"width": w, "anchor": "e"} if w else {}
        return tk.Label(parent, text=text, font=("Segoe UI", 9),
                        fg=fg, bg=BG1, **kw)

    def _row(self, parent, pady=2):
        r = tk.Frame(parent, bg=BG1)
        r.pack(fill="x", pady=pady)
        return r

    # ── Header ────────────────────────────────────────────────────────────────

    def _build_header(self, parent):
        hdr = tk.Frame(parent, bg=BG0)
        hdr.pack(fill="x", pady=(0, 10))
        tk.Label(hdr, text="⚔  L2 Crest Maker  ⚔",
                 font=("Segoe UI", 17, "bold"), fg=ACC, bg=BG0).pack(side="left")
        tk.Button(hdr, text="↺ Reiniciar", command=self._restart,
                  bg="#1c2128", fg=TXS,
                  activebackground=BG2, activeforeground=TXP,
                  relief="flat", cursor="hand2",
                  font=("Segoe UI", 9), pady=4, padx=10).pack(side="right")
        tk.Button(hdr, text="🔗 Acceso directo", command=self._create_desktop_shortcut,
                  bg="#1c2128", fg=TXS,
                  activebackground=BG2, activeforeground=ACC,
                  relief="flat", cursor="hand2",
                  font=("Segoe UI", 9), pady=4, padx=10).pack(side="right", padx=(0, 4))
        self._fs_btn = tk.Button(
            hdr, text="⛶  Pantalla completa  [F11]", command=self._toggle_fullscreen,
            bg="#1c2128", fg=TXS,
            activebackground=BG2, activeforeground=TXP,
            relief="flat", cursor="hand2",
            font=("Segoe UI", 9), pady=4, padx=10
        )
        self._fs_btn.pack(side="right", padx=(0, 6))
        tk.Label(parent, text="Clan 16×12  ·  Ally 8×12  ·  256 colores BMP",
                 font=("Segoe UI", 9), fg=TXS, bg=BG0).pack(anchor="w", pady=(0, 6))

    # ── Archivos ──────────────────────────────────────────────────────────────

    def _build_files_card(self, parent):
        p = self._card(parent, "📁  Archivos")

        def _row_file(label, var, browse_cmd):
            r = self._row(p)
            self._lbl(r, label, w=10).pack(side="left")
            ttk.Entry(r, textvariable=var, width=34).pack(side="left", padx=(4, 4))
            self._btn(r, "…", browse_cmd, width=3).pack(side="left")

        _row_file("Fuente 1 ★:", self.src_path, self._browse_source)

        # Fuente 2 con botón swap
        r2 = self._row(p, pady=2)
        self._lbl(r2, "Fuente 2:", w=10).pack(side="left")
        ttk.Entry(r2, textvariable=self.src_path2, width=34).pack(side="left", padx=(4, 4))
        self._btn(r2, "…", self._browse_source2, width=3).pack(side="left", padx=(0, 4))
        self._btn(r2, "✕", lambda: self.src_path2.set(""), width=3,
                  bg="#3d1f1f", fg=RED).pack(side="left", padx=(0, 8))
        self._btn(r2, "⇅ Swap capas", self._swap_sources,
                  bg="#2a1f3d", fg="#c084fc").pack(side="left")

        tk.Label(p, text="  ★ = obligatoria  |  Fuente 2 (PNG) opcional — composita sobre Fuente 1",
                 font=("Segoe UI", 8, "italic"), fg=TXS, bg=BG1).pack(anchor="w", pady=(0, 4))

        _row_file("Clan BMP:", self.clan_path, self._browse_clan)
        _row_file("Ally BMP:", self.ally_path, self._browse_ally)

        _row_file("Carpeta L2:", self.game_path, self._browse_game_path)

        r = self._row(p, pady=(6, 0))
        self._lbl(r, "Recientes:", w=10).pack(side="left")
        self.recent_combo = ttk.Combobox(
            r, values=self.recent_files, width=32,
            state="readonly", font=("Segoe UI", 9)
        )
        self.recent_combo.pack(side="left", padx=(4, 4))
        self.recent_combo.bind("<<ComboboxSelected>>", self._open_recent)
        if self.recent_files:
            self.recent_combo.set(self.recent_files[0])

    # ── Transformaciones ──────────────────────────────────────────────────────

    def _build_transform_card(self, parent):
        p = self._card(parent, "🔄  Transformaciones")
        r = self._row(p)
        self._lbl(r, "Rotación:", w=10).pack(side="left")
        for deg in [0, 90, 180, 270]:
            tk.Radiobutton(
                r, text=f"{deg}°", variable=self.rotation_var, value=deg,
                font=("Segoe UI", 9), fg=TXP, bg=BG1,
                selectcolor=BG2, activebackground=BG1, cursor="hand2",
                command=self._refresh_text_preview
            ).pack(side="left", padx=3)
        self._lbl(r, "  Flip:", fg=TXS).pack(side="left", padx=(10, 4))
        self._chk(r, "↔ H", self.flip_h_var).pack(side="left", padx=2)
        self._chk(r, "↕ V", self.flip_v_var).pack(side="left", padx=2)

    # ── Ajustes de imagen ─────────────────────────────────────────────────────

    def _build_adjust_card(self, parent):
        p = self._card(parent, "🎨  Ajustes de imagen")

        def _srow(label, var, from_, to):
            r = self._row(p, pady=1)
            self._lbl(r, label, w=12).pack(side="left")
            self._scale(r, var, from_, to, length=200, res=0.05).pack(side="left", padx=(4, 0))

        _srow("Brillo:",     self.brightness_var, 0.5, 2.0)
        _srow("Contraste:",  self.contrast_var,   0.5, 2.0)
        _srow("Saturación:", self.saturation_var, 0.0, 2.0)

        r = self._row(p, pady=1)
        self._lbl(r, "Tono (hue):", w=12).pack(side="left")
        self._scale(r, self.hue_var, -180, 180, length=200, res=1).pack(side="left", padx=(4, 0))
        self._lbl(r, "°").pack(side="left", padx=(2, 0))

        r = self._row(p, pady=(6, 0))
        self._btn(r, "⟳ Reset", self._reset_adjustments, bg=BG2, fg=TXS).pack(side="left", padx=(0, 4))
        self._btn(r, "✨ Auto", self._auto_adjust, bg=BG2, fg=ACC).pack(side="left", padx=(0, 12))
        self._chk(r, "Nitidez",  self.sharpen_var).pack(side="left", padx=4)
        self._chk(r, "Dithering", self.dither_var).pack(side="left", padx=4)
        self._chk(r, "Exportar PNG", self.export_png_var, cmd=lambda: None).pack(side="left", padx=4)

        r2 = self._row(p, pady=(4, 0))
        self._repl_btn = self._btn(r2, "Reemplazos (0)", self._show_replacements_popup, bg=BG2, fg=TXS)
        self._repl_btn.pack(side="left", padx=(0, 4))

    # ── Texto / Iniciales ─────────────────────────────────────────────────────

    def _build_text_card(self, parent):
        p = self._card(parent, "✏️  Texto / Iniciales")
        vcmd = (self.register(lambda P: len(P) <= 3), "%P")

        r = self._row(p, pady=3)
        self._lbl(r, "Letras:", fg=ACC, w=12).pack(side="left")
        tk.Entry(
            r, textvariable=self.text_var, width=5,
            validate="key", validatecommand=vcmd,
            font=("Segoe UI", 13, "bold"),
            bg=BG2, fg=ACC, insertbackground=ACC,
            relief="flat", bd=4
        ).pack(side="left", padx=(4, 8))
        self._lbl(r, "Tamaño:").pack(side="left")
        self._scale(r, self.text_size, 10, 200, length=100).pack(side="left")
        self._lbl(r, "%").pack(side="left", padx=(0, 8))
        self._btn(r, "⊙ Auto", self._auto_fit, bg=BG2, fg=ACC).pack(side="left", padx=(0, 4))
        self._smart_layout_btn = tk.Button(
            r, text="📐 Smart", command=self._apply_smart_layout,
            bg=BG2, fg=TXS, relief="flat", cursor="hand2", bd=0,
            activebackground="#2d333b", activeforeground="#ffffff",
            font=("Segoe UI", 9), pady=5, padx=8
        )
        self._smart_layout_btn.pack(side="left", padx=(0, 4))
        self._btn(r, "✕ Layout", self._clear_smart_layout, bg=BG2, fg=TXS).pack(side="left")

        ttk.Separator(p, orient="horizontal").pack(fill="x", pady=6)

        # Fuente
        r = self._row(p)
        self._lbl(r, "Fuente:", w=12).pack(side="left")
        self.font_combo = ttk.Combobox(
            r, textvariable=self.selected_font,
            values=self.font_names, width=22
        )
        self.font_combo.pack(side="left", padx=(4, 4))
        self.font_combo.bind("<<ComboboxSelected>>", self._on_font_selected)
        self.font_combo.bind("<KeyRelease>", self._filter_fonts)
        self._btn(r, "🔤", self._open_font_picker, bg=BG2, fg=AC2, width=3).pack(side="left", padx=(0, 6))
        self._lbl(r, f"({len(self.font_names)})").pack(side="left")

        # Font preview label
        self._font_prev_lbl = tk.Label(p, bg=BG2, relief="flat", bd=0)
        self._font_prev_lbl.pack(fill="x", padx=12, pady=(2, 4))
        self._tk_font_prev_img = None

        # Color + cursiva
        r = self._row(p, pady=4)
        self._lbl(r, "Color texto:", w=12).pack(side="left")
        for lbl, col, fgc in [("Blanco", "#ffffff", "#111"), ("Negro", "#000000", "#eee"), ("Dorado", "#e0b84a", "#111")]:
            btn = tk.Button(
                r, text=lbl, width=6, bg=col, fg=fgc,
                relief="flat", cursor="hand2", font=("Segoe UI", 8),
                command=lambda c=col: self._set_text_color(c)
            )
            btn.pack(side="left", padx=2)
            self._color_btns[col] = btn
        self._btn(r, "Custom…", self._pick_custom_color, width=7).pack(side="left", padx=(4, 16))
        self._chk(r, "Cursiva", self.italic_var).pack(side="left")
        self._chk(r, "Negrita", self.bold_var).pack(side="left", padx=(8, 0))
        self._color_btns["#ffffff"].config(relief="sunken")

        r_auto = self._row(p, pady=(0, 4))
        self._btn(r_auto, "🎯 Auto (según imagen)", self._auto_text_color,
                  bg=BG2, fg=ACC).pack(side="left")
        self._lbl(r_auto, "  analiza color/contraste de la imagen y ajusta texto+contorno+sombra",
                  fg=TXS).pack(side="left")

        # Espaciado
        r = self._row(p)
        self._lbl(r, "Espaciado:", w=12).pack(side="left")
        self._scale(r, self.text_spacing, 0, 100, length=100).pack(side="left")
        self._lbl(r, "%").pack(side="left", padx=(0, 12))

        # Opacidad
        r = self._row(p)
        self._lbl(r, "Opacidad:", w=12).pack(side="left")
        self._scale(r, self.text_opacity_var, 0, 100, length=100).pack(side="left")
        self._lbl(r, "%").pack(side="left", padx=(0, 12))

        # Rotación texto
        r = self._row(p)
        self._lbl(r, "Rotación:", w=12).pack(side="left")
        self._scale(r, self.text_rotation_var, -45, 45, length=130).pack(side="left")
        self._lbl(r, "°").pack(side="left", padx=(0, 12))

        # Contorno
        r = self._row(p)
        self._lbl(r, "Contorno:", w=12).pack(side="left")
        self._scale(r, self.outline_var, 0, 8, length=100).pack(side="left")

        ttk.Separator(p, orient="horizontal").pack(fill="x", pady=6)

        # Sombra
        r = self._row(p)
        self._lbl(r, "Sombra:", w=12).pack(side="left")
        self._chk(r, "Activar", self.shadow_var).pack(side="left", padx=(4, 10))
        for lbl, var in [("X:", self.shadow_x), ("Y:", self.shadow_y)]:
            self._lbl(r, lbl).pack(side="left")
            self._scale(r, var, -3, 3, length=60).pack(side="left", padx=(0, 6))
        self._shadow_btn = tk.Button(
            r, text="Color", width=6,
            bg=self.shadow_color, fg="#e0e0ff",
            relief="flat", cursor="hand2", font=("Segoe UI", 8),
            command=self._pick_shadow_color
        )
        self._shadow_btn.pack(side="left", padx=4)

        # Snap positions
        r = self._row(p, pady=(6, 0))
        self._lbl(r, "Posición:", w=12).pack(side="left")
        grid = tk.Frame(r, bg=BG1)
        grid.pack(side="left", padx=4)
        for i, (sym, anchor) in enumerate([
            ("↖","nw"),("↑","n"),("↗","ne"),
            ("←","w"), ("⊙","c"),("→","e"),
            ("↙","sw"),("↓","s"),("↘","se"),
        ]):
            tk.Button(
                grid, text=sym, width=2,
                bg=BG2, fg=TXP, relief="flat", cursor="hand2",
                font=("Segoe UI", 9),
                command=lambda a=anchor: self._snap_text_pos(a)
            ).grid(row=i//3, column=i%3, padx=1, pady=1)

        ttk.Separator(p, orient="horizontal").pack(fill="x", pady=(8, 4))

        # ── Degradado de texto ────────────────────────────────────────────────
        r = self._row(p, pady=(0, 2))
        self._chk(r, "Degradado", self.text_gradient_var,
                  cmd=self._refresh_text_preview).pack(side="left", padx=(0, 8))
        self._grad_btn1 = tk.Button(
            r, text="  ", width=3, bg=self._gradient_color1,
            relief="flat", cursor="hand2", font=("Segoe UI", 8),
            command=self._pick_gradient_color1
        )
        self._grad_btn1.pack(side="left", padx=(0, 2))
        tk.Label(r, text="→", font=("Segoe UI", 10), fg=TXS, bg=BG1).pack(side="left", padx=2)
        self._grad_btn2 = tk.Button(
            r, text="  ", width=3, bg=self._gradient_color2,
            relief="flat", cursor="hand2", font=("Segoe UI", 8),
            command=self._pick_gradient_color2
        )
        self._grad_btn2.pack(side="left", padx=(0, 10))
        self._lbl(r, "Dir:").pack(side="left")
        ttk.Combobox(
            r, textvariable=self.gradient_dir_var,
            values=["vertical", "horizontal"],
            state="readonly", width=10,
            font=("Segoe UI", 9)
        ).pack(side="left", padx=(4, 0))
        self.gradient_dir_var.trace_add("write", lambda *_: self._refresh_text_preview())

        # Quick gradient presets
        r2 = self._row(p, pady=(2, 0))
        self._lbl(r2, "Estilos:", w=12).pack(side="left")
        for label, c1, c2 in [
            ("⚜ Dorado",   "#ffe680", "#7b3000"),
            ("🔥 Fuego",   "#ff6600", "#cc0000"),
            ("❄ Hielo",    "#e0f4ff", "#2266aa"),
            ("🌑 Sombra",  "#ffffff", "#333333"),
        ]:
            self._btn(r2, label, lambda a=c1, b=c2: self._apply_gradient_preset(a, b),
                      bg=BG2, fg=TXS).pack(side="left", padx=(0, 3))
        self._btn(r2, "🎯 Auto", self._auto_gradient_color,
                  bg=BG2, fg=ACC).pack(side="left", padx=(8, 0))

        ttk.Separator(p, orient="horizontal").pack(fill="x", pady=(6, 4))

        # ── Color del contorno ────────────────────────────────────────────────
        r3 = self._row(p, pady=(0, 4))
        self._lbl(r3, "Color contorno:", w=14).pack(side="left")
        self._outline_color_btn = tk.Button(
            r3, text="Auto", width=6,
            bg=BG2, fg=TXS,
            relief="flat", cursor="hand2", font=("Segoe UI", 8),
            command=self._pick_outline_color
        )
        self._outline_color_btn.pack(side="left", padx=(4, 6))
        self._btn(r3, "✕ Reset", self._reset_outline_color, bg=BG2, fg=TXS).pack(side="left")

        # Initialize font preview
        self.after_idle(self._update_font_preview)

    # ── Presets ───────────────────────────────────────────────────────────────

    def _build_presets_card(self, parent):
        p = self._card(parent, "💾  Presets")
        r = self._row(p)
        self._lbl(r, "Perfil:", w=8).pack(side="left")
        self.preset_combo = ttk.Combobox(
            r, textvariable=self.preset_name,
            values=list(self.presets.keys()), width=22
        )
        self.preset_combo.pack(side="left", padx=(4, 6))
        self._btn(r, "Cargar",  self._load_preset,          bg="#1f4e2e", fg=GRN).pack(side="left", padx=2)
        self._btn(r, "Guardar", self._save_current_preset,  bg="#1a3a5e", fg=AC2).pack(side="left", padx=2)
        self._btn(r, "Borrar",  self._delete_preset,        bg="#3d1f1f", fg=RED).pack(side="left", padx=2)

    # ── Acciones ──────────────────────────────────────────────────────────────

    def _build_actions_card(self, parent):
        p = self._card(parent, "▶  Acciones", accent=GRN)
        r1 = self._row(p, pady=(0, 6))
        tk.Button(
            r1, text="👁  Vista previa    Ctrl+P",
            command=self._preview,
            font=("Segoe UI", 10, "bold"),
            bg="#1a3a5e", fg="#88c0d0",
            activebackground="#2a4a7e", activeforeground="#ffffff",
            relief="flat", padx=14, pady=7, cursor="hand2"
        ).pack(side="left", padx=(0, 8))
        tk.Button(
            r1, text="⚙  Convertir    Ctrl+Enter",
            command=self._convert,
            font=("Segoe UI", 10, "bold"),
            bg="#3d2b00", fg=ACC,
            activebackground="#5a4000", activeforeground=ACC,
            relief="flat", padx=14, pady=7, cursor="hand2"
        ).pack(side="left")

        r2 = self._row(p)
        self._btn(r2, "📋 Copiar Clan", lambda: self._copy_to_clipboard("clan"), bg=BG2, fg=ACC).pack(side="left", padx=(0, 6))
        self._btn(r2, "📋 Copiar Ally", lambda: self._copy_to_clipboard("ally"), bg=BG2, fg=AC2).pack(side="left", padx=(0, 16))
        self._chk(r2, "Exportar PNG también", self.export_png_var, cmd=lambda: None).pack(side="left")

        r3 = self._row(p, pady=(6, 0))
        self._btn(r3, "📂 Procesar carpeta…", self._process_batch,
                  bg="#1f3020", fg=GRN).pack(side="left", padx=(0, 8))
        self._btn(r3, "🎮 Enviar al juego", self._send_to_game,
                  bg="#2a1f3d", fg="#c084fc").pack(side="left")

        self._batch_progress = ttk.Progressbar(p, orient="horizontal", mode="determinate", length=200)
        self._batch_progress.pack(fill="x", padx=8, pady=(4, 0))
        self._batch_progress.pack_forget()  # hidden initially

    # ── Source Preview ────────────────────────────────────────────────────────

    def _build_source_preview(self, parent):
        hdr_frame = tk.Frame(parent, bg=BG0)
        hdr_frame.pack(fill="x", pady=(0, 4))
        tk.Label(
            hdr_frame, text="IMAGEN FUENTE  ·  ZONAS DE RECORTE",
            font=("Segoe UI", 8, "bold"), fg=TXS, bg=BG0
        ).pack(side="left")
        self._ba_btn = tk.Button(
            hdr_frame, text="◐ Antes/Después",
            command=self._toggle_before_after,
            bg=BG2, fg=TXS, relief="flat", cursor="hand2",
            font=("Segoe UI", 8), padx=6, pady=2
        )
        self._ba_btn.pack(side="right")
        self._reset_split_btn = tk.Button(
            hdr_frame, text="↔ Reset split",
            command=self._reset_split,
            bg=BG2, fg=TXS, relief="flat", cursor="hand2",
            font=("Segoe UI", 8), padx=6, pady=2
        )
        self._reset_split_btn.pack(side="right", padx=(0, 4))
        outer = tk.LabelFrame(
            parent,
            text="  ■ Dorado = Clan (16×12)     ■ Azul = Ally (8×12)  ",
            fg=TXS, bg=BG1, font=("Segoe UI", 8), relief="solid", bd=1
        )
        outer.pack(fill="both", expand=True)
        self.src_canvas = tk.Canvas(
            outer, width=SOURCE_PREV_W, height=SOURCE_PREV_H,
            bg="#0a0a14", highlightthickness=0
        )
        self.src_canvas.pack(fill="both", expand=True, padx=6, pady=6)
        self.src_canvas.create_text(
            SOURCE_PREV_W // 2, SOURCE_PREV_H // 2,
            text="Cargá una imagen para ver las zonas de recorte",
            fill="#3a3a6e", font=("Segoe UI", 10)
        )
        self.src_canvas.bind("<Button-1>", self._text_drag_start)
        self.src_canvas.bind("<B1-Motion>", self._text_drag_move)
        self.src_canvas.bind("<Shift-Button-1>", self._pick_color_from_image)
        self.src_canvas.bind("<Control-Button-1>", self._start_color_replace)
        self.src_canvas.bind("<Button-3>", self._split_drag_start)
        self.src_canvas.bind("<B3-Motion>", self._split_drag_move)
        self.src_canvas.bind("<ButtonRelease-3>", self._split_drag_end)
        self.src_canvas.bind("<Configure>", self._on_src_canvas_resize)
        self.src_canvas.bind("<Left>",  lambda e: self._nudge_text(-0.01, 0.0))
        self.src_canvas.bind("<Right>", lambda e: self._nudge_text( 0.01, 0.0))
        self.src_canvas.bind("<Up>",    lambda e: self._nudge_text( 0.0, -0.01))
        self.src_canvas.bind("<Down>",  lambda e: self._nudge_text( 0.0,  0.01))
        self.src_canvas.focus_set()
        if _HAS_DND:
            self.src_canvas.drop_target_register(_DND_FILES)
            self.src_canvas.dnd_bind('<<Drop>>', self._on_file_drop)
        tk.Label(parent, text="Shift+click para tomar color  ·  Ctrl+click para reemplazar color  ·  Clic-derecho sobre la línea para mover el split",
                 bg=BG0, fg=TXS, font=("Segoe UI", 7)).pack(anchor="w")

    # ── Result Preview ────────────────────────────────────────────────────────

    def _build_result_preview(self, parent):
        tk.Frame(parent, bg=BG0, height=14).pack()

        bg_row = tk.Frame(parent, bg=BG0)
        bg_row.pack(anchor="w", pady=(0, 6))
        tk.Label(bg_row, text="RESULTADO  ·  Fondo:",
                 font=("Segoe UI", 8, "bold"), fg=TXS, bg=BG0).pack(side="left", padx=(0, 8))
        for lbl, val in [("■ Negro", "black"), ("□ Blanco", "white"), ("▦ Checker", "checker")]:
            tk.Radiobutton(
                bg_row, text=lbl, variable=self.preview_bg_var, value=val,
                font=("Segoe UI", 8), fg=TXS, bg=BG0,
                selectcolor=BG0, activebackground=BG0,
                cursor="hand2", command=self._apply_preview_bg
            ).pack(side="left", padx=3)

        frames_row = tk.Frame(parent, bg=BG0)
        frames_row.pack()

        ally_lf = tk.LabelFrame(
            frames_row, text=" Alliance (8×12) ",
            fg=AC2, bg=BG1, font=("Segoe UI", 9, "bold"), relief="solid", bd=1
        )
        ally_lf.pack(side="left", padx=(0, 12))
        self.ally_canvas = tk.Canvas(
            ally_lf,
            width=ALLY_SIZE[0] * PREVIEW_MULT,
            height=ALLY_SIZE[1] * PREVIEW_MULT,
            bg="black", highlightthickness=0
        )
        self.ally_canvas.pack(padx=6, pady=6)
        self.ally_canvas.bind("<Button-1>", lambda _: self._show_zoom_popup("ally"))

        clan_lf = tk.LabelFrame(
            frames_row, text=" Clan (16×12) ",
            fg=ACC, bg=BG1, font=("Segoe UI", 9, "bold"), relief="solid", bd=1
        )
        clan_lf.pack(side="left")
        self.clan_canvas = tk.Canvas(
            clan_lf,
            width=CLAN_SIZE[0] * PREVIEW_MULT,
            height=CLAN_SIZE[1] * PREVIEW_MULT,
            bg="black", highlightthickness=0
        )
        self.clan_canvas.pack(padx=6, pady=6)
        self.clan_canvas.bind("<Button-1>", lambda _: self._show_zoom_popup("clan"))

        r_pal = tk.Frame(parent, bg=BG0)
        r_pal.pack(anchor="w", pady=(8, 0))
        self._btn(r_pal, "🎨 Ver paleta Clan", lambda: self._show_palette("clan"), bg=BG2, fg=ACC).pack(side="left", padx=(0, 4))
        self._btn(r_pal, "🎨 Ver paleta Ally", lambda: self._show_palette("ally"), bg=BG2, fg=AC2).pack(side="left", padx=(0, 4))
        self._btn(r_pal, "🎮 Ver en juego", self._show_ingame_preview, bg="#1a2030", fg=AC2).pack(side="left", padx=(0, 4))
        self._btn(r_pal, "📋 Historial", self._show_history, bg=BG2, fg=TXS).pack(side="left", padx=(0, 4))

    def _apply_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TEntry",
                        fieldbackground=BG2, foreground=TXP,
                        insertcolor=ACC, bordercolor="#30363d",
                        lightcolor="#30363d", darkcolor="#30363d")
        style.configure("TCombobox",
                        fieldbackground=BG2, foreground=TXP,
                        selectbackground=BG2, selectforeground=TXP,
                        arrowcolor=ACC)
        style.map("TCombobox",
                  fieldbackground=[("readonly", BG2)],
                  foreground=[("readonly", TXP)])
        style.configure("TSeparator", background="#30363d")

    # ── Pantalla completa ─────────────────────────────────────────────────────

    def _toggle_fullscreen(self, _event=None):
        self._fullscreen = not self._fullscreen
        self.attributes("-fullscreen", self._fullscreen)
        label = "⊡  Salir de pantalla completa  [Esc]" if self._fullscreen else "⛶  Pantalla completa  [F11]"
        self._fs_btn.config(text=label, fg=ACC if self._fullscreen else TXS)

    def _exit_fullscreen(self, _event=None):
        if self._fullscreen:
            self._fullscreen = False
            self.attributes("-fullscreen", False)
            self._fs_btn.config(text="⛶  Pantalla completa  [F11]", fg=TXS)

    def _on_src_canvas_resize(self, event):
        if self._resize_after:
            self.after_cancel(self._resize_after)
        self._resize_after = self.after(
            150, self._do_src_canvas_resize, event.width, event.height
        )

    def _do_src_canvas_resize(self, w, h):
        self._resize_after = None
        if w < 80 or h < 40:
            return
        if w == self.src_prev_w and h == self.src_prev_h:
            return
        self.src_prev_w = w
        self.src_prev_h = h
        src = self.src_path.get().strip()
        if src and os.path.isfile(src):
            self._update_source_preview(src)

    # ── Archivos ──────────────────────────────────────────────────────────────

    def _browse_source(self):
        path = filedialog.askopenfilename(
            title="Seleccionar imagen fuente",
            filetypes=[("Imágenes", "*.jpg *.jpeg *.png *.bmp *.tga *.gif *.webp"),
                       ("Todos", "*.*")]
        )
        if not path:
            return
        self.src_path.set(path)
        name = os.path.splitext(os.path.basename(path))[0]
        self.clan_path.set(os.path.join(OUTPUT_DIR, name + "_clan.bmp"))
        self.ally_path.set(os.path.join(OUTPUT_DIR, name + "_ally.bmp"))
        self.status_var.set(f"Imagen cargada: {os.path.basename(path)}")
        self._add_recent(path)
        self.text_pos = (0.5, 0.5)
        self._update_source_preview(path)

    def _browse_clan(self):
        path = filedialog.asksaveasfilename(
            title="Guardar Clan BMP", initialdir=OUTPUT_DIR,
            defaultextension=".bmp", filetypes=[("BMP", "*.bmp")]
        )
        if path:
            self.clan_path.set(path)

    def _browse_ally(self):
        path = filedialog.asksaveasfilename(
            title="Guardar Alliance BMP", initialdir=OUTPUT_DIR,
            defaultextension=".bmp", filetypes=[("BMP", "*.bmp")]
        )
        if path:
            self.ally_path.set(path)

    def _browse_source2(self):
        path = filedialog.askopenfilename(
            title="Seleccionar PNG overlay (Fuente 2)",
            filetypes=[("PNG con transparencia", "*.png"),
                       ("Imágenes", "*.jpg *.jpeg *.png *.bmp *.webp"),
                       ("Todos", "*.*")]
        )
        if path:
            self.src_path2.set(path)
            self._refresh_text_preview()

    def _swap_sources(self):
        a, b = self.src_path.get(), self.src_path2.get()
        self.src_path.set(b)
        self.src_path2.set(a)
        self._refresh_text_preview()

    def _browse_game_path(self):
        path = filedialog.askdirectory(title="Seleccionar carpeta de Lineage 2")
        if path:
            self.game_path.set(path)

    def _add_recent(self, path: str):
        if path in self.recent_files:
            self.recent_files.remove(path)
        self.recent_files.insert(0, path)
        self.recent_files = self.recent_files[:MAX_RECENT]
        self.recent_combo["values"] = self.recent_files
        self.recent_combo.set(path)
        _save_json(RECENT_FILE, self.recent_files)

    def _open_recent(self, _=None):
        path = self.recent_combo.get()
        if not path or not os.path.isfile(path):
            self.status_var.set("Archivo reciente no encontrado.")
            return
        self.src_path.set(path)
        name = os.path.splitext(os.path.basename(path))[0]
        self.clan_path.set(os.path.join(OUTPUT_DIR, name + "_clan.bmp"))
        self.ally_path.set(os.path.join(OUTPUT_DIR, name + "_ally.bmp"))
        self._add_recent(path)
        self._update_source_preview(path)

    # ── Presets ───────────────────────────────────────────────────────────────

    def _get_current_settings(self) -> dict:
        return {
            "text":      self.text_var.get(),
            "text_size": self.text_size.get(),
            "text_pos":  list(self.text_pos),
            "text_spacing":   self.text_spacing.get(),
            "italic":         self.italic_var.get(),
            "bold":           self.bold_var.get(),
            "text_color":     self.text_color,
            "font":           self.selected_font.get(),
            "shadow":         self.shadow_var.get(),
            "shadow_x":       self.shadow_x.get(),
            "shadow_y":       self.shadow_y.get(),
            "shadow_color":   self.shadow_color,
            "brightness":     self.brightness_var.get(),
            "contrast":       self.contrast_var.get(),
            "saturation":     self.saturation_var.get(),
            "hue":            self.hue_var.get(),
            "sharpen":        self.sharpen_var.get(),
            "rotation":       self.rotation_var.get(),
            "flip_h":         self.flip_h_var.get(),
            "flip_v":         self.flip_v_var.get(),
            "text_outline":   self.outline_var.get(),
            "text_opacity":   self.text_opacity_var.get(),
            "text_rotation":  self.text_rotation_var.get(),
        }

    def _apply_settings(self, s: dict):
        self.text_var.set(s.get("text", s.get("clan_text", "")))
        self.text_size.set(s.get("text_size", s.get("clan_text_size", 40)))
        self.text_pos = tuple(s.get("text_pos", s.get("clan_text_pos", [0.5, 0.5])))
        self.text_spacing.set(s.get("text_spacing", 0))
        self.italic_var.set(s.get("italic", False))
        self.bold_var.set(s.get("bold", False))
        self._set_text_color(s.get("text_color", "#ffffff"))
        if s.get("font") in self.font_names:
            self.selected_font.set(s["font"])
        self.shadow_var.set(s.get("shadow", False))
        self.shadow_x.set(s.get("shadow_x", 1))
        self.shadow_y.set(s.get("shadow_y", 1))
        self.shadow_color = s.get("shadow_color", "#000000")
        self._shadow_btn.config(bg=self.shadow_color)
        self.brightness_var.set(s.get("brightness", 1.0))
        self.contrast_var.set(s.get("contrast", 1.0))
        self.saturation_var.set(s.get("saturation", 1.0))
        self.hue_var.set(s.get("hue", 0))
        self.sharpen_var.set(s.get("sharpen", False))
        self.rotation_var.set(s.get("rotation", 0))
        self.flip_h_var.set(s.get("flip_h", False))
        self.flip_v_var.set(s.get("flip_v", False))
        self.outline_var.set(s.get("text_outline", 2))
        self.text_opacity_var.set(s.get("text_opacity", 100))
        self.text_rotation_var.set(s.get("text_rotation", 0))
        self._refresh_text_preview()

    def _save_current_preset(self):
        name = self.preset_name.get().strip()
        if not name:
            messagebox.showwarning("Preset", "Ingresá un nombre para el preset.")
            return
        self.presets[name] = self._get_current_settings()
        _save_json(PRESETS_FILE, self.presets)
        self.preset_combo["values"] = list(self.presets.keys())
        self.status_var.set(f"Preset '{name}' guardado.")

    def _load_preset(self):
        name = self.preset_name.get().strip()
        if name not in self.presets:
            messagebox.showwarning("Preset", f"No existe el preset '{name}'.")
            return
        self._apply_settings(self.presets[name])
        self.status_var.set(f"Preset '{name}' cargado.")

    def _delete_preset(self):
        name = self.preset_name.get().strip()
        if name not in self.presets:
            return
        if messagebox.askyesno("Borrar preset", f"¿Eliminar '{name}'?"):
            del self.presets[name]
            _save_json(PRESETS_FILE, self.presets)
            self.preset_combo["values"] = list(self.presets.keys())
            self.preset_name.set("")
            self.status_var.set(f"Preset '{name}' eliminado.")

    # ── Texto ─────────────────────────────────────────────────────────────────

    def _on_text_change(self):
        if self._text_upd:
            return
        self._text_upd = True
        self.text_var.set(self.text_var.get().upper()[:3])
        self._text_upd = False
        self._refresh_text_preview()
        self._update_font_preview()
        if self._text_prev_after:
            self.after_cancel(self._text_prev_after)
        self._text_prev_after = self.after(500, self._auto_text_preview)

    def _auto_text_preview(self):
        self._text_prev_after = None
        src = self.src_path.get().strip()
        if src and os.path.isfile(src):
            self._run(save=False)

    def _set_text_color(self, color: str):
        self.text_color = color
        for c, btn in self._color_btns.items():
            btn.config(relief="sunken" if c == color else "flat")
        self._refresh_text_preview()

    def _pick_custom_color(self):
        result = colorchooser.askcolor(color=self.text_color, title="Color del texto")
        if result and result[1]:
            self._set_text_color(result[1])
            for btn in self._color_btns.values():
                btn.config(relief="flat")

    def _pick_shadow_color(self):
        result = colorchooser.askcolor(color=self.shadow_color, title="Color de sombra")
        if result and result[1]:
            self.shadow_color = result[1]
            self._shadow_btn.config(bg=self.shadow_color)
            self._refresh_text_preview()


    # ── Gradient + outline color handlers ────────────────────────────────────

    def _pick_gradient_color1(self):
        result = colorchooser.askcolor(color=self._gradient_color1, title="Color degradado — arriba/izquierda")
        if result and result[1]:
            self._gradient_color1 = result[1]
            self._grad_btn1.config(bg=self._gradient_color1)
            self._refresh_text_preview()

    def _pick_gradient_color2(self):
        result = colorchooser.askcolor(color=self._gradient_color2, title="Color degradado — abajo/derecha")
        if result and result[1]:
            self._gradient_color2 = result[1]
            self._grad_btn2.config(bg=self._gradient_color2)
            self._refresh_text_preview()

    def _apply_gradient_preset(self, c1: str, c2: str):
        self._gradient_color1 = c1
        self._gradient_color2 = c2
        self._grad_btn1.config(bg=c1)
        self._grad_btn2.config(bg=c2)
        self.text_gradient_var.set(True)
        self._refresh_text_preview()

    def _auto_gradient_color(self):
        path = self.src_path.get().strip()
        if not path or not os.path.isfile(path):
            self.status_var.set("Cargá una imagen primero.")
            return
        try:
            from PIL import ImageStat
            img = Image.open(path).convert("RGB")
            bv, cv, sv, hv = (self.brightness_var.get(), self.contrast_var.get(),
                               self.saturation_var.get(), self.hue_var.get())
            if bv != 1.0: img = ImageEnhance.Brightness(img).enhance(bv)
            if cv != 1.0: img = ImageEnhance.Contrast(img).enhance(cv)
            if sv != 1.0: img = ImageEnhance.Color(img).enhance(sv)
            if hv != 0:   img = _apply_hue_shift(img, hv)

            sw, sh = img.size
            bx1, by1, bx2, by2 = _combined_base(sw, sh)
            bw = bx2 - bx1
            split = bx1 + bw * self._split_ratio
            crop = img.crop((int(split), int(by1), int(bx2), int(by2)))

            stat = ImageStat.Stat(crop)
            cr, cg, cb = stat.mean
            bg_lum = 0.2126 * cr + 0.7152 * cg + 0.0722 * cb
            bg_hex = "#{:02x}{:02x}{:02x}".format(int(cr), int(cg), int(cb))

            # Hue del fondo para calcular complementario
            h, s, _ = colorsys.rgb_to_hsv(cr / 255, cg / 255, cb / 255)
            comp_h = (h + 0.5) % 1.0

            def _hsv_hex(hh, ss, vv):
                r2, g2, b2 = colorsys.hsv_to_rgb(hh, ss, vv)
                return "#{:02x}{:02x}{:02x}".format(int(r2*255), int(g2*255), int(b2*255))

            # Sugerencia 1: contraste máximo (blanco→negro o negro→blanco según fondo)
            if bg_lum < 128:
                sug1 = ("#ffffff", "#888888", "Contraste alto")
            else:
                sug1 = ("#111111", "#666666", "Contraste alto")

            # Sugerencia 2: complementario al fondo (claro→oscuro en hue opuesto)
            c_light = _hsv_hex(comp_h, max(0.45, s * 0.6), 0.95)
            c_dark  = _hsv_hex(comp_h, min(1.0,  s * 1.2), 0.40)
            sug2 = (c_light, c_dark, "Complementario al fondo")

            # Sugerencia 3: clásico L2 (siempre útil)
            sug3 = ("#ffe680", "#7b3000", "Dorado clásico")

            # Sugerencia 4: según luminancia del fondo
            if bg_lum < 80:
                sug4 = ("#e0f4ff", "#2266aa", "Hielo (fondo oscuro)")
            elif bg_lum < 160:
                sug4 = ("#ffffff", "#e0b84a", "Blanco → Dorado")
            else:
                sug4 = ("#ff6600", "#cc0000", "Fuego (fondo claro)")

            self._show_gradient_recommendation(bg_hex, [sug1, sug2, sug3, sug4])

        except Exception as e:
            self.status_var.set(f"Auto degradado error: {e}")

    def _show_gradient_recommendation(self, bg_hex, suggestions):
        dlg = tk.Toplevel(self, bg=BG0)
        dlg.title("🎯 Degradado recomendado")
        dlg.transient(self)
        dlg.resizable(False, False)
        dlg.grab_set()

        card = tk.Frame(dlg, bg=BG1, padx=16, pady=14)
        card.pack(padx=8, pady=8, fill="both")

        tk.Label(card, text="Degradado según el fondo (zona clan)",
                 font=("Segoe UI", 10, "bold"), fg=ACC, bg=BG1
                 ).pack(anchor="w", pady=(0, 8))

        # Fondo detectado
        r0 = tk.Frame(card, bg=BG1)
        r0.pack(fill="x", pady=(0, 8))
        tk.Label(r0, text="Fondo detectado:", font=("Segoe UI", 9), fg=TXS,
                 bg=BG1, width=17, anchor="w").pack(side="left")
        tk.Label(r0, text="  ", bg=bg_hex, width=3, relief="solid", bd=1
                 ).pack(side="left", padx=(0, 6))
        tk.Label(r0, text=bg_hex, font=("Segoe UI", 9), fg=TXP, bg=BG1
                 ).pack(side="left")

        tk.Frame(card, bg="#30363d", height=1).pack(fill="x", pady=(0, 8))

        selected = tk.IntVar(value=0)
        photos = []  # keep refs to avoid GC

        for i, (c1, c2, label) in enumerate(suggestions):
            row = tk.Frame(card, bg=BG1)
            row.pack(fill="x", pady=4)

            tk.Radiobutton(row, variable=selected, value=i,
                           bg=BG1, activebackground=BG1,
                           selectcolor=BG2, cursor="hand2"
                           ).pack(side="left", padx=(0, 4))

            # Gradient swatch via PIL
            swatch = _make_gradient(110, 18, c1, c2, "horizontal")
            ph = ImageTk.PhotoImage(swatch)
            photos.append(ph)
            tk.Label(row, image=ph, bd=1, relief="solid").pack(side="left", padx=(0, 8))

            tk.Label(row, text=f"{c1} → {c2}",
                     font=("Courier New", 8), fg=TXS, bg=BG1, width=22, anchor="w"
                     ).pack(side="left")
            tk.Label(row, text=label,
                     font=("Segoe UI", 9), fg=TXP, bg=BG1
                     ).pack(side="left")

        dlg._photos = photos  # prevent GC

        tk.Frame(card, bg="#30363d", height=1).pack(fill="x", pady=10)

        btn_row = tk.Frame(card, bg=BG1)
        btn_row.pack()

        def _apply():
            c1, c2, _ = suggestions[selected.get()]
            self._apply_gradient_preset(c1, c2)
            self.status_var.set(f"🎯 Degradado aplicado: {c1} → {c2}")
            dlg.destroy()

        tk.Button(btn_row, text="Aplicar", command=_apply,
                  bg="#1f4e2e", fg=GRN, relief="flat", cursor="hand2",
                  font=("Segoe UI", 9, "bold"), padx=18, pady=6
                  ).pack(side="left", padx=(0, 8))
        tk.Button(btn_row, text="Cancelar", command=dlg.destroy,
                  bg=BG2, fg=TXS, relief="flat", cursor="hand2",
                  font=("Segoe UI", 9), padx=14, pady=6
                  ).pack(side="left")

        dlg.bind("<Return>", lambda _: _apply())
        dlg.bind("<Escape>", lambda _: dlg.destroy())

    def _pick_outline_color(self):
        initial = self._outline_color_val or "#000000"
        result = colorchooser.askcolor(color=initial, title="Color del contorno")
        if result and result[1]:
            self._outline_color_val = result[1]
            self._outline_color_btn.config(bg=self._outline_color_val, fg="#ffffff", text="Custom")
            self._refresh_text_preview()

    def _reset_outline_color(self):
        self._outline_color_val = None
        self._outline_color_btn.config(bg=BG2, fg=TXS, text="Auto")
        self._refresh_text_preview()

    def _auto_text_color(self):
        path = self.src_path.get().strip()
        if not path or not os.path.isfile(path):
            self.status_var.set("Cargá una imagen primero.")
            return
        try:
            from PIL import ImageStat
            img = Image.open(path).convert("RGB")
            bv, cv, sv, hv = (self.brightness_var.get(), self.contrast_var.get(),
                               self.saturation_var.get(), self.hue_var.get())
            if bv != 1.0: img = ImageEnhance.Brightness(img).enhance(bv)
            if cv != 1.0: img = ImageEnhance.Contrast(img).enhance(cv)
            if sv != 1.0: img = ImageEnhance.Color(img).enhance(sv)
            if hv != 0:   img = _apply_hue_shift(img, hv)

            sw, sh = img.size
            bx1, by1, bx2, by2 = _combined_base(sw, sh)
            bw = bx2 - bx1
            split = bx1 + bw * self._split_ratio
            crop = img.crop((int(split), int(by1), int(bx2), int(by2)))

            stat = ImageStat.Stat(crop)
            cr, cg, cb = stat.mean
            bg_lum = 0.2126 * cr + 0.7152 * cg + 0.0722 * cb
            noise  = sum(stat.stddev) / 3

            def _lum(hexcol):
                r, g, b = _hex_to_rgb(hexcol)
                return 0.2126 * r + 0.7152 * g + 0.0722 * b

            def _ratio(l1, l2):
                l1n, l2n = (l1 + 10) / 265, (l2 + 10) / 265
                hi, lo = max(l1n, l2n), min(l1n, l2n)
                return hi / lo

            candidates = ["#ffffff", "#000000", "#e0b84a"]
            ranked = sorted(candidates, key=lambda c: _ratio(bg_lum, _lum(c)), reverse=True)
            best       = ranked[0]
            best_ratio = _ratio(bg_lum, _lum(best))

            outline_pick = "#000000" if bg_lum > 128 else "#ffffff"
            if best == outline_pick:
                outline_pick = "#ffffff" if outline_pick == "#000000" else "#000000"

            if   noise > 55: outline_px = 5
            elif noise > 35: outline_px = 4
            elif noise > 18: outline_px = 3
            else:             outline_px = 2

            bg_hex = "#{:02x}{:02x}{:02x}".format(int(cr), int(cg), int(cb))
            self._show_color_recommendation(
                bg_hex, ranked, best_ratio, _ratio, _lum, bg_lum,
                outline_pick, outline_px, best_ratio < 2.6, noise
            )
            self.status_var.set("🎯 Revisá la recomendación y presioná Aplicar.")
        except Exception as e:
            self.status_var.set(f"Auto color error: {e}")

    def _show_color_recommendation(self, bg_hex, ranked, best_ratio,
                                   _ratio, _lum, bg_lum,
                                   outline_col, outline_px, shadow, noise):
        dlg = tk.Toplevel(self, bg=BG0)
        dlg.title("🎯 Recomendación de color")
        dlg.transient(self)
        dlg.resizable(False, False)
        dlg.grab_set()

        card = tk.Frame(dlg, bg=BG1, padx=16, pady=14)
        card.pack(padx=8, pady=8, fill="both")

        tk.Label(card, text="Análisis del fondo (zona clan)",
                 font=("Segoe UI", 10, "bold"), fg=ACC, bg=BG1
                 ).pack(anchor="w", pady=(0, 8))

        def _row(label, hexcol, note=""):
            r = tk.Frame(card, bg=BG1)
            r.pack(fill="x", pady=3)
            tk.Label(r, text=label, font=("Segoe UI", 9), fg=TXS, bg=BG1,
                     width=17, anchor="w").pack(side="left")
            tk.Label(r, text="  ", bg=hexcol, width=3, relief="solid",
                     bd=1).pack(side="left", padx=(0, 6))
            tk.Label(r, text=hexcol + (f"   {note}" if note else ""),
                     font=("Segoe UI", 9), fg=TXP, bg=BG1).pack(side="left")

        _row("Fondo detectado:", bg_hex)

        tk.Frame(card, bg="#30363d", height=1).pack(fill="x", pady=8)

        tk.Label(card, text="Colores recomendados (por contraste)",
                 font=("Segoe UI", 9, "bold"), fg=TXS, bg=BG1
                 ).pack(anchor="w", pady=(0, 6))

        names = {"#ffffff": "Blanco", "#000000": "Negro", "#e0b84a": "Dorado"}
        for i, col in enumerate(ranked):
            ratio = _ratio(bg_lum, _lum(col))
            badge = "  ← mejor" if i == 0 else ""
            _row(f"  {i+1}. {names.get(col, col)}:", col,
                 f"contraste {ratio:.1f}:1{badge}")

        tk.Frame(card, bg="#30363d", height=1).pack(fill="x", pady=8)

        tk.Label(card, text="Contorno y sombra sugeridos",
                 font=("Segoe UI", 9, "bold"), fg=TXS, bg=BG1
                 ).pack(anchor="w", pady=(0, 6))

        _row("Color contorno:", outline_col, f"grosor {outline_px}px")

        noise_lbl = ("alto — fondo muy texturizado" if noise > 55
                     else "medio" if noise > 25 else "bajo — fondo liso")
        for lbl, val in [
            ("Ruido de fondo:", f"{noise:.0f}  ({noise_lbl})"),
            ("Sombra:",         "✓ activada" if shadow else "✕ sin sombra"),
        ]:
            r2 = tk.Frame(card, bg=BG1)
            r2.pack(fill="x", pady=3)
            tk.Label(r2, text=lbl, font=("Segoe UI", 9), fg=TXS, bg=BG1,
                     width=17, anchor="w").pack(side="left")
            tk.Label(r2, text=val, font=("Segoe UI", 9), fg=TXP, bg=BG1
                     ).pack(side="left")

        tk.Frame(card, bg="#30363d", height=1).pack(fill="x", pady=10)

        btn_row = tk.Frame(card, bg=BG1)
        btn_row.pack()

        best = ranked[0]

        def _apply():
            self._set_text_color(best)
            self._outline_color_val = outline_col
            self._outline_color_btn.config(
                bg=outline_col,
                fg="#ffffff" if outline_col == "#000000" else "#111111",
                text="Auto*"
            )
            self.outline_var.set(outline_px)
            self.shadow_var.set(shadow)
            self._refresh_text_preview()
            self.status_var.set(
                f"🎯 Aplicado: texto {best}  ·  contorno {outline_col} ({outline_px}px)  ·  "
                f"contraste {best_ratio:.1f}:1  ·  ruido {noise:.0f}"
            )
            dlg.destroy()

        tk.Button(btn_row, text="Aplicar", command=_apply,
                  bg="#1f4e2e", fg=GRN, relief="flat", cursor="hand2",
                  font=("Segoe UI", 9, "bold"), padx=18, pady=6
                  ).pack(side="left", padx=(0, 8))
        tk.Button(btn_row, text="Cancelar", command=dlg.destroy,
                  bg=BG2, fg=TXS, relief="flat", cursor="hand2",
                  font=("Segoe UI", 9), padx=14, pady=6
                  ).pack(side="left")

        dlg.bind("<Return>",  lambda _: _apply())
        dlg.bind("<Escape>",  lambda _: dlg.destroy())

    def _snap_text_pos(self, anchor: str):
        self._push_undo()
        m = 0.10
        positions = {
            "nw": (m,   m),   "n":  (0.5, m),   "ne": (1-m, m),
            "w":  (m,   0.5), "c":  (0.5, 0.5), "e":  (1-m, 0.5),
            "sw": (m,   1-m), "s":  (0.5, 1-m), "se": (1-m, 1-m),
        }
        self.text_pos = positions.get(anchor, (0.5, 0.5))
        self._refresh_text_preview()

    # ── Undo / Redo ───────────────────────────────────────────────────────────

    def _push_undo(self):
        snapshot = (self._get_current_settings(), self.text_pos)
        self._undo_stack.append(snapshot)
        if len(self._undo_stack) > 20:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def _undo(self, _=None):
        if not self._undo_stack:
            return
        current = (self._get_current_settings(), self.text_pos)
        self._redo_stack.append(current)
        settings, pos = self._undo_stack.pop()
        self._apply_settings(settings)
        self.text_pos = pos
        self._refresh_text_preview()

    def _redo(self, _=None):
        if not self._redo_stack:
            return
        current = (self._get_current_settings(), self.text_pos)
        self._undo_stack.append(current)
        settings, pos = self._redo_stack.pop()
        self._apply_settings(settings)
        self.text_pos = pos
        self._refresh_text_preview()

    # ── Arrow-key nudge ───────────────────────────────────────────────────────

    def _nudge_text(self, dx: float, dy: float):
        if not self._nudge_pushed:
            self._push_undo()
            self._nudge_pushed = True
        x = max(0.0, min(1.0, self.text_pos[0] + dx))
        y = max(0.0, min(1.0, self.text_pos[1] + dy))
        self.text_pos = (x, y)
        self._refresh_text_preview()

    # ── Font preview ──────────────────────────────────────────────────────────

    def _update_font_preview(self, _=None):
        fp = self._current_font_path()
        sample = self.text_var.get().strip() or "AaBb 123"
        try:
            img = Image.new("RGB", (260, 30), (33, 38, 45))
            draw = ImageDraw.Draw(img)
            font = _font_from_path(fp, 22)
            draw.text((6, 3), sample, font=font, fill=(201, 209, 217))
            self._tk_font_prev_img = ImageTk.PhotoImage(img)
            self._font_prev_lbl.config(image=self._tk_font_prev_img)
        except Exception:
            pass

    # ── Drag & Drop ───────────────────────────────────────────────────────────

    def _on_file_drop(self, event):
        raw = event.data.strip()
        path = raw.strip('{}') if raw.startswith('{') else raw
        if os.path.isfile(path) and path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp')):
            self.src_path.set(path)
            name = os.path.splitext(os.path.basename(path))[0]
            self.clan_path.set(os.path.join(OUTPUT_DIR, name + "_clan.bmp"))
            self.ally_path.set(os.path.join(OUTPUT_DIR, name + "_ally.bmp"))
            self.status_var.set(f"Imagen cargada: {os.path.basename(path)}")
            self._add_recent(path)
            self.text_pos = (0.5, 0.5)
            self._update_source_preview(path)

    # ── Fuentes ───────────────────────────────────────────────────────────────

    def _on_font_selected(self, _=None):
        self._refresh_text_preview()
        self._update_font_preview()

    def _filter_fonts(self, _):
        typed = self.selected_font.get().lower()
        filtered = [n for n in self.font_names if typed in n.lower()]
        self.font_combo["values"] = filtered if filtered else self.font_names

    def _open_font_picker(self):
        if self._font_picker_open:
            return
        self._font_picker_open = True

        ITEM_H = 40
        W      = 430

        dlg = tk.Toplevel(self, bg=BG0)
        dlg.title("Elegir fuente")
        dlg.transient(self)
        dlg.geometry(f"460x560+{self.winfo_x()+120}+{self.winfo_y()+60}")
        dlg.resizable(False, True)

        # ── Barra de búsqueda ──────────────────────────────────────────────
        top_f = tk.Frame(dlg, bg=BG0)
        top_f.pack(fill="x", padx=10, pady=8)
        tk.Label(top_f, text="Buscar:", bg=BG0, fg=TXS,
                 font=("Segoe UI", 9)).pack(side="left")
        search_var = tk.StringVar()
        search_ent = tk.Entry(top_f, textvariable=search_var,
                              bg=BG2, fg=TXP, insertbackground=TXP,
                              relief="flat", bd=4, font=("Segoe UI", 10))
        search_ent.pack(side="left", fill="x", expand=True, padx=(6, 0))
        search_ent.focus_set()

        count_lbl = tk.Label(top_f, bg=BG0, fg=TXS, font=("Segoe UI", 8),
                             text=f"{len(self.font_names)}")
        count_lbl.pack(side="left", padx=(6, 0))

        # ── Canvas + scrollbar ─────────────────────────────────────────────
        cf = tk.Frame(dlg, bg=BG1)
        cf.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        vsb    = ttk.Scrollbar(cf, orient="vertical")
        vsb.pack(side="right", fill="y")
        canvas = tk.Canvas(cf, bg=BG1, highlightthickness=0,
                           yscrollcommand=vsb.set, width=W)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.config(command=canvas.yview)

        current_list: list = []
        img_items:    list = []

        # ── Helpers ────────────────────────────────────────────────────────
        def _hex3(h):
            return tuple(int(h[i:i+2], 16) for i in (1, 3, 5))

        def _render(name: str) -> ImageTk.PhotoImage:
            if name in self._font_thumb_cache:
                return self._font_thumb_cache[name]
            selected = (name == self.selected_font.get())
            bg_col   = _hex3(BG2) if selected else _hex3(BG1)
            img      = Image.new("RGB", (W, ITEM_H - 2), bg_col)
            draw     = ImageDraw.Draw(img)
            fp       = self.font_paths.get(name, "")
            try:
                fnt = _font_from_path(fp, 20)
                draw.text((10, 8), name, font=fnt, fill=_hex3(ACC if selected else TXP))
            except Exception:
                draw.text((10, 10), name, fill=_hex3(TXS))
            ph = ImageTk.PhotoImage(img)
            self._font_thumb_cache[name] = ph
            return ph

        def render_visible(_event=None):
            if not current_list:
                return
            total_h = len(current_list) * ITEM_H
            yv      = canvas.yview()
            y0      = yv[0] * total_h
            y1      = yv[1] * total_h
            i_start = max(0, int(y0 // ITEM_H) - 1)
            i_end   = min(len(current_list), int(y1 // ITEM_H) + 3)
            for i in range(i_start, i_end):
                if i < len(img_items):
                    canvas.itemconfig(img_items[i],
                                      image=_render(current_list[i]))

        def rebuild(names: list):
            nonlocal current_list
            current_list = names
            canvas.delete("all")
            img_items.clear()
            total_h = max(len(names) * ITEM_H, 1)
            canvas.config(scrollregion=(0, 0, W, total_h))
            count_lbl.config(text=str(len(names)))
            for i, name in enumerate(names):
                y       = i * ITEM_H
                tag_r   = f"r{i}"
                tag_i   = f"m{i}"
                is_sel  = (name == self.selected_font.get())
                canvas.create_rectangle(0, y, W, y + ITEM_H - 1,
                                        fill=BG2 if is_sel else BG1,
                                        outline=ACC if is_sel else "",
                                        tags=tag_r)
                iid = canvas.create_image(0, y + 1, anchor="nw", tags=tag_i)
                img_items.append(iid)
                for tag in (tag_r, tag_i):
                    canvas.tag_bind(tag, "<Button-1>",
                                    lambda _e, n=name: _select(n))
                    canvas.tag_bind(tag, "<Enter>",
                                    lambda _e, ri=i, n=name:
                                        canvas.itemconfig(f"r{ri}",
                                            fill=BG2 if n != self.selected_font.get() else BG2))
            render_visible()

        def _select(name: str):
            self.selected_font.set(name)
            self._font_thumb_cache.clear()
            self._on_font_selected()
            on_close()

        def on_search(*_):
            q = search_var.get().strip().lower()
            filtered = ([n for n in self.font_names if q in n.lower()]
                        if q else list(self.font_names))
            rebuild(filtered)
            canvas.yview_moveto(0)

        def on_scroll(event):
            canvas.yview_scroll(-1 * (event.delta // 120), "units")
            render_visible()

        def on_close():
            self._font_picker_open = False
            dlg.destroy()

        search_var.trace_add("write", on_search)
        canvas.bind("<Configure>", render_visible)
        canvas.bind("<MouseWheel>", on_scroll)
        vsb.config(command=lambda *a: [canvas.yview(*a), render_visible()])
        dlg.protocol("WM_DELETE_WINDOW", on_close)

        # ── Construir lista inicial y centrar en fuente seleccionada ───────
        rebuild(list(self.font_names))
        sel = self.selected_font.get()
        if sel in self.font_names:
            idx    = self.font_names.index(sel)
            total  = len(self.font_names) * ITEM_H
            frac   = max(0.0, (idx * ITEM_H - 140) / total)
            canvas.yview_moveto(frac)
            render_visible()

    def _current_font_path(self) -> str:
        return self.font_paths.get(self.selected_font.get(), "")

    # ── Ajustes ───────────────────────────────────────────────────────────────

    def _reset_adjustments(self):
        self.brightness_var.set(1.0)
        self.contrast_var.set(1.0)
        self.saturation_var.set(1.0)
        self.hue_var.set(0)
        self.sharpen_var.set(False)
        self._refresh_text_preview()

    # ── Drag / posición texto ─────────────────────────────────────────────────

    def _refresh_text_preview(self):
        path = self.src_path.get().strip()
        if path and os.path.isfile(path):
            self._update_source_preview(path)

    def _text_drag_start(self, event):
        self._push_undo()
        self._nudge_pushed = False
        self._update_text_pos_from_canvas(event.x, event.y)

    def _text_drag_move(self, event):
        self._update_text_pos_from_canvas(event.x, event.y)

    def _update_text_pos_from_canvas(self, cx: int, cy: int):
        if not self._src_disp_rect:
            return
        off_x, off_y, disp_w, disp_h = self._src_disp_rect
        rel_x = max(0.0, min(1.0, (cx - off_x) / disp_w))
        rel_y = max(0.0, min(1.0, (cy - off_y) / disp_h))

        # Constrain drag to the clan zone so text stays within the crest canvas.
        # Without this, dragging past the right/top/bottom of the combined zone
        # maps to coordinates outside the 256×192 clan canvas and text disappears.
        if self._src_img_size:
            try:
                src_w, src_h = self._src_img_size
                bx1, by1, bx2, by2 = _combined_base(src_w, src_h)
                bw = bx2 - bx1
                cl_split   = bx1 + bw * _split_ratio
                cl_x_left  = cl_split / src_w
                cl_x_right = bx2    / src_w
                cl_y_top   = by1    / src_h
                cl_y_bot   = by2    / src_h
                # Italic shear shifts the top of each character rightward by
                # ~0.30 × sh (≈57 px) in the actual 256-wide crest canvas.
                # Subtract that margin from the right limit to prevent the
                # character top from being clipped off the crest edge.
                if self.italic_var.get():
                    sw_c = CLAN_SIZE[0] * SUPER_SAMPLE   # 256
                    sh_c = ALLY_SIZE[1] * SUPER_SAMPLE   # 192
                    shear_px = 0.30 * sh_c               # ≈ 57.6
                    crop_w   = bx2 - cl_split
                    cl_x_right -= (shear_px / sw_c) * (crop_w / src_w)
                rel_x = max(cl_x_left, min(cl_x_right, rel_x))
                rel_y = max(cl_y_top,  min(cl_y_bot,   rel_y))
            except Exception:
                pass

        self.text_pos = (rel_x, rel_y)
        self._refresh_text_preview()
        if self._drag_preview_after:
            self.after_cancel(self._drag_preview_after)
        self._drag_preview_after = self.after(250, lambda: self._run(save=False))

    # ── Source preview ────────────────────────────────────────────────────────

    def _update_source_preview(self, src_path: str):
        try:
            img = Image.open(src_path).convert("RGBA")
            # Compositar Fuente 2 si existe
            src2 = self.src_path2.get().strip()
            if src2 and os.path.isfile(src2):
                ov = Image.open(src2).convert("RGBA")
                if ov.size != img.size:
                    ov = ov.resize(img.size, Image.LANCZOS)
                img = Image.alpha_composite(img, ov)
            img = img.convert("RGB")
            rot = self.rotation_var.get()
            if rot:
                img = img.rotate(-rot, expand=True)
            if self.flip_h_var.get():
                img = img.transpose(Image.FLIP_LEFT_RIGHT)
            if self.flip_v_var.get():
                img = img.transpose(Image.FLIP_TOP_BOTTOM)
            src_w, src_h = img.size
            self._src_img_size = (src_w, src_h)

            bv = self.brightness_var.get()
            cv = self.contrast_var.get()
            sv = self.saturation_var.get()
            hv = self.hue_var.get()
            if not self._before_after_mode:
                if bv != 1.0: img = ImageEnhance.Brightness(img).enhance(bv)
                if cv != 1.0: img = ImageEnhance.Contrast(img).enhance(cv)
                if sv != 1.0: img = ImageEnhance.Color(img).enhance(sv)
                if hv != 0:   img = _apply_hue_shift(img.convert("RGB"), hv)
                if self._color_replacements:
                    _arr = list(img.convert("RGB").getdata())
                    _new = []
                    for _px in _arr:
                        _rp, _gp, _bp = _px[0], _px[1], _px[2]
                        _ok = False
                        for (_r1, _g1, _b1), (_nr, _ng, _nb), _tol in self._color_replacements:
                            if abs(_rp-_r1) + abs(_gp-_g1) + abs(_bp-_b1) <= _tol * 3:
                                _new.append((_nr, _ng, _nb))
                                _ok = True
                                break
                        if not _ok:
                            _new.append((_rp, _gp, _bp))
                    img = img.convert("RGB")
                    img.putdata(_new)

            pw, ph = self.src_prev_w, self.src_prev_h
            scale  = min(pw / src_w, ph / src_h)
            disp_w = int(src_w * scale)
            disp_h = int(src_h * scale)
            off_x  = (pw - disp_w) // 2
            off_y  = (ph - disp_h) // 2
            self._src_disp_rect = (off_x, off_y, disp_w, disp_h)

            bg = Image.new("RGB", (pw, ph), (10, 10, 20))
            bg.paste(img.resize((disp_w, disp_h), Image.LANCZOS), (off_x, off_y))

            def to_canvas(box):
                x1, y1, x2, y2 = box
                return (off_x + int(x1*scale), off_y + int(y1*scale),
                        off_x + int(x2*scale)-1, off_y + int(y2*scale)-1)

            clan_box = to_canvas(_crop_box(src_w, src_h, *CLAN_SIZE, align="clan"))
            ally_box = to_canvas(_crop_box(src_w, src_h, *ALLY_SIZE, align="ally"))

            # Bounding box combinada (ally + clan = canvas 24:12 sin solapamiento)
            cmb_x1 = min(ally_box[0], clan_box[0])
            cmb_y1 = min(ally_box[1], clan_box[1])
            cmb_x2 = max(ally_box[2], clan_box[2])
            cmb_y2 = max(ally_box[3], clan_box[3])

            overlay = Image.new("RGBA", (pw, ph), (0,0,0,0))
            ov = ImageDraw.Draw(overlay)
            dark = (0, 0, 0, 160)
            if cmb_x1 > off_x:
                ov.rectangle([off_x, off_y, cmb_x1-1, off_y+disp_h-1], fill=dark)
            if cmb_x2 < off_x+disp_w-1:
                ov.rectangle([cmb_x2+1, off_y, off_x+disp_w-1, off_y+disp_h-1], fill=dark)
            if cmb_y1 > off_y:
                ov.rectangle([off_x, off_y, off_x+disp_w-1, cmb_y1-1], fill=dark)
            if cmb_y2 < off_y+disp_h-1:
                ov.rectangle([off_x, cmb_y2+1, off_x+disp_w-1, off_y+disp_h-1], fill=dark)
            ov.rectangle(clan_box, outline=(230, 184, 74, 255), width=2)
            ov.rectangle(ally_box, outline=(88, 166, 255, 255), width=2)

            result_rgba = Image.alpha_composite(bg.convert("RGBA"), overlay)

            if not self._before_after_mode:
                r, g, b = _hex_to_rgb(self.text_color)
                fp = self._current_font_path()
                sp = self.text_spacing.get()
                _bold = self.bold_var.get()
                text_layer = Image.new("RGBA", (pw, ph), (0,0,0,0))
                td = ImageDraw.Draw(text_layer)
                zt = self.text_var.get().strip()
                if zt:
                    # Build list of (char_str, px_x, px_y, font, bold_stroke)
                    _items = []
                    if self._smart_layout_active:
                        for _ch, (_rx, _ry), _spct in self._get_smart_layout_texts(zt):
                            _itx = off_x + int(_rx * disp_w)
                            _ity = off_y + int(_ry * disp_h)
                            _ifs = max(8, int(disp_h * _spct / 100))
                            _ibsw = max(1, _ifs // 45) if _bold else 0
                            _items.append((_ch, _itx, _ity, _font_from_path(fp, _ifs), _ibsw))
                    else:
                        _fs  = max(8, int(disp_h * self.text_size.get() / 100))
                        _itx = off_x + int(self.text_pos[0] * disp_w)
                        _ity = off_y + int(self.text_pos[1] * disp_h)
                        _bsw = max(1, _fs // 45) if _bold else 0
                        _items.append((zt, _itx, _ity, _font_from_path(fp, _fs), _bsw))

                    for _ch, _itx, _ity, _fnt, _bsw in _items:
                        if self.shadow_var.get():
                            sr2, sg2, sb2 = _hex_to_rgb(self.shadow_color)
                            _draw_chars(td, _ch, _fnt,
                                        _itx + self.shadow_x.get(),
                                        _ity + self.shadow_y.get(),
                                        sp, (sr2, sg2, sb2, 180), stroke_w=_bsw)
                        if self.text_gradient_var.get():
                            _fl = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
                            _fd = ImageDraw.Draw(_fl)
                            _draw_chars(_fd, _ch, _fnt, _itx, _ity, sp,
                                        (255, 255, 255, 255), stroke_w=_bsw)
                            _, _, _, _fa = _fl.split()
                            _bb = _fa.getbbox()
                            if _bb:
                                _gx1, _gy1, _gx2, _gy2 = _bb
                                _gw, _gh = max(1, _gx2-_gx1), max(1, _gy2-_gy1)
                                _gtile = _make_gradient(_gw, _gh, self._gradient_color1,
                                                        self._gradient_color2, self.gradient_dir_var.get())
                                _r2g, _g2g, _b2g = _hex_to_rgb(self._gradient_color2)
                                _gfull = Image.new("RGB", (pw, ph), (_r2g, _g2g, _b2g))
                                _gfull.paste(_gtile, (_gx1, _gy1))
                                _grba = _gfull.convert("RGBA")
                                _grba.putalpha(_fa)
                                text_layer = Image.alpha_composite(text_layer, _grba)
                        else:
                            _draw_chars(td, _ch, _fnt, _itx, _ity, sp,
                                        (r, g, b, 255), stroke_w=_bsw)
                if self.text_rotation_var.get() != 0:
                    text_layer = text_layer.rotate(-self.text_rotation_var.get(), expand=False, resample=Image.BICUBIC)
                if self.italic_var.get():
                    text_layer = _apply_italic(text_layer)
                result_rgba = Image.alpha_composite(result_rgba, text_layer)
                if self.text_var.get().strip():
                    tx_ch = off_x + int(self.text_pos[0] * disp_w)
                    ty_ch = off_y + int(self.text_pos[1] * disp_h)
                    cross_layer = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
                    cd = ImageDraw.Draw(cross_layer)
                    arm = 10
                    ch_col = (255, 220, 50, 200)
                    cd.line([(tx_ch - arm, ty_ch), (tx_ch + arm, ty_ch)], fill=ch_col, width=1)
                    cd.line([(tx_ch, ty_ch - arm), (tx_ch, ty_ch + arm)], fill=ch_col, width=1)
                    result_rgba = Image.alpha_composite(result_rgba, cross_layer)
            else:
                orig_layer = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
                od = ImageDraw.Draw(orig_layer)
                od.rectangle([off_x+4, off_y+4, off_x+76, off_y+18], fill=(0, 0, 0, 160))
                od.text((off_x+6, off_y+5), "ORIGINAL", fill=(255, 255, 255, 220))
                result_rgba = Image.alpha_composite(result_rgba, orig_layer)

            # Línea divisora ally|clan con handle arrastrable (clic derecho)
            try:
                _bx1, _by1, _bx2, _by2 = _combined_base(src_w, src_h)
                _bw = _bx2 - _bx1
                _split_x_src = _bx1 + _bw * _split_ratio
                _split_cx = off_x + int(_split_x_src * scale)
                _top_y = off_y + int(_by1 * scale)
                _bot_y = off_y + int(_by2 * scale)
                _handle_y = (_top_y + _bot_y) // 2
                _sl = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
                _sd = ImageDraw.Draw(_sl)
                _sd.line([(_split_cx, _top_y), (_split_cx, _bot_y)],
                         fill=(255, 255, 255, 110), width=2)
                _sd.ellipse([_split_cx-7, _handle_y-7, _split_cx+7, _handle_y+7],
                            fill=(255, 255, 255, 160), outline=(230, 184, 74, 220))
                result_rgba = Image.alpha_composite(result_rgba, _sl)
            except Exception:
                pass

            self._tk_src = ImageTk.PhotoImage(result_rgba.convert("RGB"))
            self.src_canvas.delete("all")
            self.src_canvas.create_image(0, 0, anchor="nw", image=self._tk_src)
        except Exception:
            pass

    # ── Result preview BG ─────────────────────────────────────────────────────

    def _apply_preview_bg(self):
        bg = self.preview_bg_var.get()
        color = {"black": "#000000", "white": "#ffffff"}.get(bg, "#555555")
        for canvas in [self.clan_canvas, self.ally_canvas]:
            canvas.config(bg=color)
        self._redraw_result_canvases()

    def _draw_checker(self, canvas, w, h):
        sz = 20
        for row in range(0, h, sz):
            for col in range(0, w, sz):
                c = "#444" if (row//sz + col//sz) % 2 == 0 else "#666"
                canvas.create_rectangle(col, row, col+sz, row+sz, fill=c, outline="")

    def _redraw_result_canvases(self):
        bg = self.preview_bg_var.get()
        for canvas, size, img, tkimg_attr in [
            (self.clan_canvas, CLAN_SIZE, self._last_clan_img, "_tk_clan"),
            (self.ally_canvas, ALLY_SIZE, self._last_ally_img, "_tk_ally"),
        ]:
            canvas.delete("all")
            if bg == "checker":
                self._draw_checker(canvas, size[0]*PREVIEW_MULT, size[1]*PREVIEW_MULT)
            if img is not None:
                tkimg = ImageTk.PhotoImage(img)
                setattr(self, tkimg_attr, tkimg)
                canvas.create_image(0, 0, anchor="nw", image=tkimg)

    # ── Copy to clipboard ─────────────────────────────────────────────────────

    def _copy_to_clipboard(self, zone: str):
        img = self._last_clan_img if zone == "clan" else self._last_ally_img
        if img is None:
            messagebox.showinfo("Portapapeles", "Generá una vista previa primero.")
            return
        try:
            _copy_image_to_clipboard(img)
            name = "Clan" if zone == "clan" else "Ally"
            self.status_var.set(f"✔ {name} copiado al portapapeles.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo copiar al portapapeles:\n{e}")

    # ── Auto-fit ──────────────────────────────────────────────────────────────

    def _auto_fit(self):
        text = self.text_var.get().strip()
        if not text:
            self.status_var.set("Escribí las letras primero.")
            return
        try:
            n   = len(text)
            fp  = self._current_font_path()
            ss  = SUPER_SAMPLE
            fw, fh = CLAN_SIZE          # 16 × 12 final pixels
            ss_w, ss_h = fw * ss, fh * ss  # 256 × 192 super-sample

            # ── Medir aspect ratio real del font ──────────────────────────────
            _test_sz = 128
            _dummy   = Image.new("RGBA", (1, 1))
            _dd      = ImageDraw.Draw(_dummy)
            _ft      = _font_from_path(fp, _test_sz)
            _ws      = [max(1, _dd.textbbox((0, 0), c, font=_ft)[2]) for c in text]
            _hs      = [max(1, _dd.textbbox((0, 0), c, font=_ft)[3] -
                              _dd.textbbox((0, 0), c, font=_ft)[1]) for c in text]
            avg_char_w = sum(_ws) / len(_ws)
            avg_char_h = sum(_hs) / len(_hs)

            # ── Tamaño limitado por ALTURA (dejar margen ascendentes/descend.) ─
            # font_size en super-sample ≈ avg_char_h * (test_sz / avg_char_h) * factor
            # Queremos avg_char_h_render ≤ ss_h * 0.80
            h_factor = avg_char_h / _test_sz           # proporción glifo/tamaño
            size_by_h = int(ss_h * 0.80 / h_factor)   # font_size ss que da 80% alto

            # ── Tamaño limitado por ANCHO ──────────────────────────────────────
            # Ancho total: n * char_w + (n-1) * gap_mínimo (1px final = ss pixels)
            # char_w = font_size * (avg_char_w / test_sz)
            # gap_min = ss   (1 px final entre chars)
            w_factor = avg_char_w / _test_sz           # proporción ancho/tamaño
            usable_w = ss_w * 0.90 - (n - 1) * ss     # espacio para todos los chars
            size_by_w = int(usable_w / (n * w_factor)) if w_factor > 0 else size_by_h

            # ── Tamaño óptimo y conversión a % ────────────────────────────────
            opt_ss = max(4 * ss, min(size_by_h, size_by_w))
            opt_pct = max(10, min(95, round(opt_ss / ss_h * 100)))

            # ── Outline automático — inversamente proporcional a n ─────────────
            # Más chars → contorno más fino para evitar que se peguen
            outline_map = {1: 5, 2: 3, 3: 2}
            opt_outline = outline_map.get(n, 2)

            # ── Píxeles finales estimados por char ─────────────────────────────
            final_px_h = round(opt_ss * h_factor / ss)
            final_px_w = round(opt_ss * w_factor / ss)

            self.text_size.set(opt_pct)
            self.outline_var.set(opt_outline)
            self._refresh_text_preview()

            warn = "  ⚠ puede ser ilegible" if final_px_w < 4 else ""
            self.status_var.set(
                f"Auto: {opt_pct}%  ·  contorno {opt_outline}"
                f"  ·  ≈{final_px_w}×{final_px_h}px/char{warn}"
            )
        except Exception as e:
            self.status_var.set(f"Error en auto: {e}")

    # ── Smart layout de iniciales ─────────────────────────────────────────────

    def _get_smart_layout_texts(self, text: str) -> list:
        """
        Retorna lista de (char, (rel_x, rel_y), size_pct) en coordenadas
        relativas al crop box (0-1).  Usa geometría óptima según n chars:
          n=1 → centrado grande
          n=2 → dos columnas iguales
          n=3 → primera letra grande izquierda + dos apiladas a la derecha
        """
        n = min(len(text), 3)
        if n == 1:
            return [(text[0], (0.50, 0.50), 82)]
        if n == 2:
            # Dos mitades iguales, centrado vertical
            return [
                (text[0], (0.27, 0.50), 72),
                (text[1], (0.73, 0.50), 72),
            ]
        # n == 3 — layout asimétrico: 1 grande + 2 apiladas
        # Letra principal: ocupa lado izquierdo, altura completa
        # Dos letras pequeñas: lado derecho, filas superior e inferior
        #   ┌─────┬─────┐
        #   │     │  B  │  ← 28% del alto (y≈0.28)
        #   │  A  ├─────┤
        #   │     │  C  │  ← 72% del alto (y≈0.72)
        #   └─────┴─────┘
        size_big   = 75    # % de sh
        size_small = 40    # % de sh
        return [
            (text[0], (0.27, 0.50), size_big),
            (text[1], (0.73, 0.28), size_small),
            (text[2], (0.73, 0.72), size_small),
        ]

    def _apply_smart_layout(self):
        text = self.text_var.get().strip()
        if not text:
            self.status_var.set("Escribí las letras primero.")
            return
        self._smart_layout_active = True
        self._smart_layout_btn.config(bg="#3a3018", fg=ACC)
        self._run(save=False)
        n = min(len(text), 3)
        layouts = {1: "centrado", 2: "columnas iguales", 3: "1 grande + 2 apiladas"}
        self.status_var.set(f"Smart layout: {layouts[n]}  ·  Ctrl+P para actualizar")

    def _clear_smart_layout(self):
        self._smart_layout_active = False
        self._smart_layout_btn.config(bg=BG2, fg=TXS)
        self._run(save=False)
        self.status_var.set("Layout normal restaurado.")

    # ── Conversión ────────────────────────────────────────────────────────────

    def _preview(self):
        self._run(save=False)

    def _convert(self):
        self._run(save=True)

    def _run(self, save: bool):
        self._push_undo()
        src  = self.src_path.get().strip()
        clan = self.clan_path.get().strip()
        ally = self.ally_path.get().strip()
        if not src:
            messagebox.showerror("Error", "Seleccioná una imagen fuente.")
            return
        if not os.path.isfile(src):
            messagebox.showerror("Error", f"No se encontró:\n{src}")
            return
        if save and not clan and not ally:
            messagebox.showerror("Error", "Ingresá al menos un archivo de salida.")
            return
        if save:
            os.makedirs(OUTPUT_DIR, exist_ok=True)

        common_kw = self._common_kw()
        common_kw["overlay_path"] = self.src_path2.get().strip() or None
        do_png = self.export_png_var.get() and save
        bg_mode = self.preview_bg_var.get()
        errors = []

        _t = self.text_var.get().strip()
        if _t and self._smart_layout_active:
            _texts_clan = self._get_smart_layout_texts(_t)
            # Ally: solo primera letra grande centrada (8×12 es muy estrecho)
            _texts_ally = [(_t[0], (0.50, 0.50), 82)]
            _texts_relative = True
        else:
            _texts_clan = [(_t, self.text_pos, self.text_size.get())] if _t else []
            _texts_ally  = _texts_clan
            _texts_relative = False

        def _process(dest_path, size, align, texts, texts_rel):
            img_p = image_to_l2_bmp(
                src, dest_path, size, align=align,
                texts=texts, texts_are_crop_relative=texts_rel, **common_kw
            )
            if do_png and dest_path:
                make_preview(img_p, PREVIEW_MULT).save(
                    os.path.splitext(dest_path)[0] + ".png", format="PNG"
                )
            return img_p

        clan_dest = clan if save else None
        if clan or not save:
            try:
                img_p = _process(clan_dest, CLAN_SIZE, "clan", _texts_clan, _texts_relative)
                prev = make_preview(img_p, PREVIEW_MULT)
                self._last_clan_img = prev
                self._tk_clan = ImageTk.PhotoImage(prev)
                self.clan_canvas.delete("all")
                if bg_mode == "checker":
                    self._draw_checker(self.clan_canvas, CLAN_SIZE[0]*PREVIEW_MULT, CLAN_SIZE[1]*PREVIEW_MULT)
                self.clan_canvas.create_image(0, 0, anchor="nw", image=self._tk_clan)
            except Exception as e:
                errors.append(f"Clan: {e}")

        ally_dest = ally if save else None
        if ally or not save:
            try:
                img_p = _process(ally_dest, ALLY_SIZE, "ally", _texts_ally, _texts_relative)
                prev = make_preview(img_p, PREVIEW_MULT)
                self._last_ally_img = prev
                self._tk_ally = ImageTk.PhotoImage(prev)
                self.ally_canvas.delete("all")
                if bg_mode == "checker":
                    self._draw_checker(self.ally_canvas, ALLY_SIZE[0]*PREVIEW_MULT, ALLY_SIZE[1]*PREVIEW_MULT)
                self.ally_canvas.create_image(0, 0, anchor="nw", image=self._tk_ally)
            except Exception as e:
                errors.append(f"Ally: {e}")

        if save and not errors and self._last_clan_img and self._last_ally_img:
            import datetime
            self._export_history.insert(0, {
                "clan":     self._last_clan_img.copy(),
                "ally":     self._last_ally_img.copy(),
                "settings": self._get_current_settings(),
                "src":      self.src_path.get(),
                "time":     datetime.datetime.now().strftime("%H:%M:%S"),
            })
            self._export_history = self._export_history[:10]

        if errors:
            messagebox.showerror("Error" if save else "Error en preview", "\n".join(errors))
        elif save:
            salidas = [os.path.basename(p) for p in [clan, ally] if p]
            self.status_var.set("✔ Convertido: " + " · ".join(salidas))
            messagebox.showinfo("Listo", "¡Crests generados!\n\n" + "\n".join(
                ([f"Clan → {clan}"] if clan else []) +
                ([f"Ally → {ally}"] if ally else []) +
                ([f"(+ PNG exportado)"] if do_png else [])
            ))
        else:
            self.status_var.set("Vista previa lista  |  Ctrl+P = preview  |  Ctrl+Enter = convertir")

    # ── Zoom popup ────────────────────────────────────────────────────────────

    def _show_zoom_popup(self, zone: str):
        img = self._last_clan_img if zone == "clan" else self._last_ally_img
        if img is None:
            messagebox.showinfo("Zoom", "Generá una vista previa primero.")
            return
        size = CLAN_SIZE if zone == "clan" else ALLY_SIZE
        zoomed = img.resize((size[0] * ZOOM_MULT, size[1] * ZOOM_MULT), Image.NEAREST)

        popup = tk.Toplevel(self)
        popup.title(f"Zoom ×{ZOOM_MULT}  ·  {'Clan 16×12' if zone=='clan' else 'Ally 8×12'}")
        popup.configure(bg=BG0)
        popup.resizable(False, False)

        w, h = zoomed.size
        canvas = tk.Canvas(popup, width=w, height=h, bg="black", highlightthickness=0)
        canvas.pack(padx=8, pady=8)

        tkimg = ImageTk.PhotoImage(zoomed)
        popup._tkimg = tkimg   # evitar garbage collection
        canvas.create_image(0, 0, anchor="nw", image=tkimg)

        # Grilla de píxeles
        for x in range(0, w, ZOOM_MULT):
            canvas.create_line(x, 0, x, h, fill="#333333", width=1)
        for y in range(0, h, ZOOM_MULT):
            canvas.create_line(0, y, w, y, fill="#333333", width=1)

        tk.Label(popup,
                 text=f"Cada celda = 1 px real  ·  Click fuera para cerrar",
                 font=("Segoe UI", 8), fg=TXS, bg=BG0).pack(pady=(0, 6))
        popup.bind("<Escape>", lambda _: popup.destroy())
        popup.bind("<Button-1>", lambda _: popup.destroy())

    # ── Batch processing ──────────────────────────────────────────────────────

    def _process_batch(self):
        folder = filedialog.askdirectory(title="Seleccionar carpeta con imágenes fuente")
        if not folder:
            return
        exts = {".jpg", ".jpeg", ".png", ".bmp", ".tga", ".gif", ".webp"}
        files = [f for f in os.listdir(folder)
                 if os.path.splitext(f)[1].lower() in exts]
        if not files:
            messagebox.showinfo("Batch", "No se encontraron imágenes en la carpeta.")
            return
        if not messagebox.askyesno("Batch",
            f"Se procesarán {len(files)} imagen(es).\n"
            f"Salida → {OUTPUT_DIR}\n\n¿Continuar?"):
            return

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        common_kw = self._common_kw()
        common_kw["overlay_path"] = self.src_path2.get().strip() or None
        ok = errors = 0
        _bt = self.text_var.get().strip()
        _batch_texts = [(_bt, self.text_pos, self.text_size.get())] if _bt else []

        self._batch_progress.pack(fill="x", padx=8, pady=(4, 0))
        self._batch_progress["maximum"] = len(files)
        self._batch_progress["value"] = 0

        for i, fname in enumerate(files, 1):
            src = os.path.join(folder, fname)
            name = os.path.splitext(fname)[0]
            self.status_var.set(f"Procesando {i}/{len(files)}: {fname}…")
            self.update_idletasks()
            try:
                for dest_sfx, size, align in [
                    ("_clan", CLAN_SIZE, "clan"),
                    ("_ally", ALLY_SIZE, "ally"),
                ]:
                    dest = os.path.join(OUTPUT_DIR, name + dest_sfx + ".bmp")
                    image_to_l2_bmp(src, dest, size, align=align,
                                    texts=_batch_texts, **common_kw)
                ok += 1
            except Exception as e:
                errors += 1
                print(f"Error en {fname}: {e}")
            self._batch_progress["value"] = i
            self.update_idletasks()

        self._batch_progress.pack_forget()
        self.status_var.set(f"Batch listo: {ok} OK · {errors} errores → {OUTPUT_DIR}")
        messagebox.showinfo("Batch completado",
                            f"✔ {ok} imagen(es) convertidas\n"
                            f"✖ {errors} error(es)\n\nSalida: {OUTPUT_DIR}")

    # ── Enviar al juego ────────────────────────────────────────────────────────

    def _detect_l2_path(self) -> str:
        candidates = [
            r"C:\Program Files\Lineage II",
            r"C:\Program Files (x86)\Lineage II",
            r"C:\Lineage II",
            r"D:\Lineage II",
            r"E:\Lineage II",
        ]
        for p in candidates:
            if os.path.isdir(p):
                return p
        return ""

    def _send_to_game(self):
        game_dir = self.game_path.get().strip()
        if not game_dir or not os.path.isdir(game_dir):
            messagebox.showerror("Error",
                "Configurá la carpeta de Lineage 2 en el campo 'Carpeta L2'.")
            return
        clan = self.clan_path.get().strip()
        ally = self.ally_path.get().strip()
        sent = []
        for src_bmp in [clan, ally]:
            if src_bmp and os.path.isfile(src_bmp):
                import shutil
                dest = os.path.join(game_dir, os.path.basename(src_bmp))
                shutil.copy2(src_bmp, dest)
                sent.append(os.path.basename(src_bmp))
        if sent:
            self.status_var.set(f"✔ Enviado al juego: {' · '.join(sent)}")
            messagebox.showinfo("Enviado", f"Copiado a {game_dir}:\n" + "\n".join(sent))
        else:
            messagebox.showwarning("Enviar al juego",
                "Convertí primero los crests antes de enviarlos.")

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
        except Exception:
            pass

    # ── Feature 1: Color picker (Shift+click) ────────────────────────────────

    def _pick_color_from_image(self, event):
        if not self._src_disp_rect or not self.src_path.get():
            return
        off_x, off_y, disp_w, disp_h = self._src_disp_rect
        src_w, src_h = self._src_img_size
        px = max(0, min(src_w - 1, int((event.x - off_x) / disp_w * src_w)))
        py = max(0, min(src_h - 1, int((event.y - off_y) / disp_h * src_h)))
        try:
            img = Image.open(self.src_path.get()).convert("RGB")
            bv, cv, sv, hv = (self.brightness_var.get(), self.contrast_var.get(),
                              self.saturation_var.get(), self.hue_var.get())
            if bv != 1.0: img = ImageEnhance.Brightness(img).enhance(bv)
            if cv != 1.0: img = ImageEnhance.Contrast(img).enhance(cv)
            if sv != 1.0: img = ImageEnhance.Color(img).enhance(sv)
            if hv != 0:   img = _apply_hue_shift(img, hv)
            r, g, b = img.getpixel((px, py))
            color = f"#{r:02x}{g:02x}{b:02x}"
            self._set_text_color(color)
            for btn in self._color_btns.values():
                btn.config(relief="flat")
            self.status_var.set(f"Color tomado: {color.upper()}")
        except Exception as e:
            self.status_var.set(f"Error al tomar color: {e}")

    # ── Feature 2: Reemplazo de color (Ctrl+click) ───────────────────────────

    def _start_color_replace(self, event):
        if not self._src_disp_rect or not self.src_path.get():
            return
        off_x, off_y, disp_w, disp_h = self._src_disp_rect
        src_w, src_h = self._src_img_size
        px = max(0, min(src_w - 1, int((event.x - off_x) / disp_w * src_w)))
        py = max(0, min(src_h - 1, int((event.y - off_y) / disp_h * src_h)))
        try:
            img = Image.open(self.src_path.get()).convert("RGB")
            src_color = img.getpixel((px, py))
            hex_src = f"#{src_color[0]:02x}{src_color[1]:02x}{src_color[2]:02x}"
            result = colorchooser.askcolor(color=hex_src,
                title=f"Reemplazar {hex_src.upper()} con:")
            if result and result[0]:
                new_rgb = tuple(int(c) for c in result[0])
                self._color_replacements.append((src_color, new_rgb, 30))
                self._repl_btn.config(
                    text=f"Reemplazos ({len(self._color_replacements)})",
                    fg=ACC
                )
                self._refresh_text_preview()
                self._run(save=False)
        except Exception as e:
            self.status_var.set(f"Error en reemplazo: {e}")

    def _show_replacements_popup(self):
        dlg = tk.Toplevel(self, bg=BG0)
        dlg.title("Reemplazos de color")
        dlg.transient(self)
        dlg.resizable(False, False)
        if not self._color_replacements:
            tk.Label(dlg,
                     text="No hay reemplazos activos.\nCtrl+click en la imagen para agregar.",
                     bg=BG0, fg=TXS, font=("Segoe UI", 9),
                     padx=20, pady=20).pack()
            dlg.bind("<Escape>", lambda _: dlg.destroy())
            return
        tk.Label(dlg, text="Reemplazos activos — click ✕ para eliminar:",
                 bg=BG0, fg=TXS, font=("Segoe UI", 8), padx=12, pady=6).pack(anchor="w")
        for i, (src_c, dst_c, tol) in enumerate(list(self._color_replacements)):
            src_hex = f"#{src_c[0]:02x}{src_c[1]:02x}{src_c[2]:02x}"
            dst_hex = f"#{dst_c[0]:02x}{dst_c[1]:02x}{dst_c[2]:02x}"
            row = tk.Frame(dlg, bg=BG1)
            row.pack(fill="x", padx=8, pady=2)
            tk.Label(row, bg=src_hex, width=4, height=1, relief="solid", bd=1).pack(side="left", padx=4)
            tk.Label(row, text=f"{src_hex.upper()} ->", bg=BG1, fg=TXS, font=("Segoe UI", 9)).pack(side="left")
            tk.Label(row, bg=dst_hex, width=4, height=1, relief="solid", bd=1).pack(side="left", padx=4)
            tk.Label(row, text=dst_hex.upper(), bg=BG1, fg=TXP, font=("Segoe UI", 9)).pack(side="left")
            def _del(idx=i, d=dlg):
                if idx < len(self._color_replacements):
                    self._color_replacements.pop(idx)
                n = len(self._color_replacements)
                self._repl_btn.config(text=f"Reemplazos ({n})", fg=ACC if n > 0 else TXS)
                self._refresh_text_preview()
                self._run(save=False)
                d.destroy()
                self._show_replacements_popup()
            tk.Button(row, text="✕", bg=BG1, fg=RED, relief="flat", cursor="hand2",
                      font=("Segoe UI", 9), command=_del).pack(side="right", padx=4)
        r = tk.Frame(dlg, bg=BG0)
        r.pack(fill="x", padx=8, pady=8)
        def _clear_all():
            self._color_replacements.clear()
            self._repl_btn.config(text="Reemplazos (0)", fg=TXS)
            self._refresh_text_preview()
            self._run(save=False)
            dlg.destroy()
        self._btn(r, "Limpiar todo", _clear_all, bg="#3d1f1f", fg=RED).pack(side="left")
        self._btn(r, "Cerrar", dlg.destroy, bg=BG2, fg=TXS).pack(side="right")
        dlg.bind("<Escape>", lambda _: dlg.destroy())

    # ── Feature 3: Auto-ajuste inteligente ───────────────────────────────────

    def _auto_adjust(self):
        path = self.src_path.get().strip()
        if not path or not os.path.isfile(path):
            self.status_var.set("Cargá una imagen primero.")
            return
        try:
            from PIL import ImageStat
            img = Image.open(path).convert("RGB")
            stat = ImageStat.Stat(img)
            mean   = sum(stat.mean) / 3
            stddev = sum(stat.stddev) / 3
            brightness = max(0.7, min(1.8, 128.0 / max(mean, 8)))
            contrast   = max(0.8, min(1.8, 70.0 / max(stddev, 5)))
            self.brightness_var.set(round(brightness, 2))
            self.contrast_var.set(round(contrast, 2))
            if self.saturation_var.get() == 1.0:
                self.saturation_var.set(1.15)
            self._run(save=False)
            self.status_var.set(
                f"Auto-ajuste: brillo={brightness:.2f}  contraste={contrast:.2f}")
        except Exception as e:
            self.status_var.set(f"Auto-ajuste error: {e}")

    # ── Feature 4: Paleta del BMP ─────────────────────────────────────────────

    def _show_palette(self, zone: str):
        src = self.src_path.get().strip()
        if not src or not os.path.isfile(src):
            messagebox.showinfo("Paleta", "Cargá una imagen fuente primero.")
            return
        try:
            size  = CLAN_SIZE if zone == "clan" else ALLY_SIZE
            img_p = image_to_l2_bmp(src, None, size, align=zone,
                                     **self._common_kw())
        except Exception as e:
            messagebox.showerror("Paleta", f"Error al generar: {e}")
            return
        pal_data    = img_p.getpalette()
        colors      = [(pal_data[i*3], pal_data[i*3+1], pal_data[i*3+2]) for i in range(256)]
        used_indices = set(img_p.getdata())

        dlg = tk.Toplevel(self, bg=BG0)
        dlg.title(f"Paleta {zone.title()} — {len(used_indices)} colores usados")
        dlg.transient(self)
        dlg.resizable(False, False)
        tk.Label(dlg,
                 text=f"{len(used_indices)}/256 colores usados  ·  Click para usar como color de texto",
                 bg=BG0, fg=TXS, font=("Segoe UI", 8)).pack(pady=(8, 4))
        frame = tk.Frame(dlg, bg=BG0)
        frame.pack(padx=8, pady=4)
        for i, (r2, g2, b2) in enumerate(colors):
            col_hex = f"#{r2:02x}{g2:02x}{b2:02x}"
            used = i in used_indices
            lbl = tk.Label(frame, bg=col_hex, width=2, height=1,
                           relief="solid" if used else "flat",
                           bd=1 if used else 0, cursor="hand2")
            lbl.grid(row=i // 16, column=i % 16, padx=1, pady=1)
            lbl.bind("<Button-1>", lambda e, c=col_hex: self._set_text_color(c))
            lbl.bind("<Enter>",
                lambda e, c=col_hex, u=used, d=dlg, z=zone:
                    d.title(f"Paleta {z.title()} — {c.upper()}{'  (usada)' if u else ''}"))
        tk.Label(dlg, text="Borde = color presente en la imagen",
                 bg=BG0, fg=TXS, font=("Segoe UI", 7)).pack(pady=(4, 8))
        dlg.bind("<Escape>", lambda _: dlg.destroy())

    # ── Feature 5: Antes/Después ──────────────────────────────────────────────

    def _toggle_before_after(self):
        self._before_after_mode = not self._before_after_mode
        if self._ba_btn:
            self._ba_btn.config(
                fg=ACC if self._before_after_mode else TXS,
                relief="sunken" if self._before_after_mode else "flat",
            )
        self._refresh_text_preview()

    # ── Feature 6: Preview en contexto L2 ────────────────────────────────────

    def _show_ingame_preview(self):
        if self._last_clan_img is None and self._last_ally_img is None:
            messagebox.showinfo("Preview", "Generá una vista previa primero.")
            return

        W     = 620
        TAG_H = 190   # scene with overhead name tag
        INF_H = 185   # clan info panel
        H     = TAG_H + INF_H

        # Font loading
        fnt_sm = fnt_md = fnt_bd = None
        for face in ("arialbd.ttf", "arial.ttf", "verdana.ttf"):
            fp = os.path.join(FONTS_DIR, face)
            if os.path.isfile(fp):
                try:
                    fnt_sm = ImageFont.truetype(fp, 11)
                    fnt_md = ImageFont.truetype(fp, 13)
                    fnt_bd = ImageFont.truetype(fp, 15)
                    break
                except Exception:
                    pass

        _dm = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        def _tw(text, font):
            if font is None: return len(text) * 7
            bb = _dm.textbbox((0, 0), text, font=font)
            return bb[2] - bb[0]
        def _th(font):
            if font is None: return 13
            bb = _dm.textbbox((0, 0), "Ag", font=font)
            return bb[3] - bb[1]

        # ── Section 1: Tag sobre personaje ────────────────────────────────────
        scene = Image.new("RGBA", (W, TAG_H), (0, 0, 0, 255))
        sd    = ImageDraw.Draw(scene)

        for y in range(TAG_H):
            t = y / TAG_H
            sd.line([(0, y), (W, y)],
                    fill=(int(18+10*t), int(15+8*t), int(11+6*t), 255))

        floor_y = TAG_H - 32
        sd.rectangle([0, floor_y, W, TAG_H], fill=(26, 22, 17, 255))
        for xi in range(0, W, 55):
            sd.line([(xi, floor_y), (xi, TAG_H)], fill=(33, 28, 20, 255))
        for yi in range(floor_y, TAG_H, 18):
            sd.line([(0, yi), (W, yi)],           fill=(33, 28, 20, 255))

        # Compute name tag size before drawing character
        CREST_SCALE = 2
        ally_tw  = ALLY_SIZE[0] * CREST_SCALE   # 16 px
        ally_th  = ALLY_SIZE[1] * CREST_SCALE   # 24 px
        player_name = self.text_var.get().strip() or "PlayerName"
        title_str   = "[ Bronze III ]"
        PAD = 9

        title_w = _tw(title_str, fnt_sm)
        name_rw = ally_tw + 4 + _tw(player_name, fnt_md)
        name_rh = max(ally_th, _th(fnt_md))
        tag_w   = max(title_w, name_rw) + PAD * 2
        tag_h   = _th(fnt_sm) + 4 + name_rh + PAD * 2
        tag_x   = (W - tag_w) // 2
        tag_y   = 15

        # Simple character silhouette below tag
        char_cx  = W // 2
        body_top = tag_y + tag_h + 18
        sd.rectangle([char_cx-10, body_top, char_cx+10, floor_y], fill=(28, 24, 18, 255))
        head_cy = body_top - 14
        sd.ellipse([char_cx-13, head_cy-13, char_cx+13, head_cy+13], fill=(28, 24, 18, 255))

        # Semi-transparent name tag box
        ov = Image.new("RGBA", (W, TAG_H), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)
        od.rounded_rectangle([tag_x, tag_y, tag_x+tag_w, tag_y+tag_h],
                              radius=5, fill=(0, 0, 0, 162))
        scene = Image.alpha_composite(scene, ov)
        sd    = ImageDraw.Draw(scene)

        # Title line (cyan, centered)
        tx = tag_x + (tag_w - title_w) // 2
        ty = tag_y + PAD
        sd.text((tx, ty), title_str, font=fnt_sm, fill=(100, 205, 235, 255))

        # Name row: [ally crest] PlayerName — centered within tag box
        row_y       = ty + _th(fnt_sm) + 4
        name_total  = ally_tw + 4 + _tw(player_name, fnt_md)
        row_x       = tag_x + (tag_w - name_total) // 2
        if self._last_ally_img:
            try:
                a_pil  = self._last_ally_img.convert("RGBA").resize(
                    (ally_tw, ally_th), Image.NEAREST)
                cy_off = max(0, (name_rh - ally_th) // 2)
                scene.paste(a_pil, (row_x, row_y + cy_off), a_pil)
            except Exception:
                pass
        sd.text((row_x + ally_tw + 4,
                 row_y + max(0, (name_rh - _th(fnt_md)) // 2)),
                player_name, font=fnt_md, fill=(225, 212, 165, 255))

        sd.text((6, TAG_H - 14), "Tag sobre personaje",
                font=fnt_sm, fill=(60, 54, 40, 255))

        # ── Section 2: Ventana de clan ────────────────────────────────────────
        SCALE = 6
        info  = Image.new("RGB", (W, INF_H), (14, 12, 10))
        id_   = ImageDraw.Draw(info)

        id_.rectangle([16, 8,  W-16, INF_H-8], fill=(26,22,18), outline=(78,68,48), width=2)
        id_.rectangle([18, 10, W-18, 38],       fill=(34,29,21), outline=(78,68,48), width=1)
        if fnt_bd:
            id_.text((36, 13), "Clan Information", font=fnt_bd, fill=(200, 175, 100))

        ax, ay = 46, 50
        id_.rectangle([ax-4, ay-4, ax+ALLY_SIZE[0]*SCALE+4, ay+ALLY_SIZE[1]*SCALE+4],
                      fill=(19,17,13), outline=(68,58,38), width=2)
        if fnt_sm:
            id_.text((ax, ay+ALLY_SIZE[1]*SCALE+6), "Alianza", font=fnt_sm, fill=(150,130,90))
        if self._last_ally_img:
            try:
                info.paste(self._last_ally_img.convert("RGB").resize(
                    (ALLY_SIZE[0]*SCALE, ALLY_SIZE[1]*SCALE), Image.NEAREST), (ax, ay))
            except Exception:
                pass

        cx2, cy2 = ax + ALLY_SIZE[0]*SCALE + 22, 50
        id_.rectangle([cx2-4, cy2-4, cx2+CLAN_SIZE[0]*SCALE+4, cy2+CLAN_SIZE[1]*SCALE+4],
                      fill=(19,17,13), outline=(68,58,38), width=2)
        if fnt_sm:
            id_.text((cx2, cy2+CLAN_SIZE[1]*SCALE+6), "Clan", font=fnt_sm, fill=(150,130,90))
        if self._last_clan_img:
            try:
                info.paste(self._last_clan_img.convert("RGB").resize(
                    (CLAN_SIZE[0]*SCALE, CLAN_SIZE[1]*SCALE), Image.NEAREST), (cx2, cy2))
            except Exception:
                pass

        ix = cx2 + CLAN_SIZE[0]*SCALE + 24
        for ri, (lbl, val) in enumerate([("Nombre:", "___________"),
                                          ("Alianza:", "___________"),
                                          ("Nivel:",   "___")]):
            if fnt_sm:
                id_.text((ix,      50 + ri*22), lbl, font=fnt_sm, fill=(120,110,80))
                id_.text((ix + 68, 50 + ri*22), val, font=fnt_sm, fill=(190,170,120))
        if fnt_sm:
            id_.text((6, INF_H - 14), "Ventana de información de clan",
                      font=fnt_sm, fill=(60, 54, 40))

        # ── Compose + popup ───────────────────────────────────────────────────
        full = Image.new("RGB", (W, H))
        full.paste(scene.convert("RGB"), (0, 0))
        full.paste(info, (0, TAG_H))
        ImageDraw.Draw(full).line([(0, TAG_H), (W, TAG_H)], fill=(45, 40, 30), width=2)

        dlg   = tk.Toplevel(self, bg="#000000")
        dlg.title("🎮 Preview en contexto L2")
        dlg.transient(self)
        dlg.resizable(False, False)
        photo = ImageTk.PhotoImage(full)
        lbl   = tk.Label(dlg, image=photo, bg="#000000")
        lbl.image = photo
        lbl.pack(padx=2, pady=2)
        tk.Label(dlg, text="Simulación aproximada  ·  Esc o click para cerrar",
                 bg="#000000", fg="#555555", font=("Segoe UI", 8)).pack(pady=(0, 4))
        dlg.bind("<Escape>", lambda _: dlg.destroy())
        dlg.bind("<Button-1>", lambda _: dlg.destroy())

    # ── Feature 7: Historial de exportados ───────────────────────────────────

    def _show_history(self):
        if not self._export_history:
            messagebox.showinfo("Historial", "No hay exportaciones en esta sesión.")
            return
        dlg = tk.Toplevel(self, bg=BG0)
        dlg.title(f"Historial ({len(self._export_history)} exportaciones)")
        dlg.transient(self)
        dlg.geometry("520x420")
        dlg.resizable(False, True)
        tk.Label(dlg, text="Click en 'Restaurar' para recuperar esa configuración",
                 bg=BG0, fg=TXS, font=("Segoe UI", 8)).pack(pady=(8, 4))
        cf = tk.Frame(dlg, bg=BG1)
        cf.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        vsb = ttk.Scrollbar(cf, orient="vertical")
        vsb.pack(side="right", fill="y")
        hcanvas = tk.Canvas(cf, bg=BG1, highlightthickness=0, yscrollcommand=vsb.set)
        hcanvas.pack(side="left", fill="both", expand=True)
        vsb.config(command=hcanvas.yview)
        inner = tk.Frame(hcanvas, bg=BG1)
        hcanvas.create_window((0, 0), window=inner, anchor="nw")
        MULT = 8
        self._hist_photos = []
        for entry in self._export_history:
            row_f = tk.Frame(inner, bg=BG2, relief="flat")
            row_f.pack(fill="x", padx=4, pady=3)
            thumb_w = (ALLY_SIZE[0] + CLAN_SIZE[0]) * MULT
            thumb_h = max(ALLY_SIZE[1], CLAN_SIZE[1]) * MULT
            thumb = Image.new("RGB", (thumb_w, thumb_h), (30, 35, 40))
            if entry.get("ally"):
                thumb.paste(entry["ally"].convert("RGB").resize(
                    (ALLY_SIZE[0]*MULT, ALLY_SIZE[1]*MULT), Image.NEAREST), (0, 0))
            if entry.get("clan"):
                thumb.paste(entry["clan"].convert("RGB").resize(
                    (CLAN_SIZE[0]*MULT, CLAN_SIZE[1]*MULT), Image.NEAREST),
                    (ALLY_SIZE[0]*MULT, 0))
            ph = ImageTk.PhotoImage(thumb)
            self._hist_photos.append(ph)
            tk.Label(row_f, image=ph, bg=BG2).pack(side="left", padx=6, pady=4)
            info_f = tk.Frame(row_f, bg=BG2)
            info_f.pack(side="left", fill="both", expand=True, pady=4)
            src_name = os.path.basename(entry.get("src", "")) or "—"
            tk.Label(info_f, text=f"[{entry['time']}]  {src_name}",
                     bg=BG2, fg=TXP, font=("Segoe UI", 8, "bold"), anchor="w").pack(fill="x")
            def _restore(e=entry, d=dlg):
                self._apply_settings(e["settings"])
                src_p = e.get("src", "")
                if src_p and os.path.isfile(src_p):
                    self.src_path.set(src_p)
                    self._update_source_preview(src_p)
                self._run(save=False)
                d.destroy()
            self._btn(info_f, "↩ Restaurar", _restore,
                      bg=BG1, fg=ACC, width=10).pack(anchor="w", pady=2)
        inner.update_idletasks()
        hcanvas.config(scrollregion=hcanvas.bbox("all"))
        hcanvas.bind("<MouseWheel>",
                     lambda e: hcanvas.yview_scroll(-1*(e.delta//120), "units"))
        dlg.bind("<Escape>", lambda _: dlg.destroy())

    # ── Feature 8: Crop manual con drag del split ─────────────────────────────

    def _split_drag_start(self, event):
        if not self._src_disp_rect:
            return
        off_x, off_y, disp_w, disp_h = self._src_disp_rect
        split_x = off_x + int(_split_ratio * disp_w)
        if abs(event.x - split_x) <= 14:
            self._dragging_split = True
            self.src_canvas.config(cursor="sb_h_double_arrow")

    def _split_drag_move(self, event):
        global _split_ratio
        if not self._dragging_split or not self._src_disp_rect:
            return
        off_x, off_y, disp_w, disp_h = self._src_disp_rect
        ratio = (event.x - off_x) / max(disp_w, 1)
        _split_ratio = max(0.15, min(0.55, ratio))
        self._refresh_text_preview()

    def _split_drag_end(self, event):
        if self._dragging_split:
            self._dragging_split = False
            self.src_canvas.config(cursor="")
            self._run(save=False)

    def _reset_split(self):
        global _split_ratio
        _split_ratio = 8 / 24
        self._refresh_text_preview()
        self._run(save=False)

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
        script  = os.path.join(_HERE, "L2CrestMaker.py")
        pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        if not os.path.isfile(pythonw):
            pythonw = sys.executable
        ps = (
            f"$s = New-Object -ComObject WScript.Shell;"
            f"$l = $s.CreateShortcut('{lnk}');"
            f"$l.TargetPath = '{pythonw}';"
            f"$l.Arguments = '\"{script}\"';"
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
