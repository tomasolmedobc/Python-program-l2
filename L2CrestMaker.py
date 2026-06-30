"""
L2 Crest Maker  ·  v2.0
Creador de Crests para Lineage 2
  • Clan Crest   : 16x12 px, 256 colores BMP  (zona derecha)
  • Ally Crest   :  8x12 px, 256 colores BMP  (zona izquierda)
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
from PIL import Image, ImageTk, ImageDraw, ImageFont, ImageEnhance, ImageFilter
import os, sys, json, ctypes, io, winreg

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
                spacing_pct: int, fill: tuple):
    if not text:
        return
    chars   = list(text)
    boxes   = [draw_obj.textbbox((0, 0), c, font=font) for c in chars]
    widths  = [b[2] - b[0] for b in boxes]
    heights = [b[3] - b[1] for b in boxes]
    avg_w   = sum(widths) / len(widths) if widths else 0
    gap     = int(avg_w * spacing_pct / 100)
    total_w = sum(widths) + gap * (len(chars) - 1)
    max_h   = max(heights) if heights else 0
    x = cx - total_w // 2
    y = cy - max_h  // 2
    for c, w in zip(chars, widths):
        draw_obj.text((x, y), c, font=font, fill=fill)
        x += w + gap


def _hex_to_rgb(hex_color: str) -> tuple:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


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
        split = bx1 + bw * ALLY_SIZE[0] / COMBINED_W   # borde ally|clan
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
                     text_rotation: int = 0) -> Image.Image:
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
        cr, cg, cb = min(255, (255 - r) | 40), min(255, (255 - g) | 40), min(255, (255 - b) | 40)
        outline_step = text_outline
        for t_str, text_pos, text_size_pct in active_texts:
            font_size = max(4, int(sh * text_size_pct / 100))
            font      = _font_from_path(font_path, font_size)
            tx = int((text_pos[0] * src_w - x1) / crop_w * sw)
            ty = int((text_pos[1] * src_h - y1) / crop_h * sh)
            # Sin clamping: texto render exacto donde indica la cruz, PIL recorta si sale del canvas
            if outline_step > 0:
                for odx, ody in [(-outline_step, 0), (outline_step, 0),
                                  (0, -outline_step), (0, outline_step),
                                  (-outline_step, -outline_step), (outline_step, -outline_step),
                                  (-outline_step,  outline_step), (outline_step,  outline_step)]:
                    _draw_chars(td, t_str, font, tx + odx, ty + ody,
                                text_spacing_pct, (cr, cg, cb, 220))
            if shadow:
                sr, sg, sb = _hex_to_rgb(shadow_color)
                _draw_chars(td, t_str, font,
                            tx + shadow_x * SUPER_SAMPLE,
                            ty + shadow_y * SUPER_SAMPLE,
                            text_spacing_pct, (sr, sg, sb, 200))
            _draw_chars(td, t_str, font, tx, ty, text_spacing_pct, (r, g, b, 255))
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
        self._btn(r, "⟳ Reset", self._reset_adjustments, bg=BG2, fg=TXS).pack(side="left", padx=(0, 12))
        self._chk(r, "Nitidez",  self.sharpen_var).pack(side="left", padx=4)
        self._chk(r, "Dithering", self.dither_var).pack(side="left", padx=4)
        self._chk(r, "Exportar PNG", self.export_png_var, cmd=lambda: None).pack(side="left", padx=4)

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
        self._scale(r, self.text_size, 10, 100, length=100).pack(side="left")
        self._lbl(r, "%").pack(side="left", padx=(0, 8))
        self._btn(r, "⊙ Auto", self._auto_fit, bg=BG2, fg=ACC).pack(side="left")

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
        self._color_btns["#ffffff"].config(relief="sunken")

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
        tk.Label(
            parent, text="IMAGEN FUENTE  ·  ZONAS DE RECORTE",
            font=("Segoe UI", 8, "bold"), fg=TXS, bg=BG0
        ).pack(anchor="w", pady=(0, 4))
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
        self.src_canvas.bind("<Configure>", self._on_src_canvas_resize)
        self.src_canvas.bind("<Left>",  lambda e: self._nudge_text(-0.01, 0.0))
        self.src_canvas.bind("<Right>", lambda e: self._nudge_text( 0.01, 0.0))
        self.src_canvas.bind("<Up>",    lambda e: self._nudge_text( 0.0, -0.01))
        self.src_canvas.bind("<Down>",  lambda e: self._nudge_text( 0.0,  0.01))
        self.src_canvas.focus_set()
        if _HAS_DND:
            self.src_canvas.drop_target_register(_DND_FILES)
            self.src_canvas.dnd_bind('<<Drop>>', self._on_file_drop)

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
            if bv != 1.0: img = ImageEnhance.Brightness(img).enhance(bv)
            if cv != 1.0: img = ImageEnhance.Contrast(img).enhance(cv)
            if sv != 1.0: img = ImageEnhance.Color(img).enhance(sv)
            if hv != 0:   img = _apply_hue_shift(img.convert("RGB"), hv)

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

            r, g, b = _hex_to_rgb(self.text_color)
            fp = self._current_font_path()
            sp = self.text_spacing.get()
            text_layer = Image.new("RGBA", (pw, ph), (0,0,0,0))
            td = ImageDraw.Draw(text_layer)
            zt = self.text_var.get().strip()
            if zt:
                fs = max(8, int(disp_h * self.text_size.get() / 100))
                fnt = _font_from_path(fp, fs)
                tx = off_x + int(self.text_pos[0] * disp_w)
                ty = off_y + int(self.text_pos[1] * disp_h)
                if self.shadow_var.get():
                    sr2, sg2, sb2 = _hex_to_rgb(self.shadow_color)
                    _draw_chars(td, zt, fnt,
                                tx + self.shadow_x.get(),
                                ty + self.shadow_y.get(),
                                sp, (sr2, sg2, sb2, 180))
                _draw_chars(td, zt, fnt, tx, ty, sp, (r, g, b, 255))
            if self.text_rotation_var.get() != 0:
                text_layer = text_layer.rotate(-self.text_rotation_var.get(), expand=False, resample=Image.BICUBIC)
            if self.italic_var.get():
                text_layer = _apply_italic(text_layer)
            result_rgba = Image.alpha_composite(result_rgba, text_layer)

            # Crosshair at text anchor position (only when text is set)
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
            fp    = self._current_font_path()
            sp    = self.text_spacing.get()
            chars = list(text)
            dummy = Image.new("RGBA", (1, 1))
            dd    = ImageDraw.Draw(dummy)
            ss_w  = CLAN_SIZE[0] * SUPER_SAMPLE
            ss_h  = CLAN_SIZE[1] * SUPER_SAMPLE
            best_pct = 10
            for pct in range(95, 5, -1):
                font  = _font_from_path(fp, max(4, int(ss_h * pct / 100)))
                ws    = [dd.textbbox((0,0), c, font=font)[2] for c in chars]
                avg_w = sum(ws) / len(ws) if ws else 0
                gap   = int(avg_w * sp / 100)
                total = sum(ws) + gap * (len(chars) - 1)
                if total <= ss_w * 0.85:
                    best_pct = pct
                    break
            self.text_size.set(best_pct)
            self._refresh_text_preview()
            self.status_var.set(f"Auto: {best_pct}%")
        except Exception as e:
            self.status_var.set(f"Error en auto: {e}")

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
        _texts = [(_t, self.text_pos, self.text_size.get())] if _t else []

        def _process(dest_path, size, align):
            img_p = image_to_l2_bmp(
                src, dest_path, size, align=align,
                texts=_texts, **common_kw
            )
            if do_png and dest_path:
                make_preview(img_p, PREVIEW_MULT).save(
                    os.path.splitext(dest_path)[0] + ".png", format="PNG"
                )
            return img_p

        clan_dest = clan if save else None
        if clan or not save:
            try:
                img_p = _process(clan_dest, CLAN_SIZE, "clan")
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
                img_p = _process(ally_dest, ALLY_SIZE, "ally")
                prev = make_preview(img_p, PREVIEW_MULT)
                self._last_ally_img = prev
                self._tk_ally = ImageTk.PhotoImage(prev)
                self.ally_canvas.delete("all")
                if bg_mode == "checker":
                    self._draw_checker(self.ally_canvas, ALLY_SIZE[0]*PREVIEW_MULT, ALLY_SIZE[1]*PREVIEW_MULT)
                self.ally_canvas.create_image(0, 0, anchor="nw", image=self._tk_ally)
            except Exception as e:
                errors.append(f"Ally: {e}")

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
            text_outline     = self.outline_var.get(),
            text_opacity     = self.text_opacity_var.get(),
            text_rotation    = self.text_rotation_var.get(),
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
