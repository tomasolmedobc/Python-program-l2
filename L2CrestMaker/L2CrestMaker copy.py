"""
L2 Crest Maker - Creador de Crests para Lineage 2
Convierte imágenes a formato BMP compatible con L2
- Clan Crest:     16x12 px, 256 colores BMP  (lado derecho de la imagen)
- Alliance Crest:  8x12 px, 256 colores BMP  (lado izquierdo de la imagen)
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw, ImageFont
import os
import sys
import winreg

# ─── Constantes ───────────────────────────────────────────────────────────────
CLAN_SIZE     = (16, 12)
ALLY_SIZE     = (8, 12)
PREVIEW_MULT  = 20
SOURCE_PREV_W = 480
SOURCE_PREV_H = 240
OUTPUT_DIR    = r"E:\L2CyA"
FONTS_DIR     = r"C:\Windows\Fonts"
SUPER_SAMPLE  = 8    # factor de super-muestreo para texto (texto → ×8 → LANCZOS → salida)

# ─── Fuentes del sistema ──────────────────────────────────────────────────────

def _get_system_fonts() -> list:
    """
    Lee el registro de Windows (HKLM + HKCU) y retorna lista ordenada de (nombre, ruta).
    Cubre fuentes instaladas para todos los usuarios y fuentes instaladas por usuario.
    """
    user_fonts_dir = os.path.join(
        os.environ.get("LOCALAPPDATA", ""), r"Microsoft\Windows\Fonts"
    )
    search_dirs = [FONTS_DIR, user_fonts_dir]

    seen  = {}   # nombre → ruta (HKCU tiene prioridad sobre HKLM)
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
    """Carga una fuente desde ruta; cae a default si falla."""
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
    """Inclina la capa RGBA hacia la derecha simulando cursiva (≈17°)."""
    w, h = layer.size
    matrix = (1, shear_k, -shear_k * h, 0, 1, 0)
    return layer.transform((w, h), Image.AFFINE, matrix, resample=Image.BICUBIC)


def _draw_chars(draw_obj, text: str, font, cx: int, cy: int,
                spacing_pct: int, fill: tuple):
    """Dibuja cada letra con espaciado manual, centrado en (cx, cy)."""
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


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _hex_to_rgb(hex_color: str) -> tuple:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _crop_box(src_w: int, src_h: int, target_w: int, target_h: int,
              align: str = "center") -> tuple:
    """
    Devuelve (x1, y1, x2, y2) en coords fuente.
    align: 'left' | 'right' | 'center'
    """
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


# ─── Conversión ───────────────────────────────────────────────────────────────

def image_to_l2_bmp(src_path: str, dest_path: str | None, size: tuple,
                     align: str = "center",
                     text: str = "", text_pos: tuple = (0.5, 0.5),
                     text_size_pct: int = 40, text_color: str = "#ffffff",
                     font_path: str = None, text_spacing_pct: int = 0,
                     italic: bool = False) -> Image.Image:
    """
    Pipeline de conversión con super-muestreo de texto para máxima calidad:
    1. Recorte + fondo negro + LANCZOS → tamaño final (sin texto)
    2. Texto renderizado a ×SUPER_SAMPLE del tamaño de salida
    3. LANCZOS del texto ×SUPER → tamaño final  (anti-aliasing óptimo)
    4. Alpha-composite texto sobre fondo → cuantizar a 256 colores
    """
    img = Image.open(src_path).convert("RGBA")
    src_w, src_h = img.size

    # 1 — Recorte centrado y composición sobre negro
    x1, y1, x2, y2 = _crop_box(src_w, src_h, size[0], size[1], align)
    img = img.crop((int(x1), int(y1), int(x2), int(y2)))
    bg = Image.new("RGB", img.size, (0, 0, 0))
    bg.paste(img, mask=img.split()[3])
    img = bg.resize(size, Image.LANCZOS)

    # 2-3 — Texto a super-resolución controlada
    if text:
        sw = size[0] * SUPER_SAMPLE   # e.g. 128 para clan
        sh = size[1] * SUPER_SAMPLE   # e.g.  96 para clan

        font_size = max(4, int(sh * text_size_pct / 100))
        font = _font_from_path(font_path, font_size)

        text_layer = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
        td = ImageDraw.Draw(text_layer)

        # Convertir text_pos (relativo a imagen fuente) a relativo dentro del recorte
        crop_w, crop_h = x2 - x1, y2 - y1
        tx = int((text_pos[0] * src_w - x1) / crop_w * sw)
        ty = int((text_pos[1] * src_h - y1) / crop_h * sh)

        r, g, b = _hex_to_rgb(text_color)
        _draw_chars(td, text, font, tx, ty, text_spacing_pct, (r, g, b, 255))
        if italic:
            text_layer = _apply_italic(text_layer)

        # 4 — LANCZOS del texto a tamaño final y composite
        text_out = text_layer.resize(size, Image.LANCZOS)
        img = Image.alpha_composite(img.convert("RGBA"), text_out).convert("RGB")

    img_p = img.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=1)
    if dest_path is not None:
        img_p.save(dest_path, format="BMP")
    return img_p


def make_preview(img_p: Image.Image, mult: int) -> Image.Image:
    w, h = img_p.size
    return img_p.resize((w * mult, h * mult), Image.NEAREST)


# ─── Interfaz gráfica ─────────────────────────────────────────────────────────

class L2CrestApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("L2 Crest Maker")
        self.resizable(False, False)
        self.configure(bg="#1a1a2e")

        self.src_path  = tk.StringVar()
        self.clan_path = tk.StringVar()
        self.ally_path = tk.StringVar()

        # Texto / iniciales
        self.text_var       = tk.StringVar()
        self.text_size      = tk.IntVar(value=40)
        self.text_spacing   = tk.IntVar(value=0)
        self.italic_var     = tk.BooleanVar(value=False)
        self.text_color     = "#ffffff"
        self.text_pos       = (0.5, 0.5)
        self._text_upd      = False
        self._src_disp_rect = None
        self._color_btns    = {}

        # Fuentes del sistema
        fonts = _get_system_fonts()
        self.font_names = [name for name, _ in fonts]
        self.font_paths = {name: path for name, path in fonts}
        default_font = next(
            (n for n in self.font_names
             if "faster" in n.lower() and "stroker" in n.lower()),
            self.font_names[0] if self.font_names else ""
        )
        self.selected_font = tk.StringVar(value=default_font)

        self._tk_src  = None
        self._tk_clan = None
        self._tk_ally = None

        self._build_ui()
        self.text_var.trace_add("write", self._on_text_change)

    # ── Restart ────────────────────────────────────────────────────────────────

    def _restart(self):
        self.destroy()
        os.execv(sys.executable, [sys.executable] + sys.argv)

    # ── Construcción UI ────────────────────────────────────────────────────────

    def _build_ui(self):
        PAD = 12

        # ── Título ──
        tk.Label(
            self, text="⚔  L2 Crest Maker  ⚔",
            font=("Segoe UI", 16, "bold"), fg="#e0b84a", bg="#1a1a2e"
        ).grid(row=0, column=0, columnspan=2, pady=(PAD, 4))

        tk.Button(
            self, text="↺ Reiniciar",
            command=self._restart,
            font=("Segoe UI", 8),
            bg="#2a2a5e", fg="#e0e0ff",
            activebackground="#3a3a8e", activeforeground="#ffffff",
            relief="flat", cursor="hand2", pady=4, padx=6
        ).grid(row=0, column=2, padx=(0, PAD), sticky="e")

        tk.Label(
            self, text="Clan 16×12 · Ally 8×12 · 256 colores BMP",
            font=("Segoe UI", 9), fg="#7a7aaa", bg="#1a1a2e"
        ).grid(row=1, column=0, columnspan=3, pady=(0, PAD))

        # ── Imagen fuente ──
        self._section_label("Imagen fuente", 2)
        ttk.Entry(self, textvariable=self.src_path, width=48).grid(
            row=3, column=0, columnspan=2, padx=(PAD, 4), pady=4, sticky="ew"
        )
        self._btn("Abrir…", self._browse_source).grid(row=3, column=2, padx=(0, PAD), pady=4)

        # ── Archivos de salida ──
        self._section_label("Archivos de salida", 4)

        tk.Label(self, text="Clan BMP:", fg="#c0c0e0", bg="#1a1a2e",
                 font=("Segoe UI", 9)).grid(row=5, column=0, padx=(PAD, 2), sticky="e")
        ttk.Entry(self, textvariable=self.clan_path, width=36).grid(
            row=5, column=1, padx=2, pady=3, sticky="ew"
        )
        self._btn("…", self._browse_clan, width=3).grid(row=5, column=2, padx=(0, PAD))

        tk.Label(self, text="Ally BMP:", fg="#c0c0e0", bg="#1a1a2e",
                 font=("Segoe UI", 9)).grid(row=6, column=0, padx=(PAD, 2), sticky="e")
        ttk.Entry(self, textvariable=self.ally_path, width=36).grid(
            row=6, column=1, padx=2, pady=3, sticky="ew"
        )
        self._btn("…", self._browse_ally, width=3).grid(row=6, column=2, padx=(0, PAD))

        # ── Texto / Iniciales ──
        self._section_label("Texto / Iniciales", 7)

        tf = tk.Frame(self, bg="#1a1a2e")
        tf.grid(row=8, column=0, columnspan=3, padx=PAD, pady=(2, 4), sticky="w")

        # Fila 1: letras + tamaño + color
        row1 = tk.Frame(tf, bg="#1a1a2e")
        row1.pack(fill="x", pady=(0, 6))

        tk.Label(row1, text="Letras (máx. 3):", fg="#c0c0e0", bg="#1a1a2e",
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))

        vcmd = (self.register(lambda P: len(P) <= 3), "%P")
        tk.Entry(
            row1, textvariable=self.text_var, width=5,
            validate="key", validatecommand=vcmd,
            font=("Segoe UI", 13, "bold"),
            bg="#16213e", fg="#e0b84a", insertbackground="#e0b84a",
            relief="flat", bd=4
        ).pack(side="left", padx=(0, 16))

        tk.Label(row1, text="Tamaño:", fg="#c0c0e0", bg="#1a1a2e",
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))

        tk.Scale(
            row1, variable=self.text_size, from_=10, to=100,
            orient="horizontal", length=110,
            bg="#1a1a2e", fg="#e0e0ff", troughcolor="#16213e",
            highlightthickness=0, bd=0,
            command=lambda _: self._refresh_text_preview()
        ).pack(side="left", padx=(0, 2))

        tk.Label(row1, text="%", fg="#7a7aaa", bg="#1a1a2e",
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 16))

        tk.Label(row1, text="Color:", fg="#c0c0e0", bg="#1a1a2e",
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 6))

        for label, color, fg_col in [
            ("Blanco", "#ffffff", "#111111"),
            ("Negro",  "#000000", "#e0e0ff"),
            ("Dorado", "#e0b84a", "#111111"),
        ]:
            btn = tk.Button(
                row1, text=label, width=6,
                bg=color, fg=fg_col,
                relief="flat", cursor="hand2", font=("Segoe UI", 8),
                command=lambda c=color: self._set_text_color(c)
            )
            btn.pack(side="left", padx=2)
            self._color_btns[color] = btn

        tk.Checkbutton(
            row1, text="Cursiva", variable=self.italic_var,
            command=self._refresh_text_preview,
            font=("Segoe UI", 9),
            bg="#1a1a2e", fg="#c0c0e0",
            selectcolor="#16213e", activebackground="#1a1a2e",
            activeforeground="#e0e0ff", cursor="hand2"
        ).pack(side="left", padx=(14, 0))

        tk.Label(row1, text="   ← arrastrá el texto en el preview",
                 fg="#7a7aaa", bg="#1a1a2e",
                 font=("Segoe UI", 8, "italic")).pack(side="left", padx=(10, 0))

        self._color_btns["#ffffff"].config(relief="sunken")

        # Fila 2: selector de fuente
        row2 = tk.Frame(tf, bg="#1a1a2e")
        row2.pack(fill="x")

        tk.Label(row2, text="Fuente:", fg="#c0c0e0", bg="#1a1a2e",
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 6))

        self.font_combo = ttk.Combobox(
            row2, textvariable=self.selected_font,
            values=self.font_names, width=32
        )
        self.font_combo.pack(side="left", padx=(0, 8))
        self.font_combo.bind("<<ComboboxSelected>>", self._on_font_selected)
        self.font_combo.bind("<KeyRelease>", self._filter_fonts)

        tk.Label(row2,
                 text=f"({len(self.font_names)} fuentes instaladas)",
                 fg="#7a7aaa", bg="#1a1a2e",
                 font=("Segoe UI", 8)).pack(side="left")

        # Fila 3: espaciado + botones auto
        row3 = tk.Frame(tf, bg="#1a1a2e")
        row3.pack(fill="x", pady=(6, 0))

        tk.Label(row3, text="Espaciado:", fg="#c0c0e0", bg="#1a1a2e",
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))

        tk.Scale(
            row3, variable=self.text_spacing, from_=0, to=100,
            orient="horizontal", length=110,
            bg="#1a1a2e", fg="#e0e0ff", troughcolor="#16213e",
            highlightthickness=0, bd=0,
            command=lambda _: self._refresh_text_preview()
        ).pack(side="left", padx=(0, 2))

        tk.Label(row3, text="%   ", fg="#7a7aaa", bg="#1a1a2e",
                 font=("Segoe UI", 9)).pack(side="left")

        tk.Button(
            row3, text="⊙ Auto Ally",
            command=lambda: self._auto_fit("ally"),
            font=("Segoe UI", 8, "bold"),
            bg="#16213e", fg="#4adde0",
            activebackground="#2a2a5e", activeforeground="#4adde0",
            relief="flat", cursor="hand2", padx=8, pady=3
        ).pack(side="left", padx=(0, 4))

        tk.Button(
            row3, text="⊙ Auto Clan",
            command=lambda: self._auto_fit("clan"),
            font=("Segoe UI", 8, "bold"),
            bg="#16213e", fg="#e0b84a",
            activebackground="#2a2a5e", activeforeground="#e0b84a",
            relief="flat", cursor="hand2", padx=8, pady=3
        ).pack(side="left", padx=(0, 4))

        tk.Label(row3,
                 text="← calcula tamaño y posición óptimos para cada zona",
                 fg="#7a7aaa", bg="#1a1a2e",
                 font=("Segoe UI", 8, "italic")).pack(side="left", padx=(6, 0))

        # ── Botones Convertir / Vista previa ──
        btn_frame = tk.Frame(self, bg="#1a1a2e")
        btn_frame.grid(row=9, column=0, columnspan=3, pady=PAD)

        tk.Button(
            btn_frame, text="👁  Vista previa",
            command=self._preview,
            font=("Segoe UI", 11, "bold"),
            bg="#2a2a5e", fg="#e0e0ff",
            activebackground="#3a3a8e", activeforeground="#ffffff",
            relief="flat", padx=20, pady=8, cursor="hand2"
        ).pack(side="left", padx=8)

        tk.Button(
            btn_frame, text="⚙  Convertir",
            command=self._convert,
            font=("Segoe UI", 11, "bold"),
            bg="#e0b84a", fg="#1a1a2e",
            activebackground="#c9a43a", activeforeground="#1a1a2e",
            relief="flat", padx=20, pady=8, cursor="hand2"
        ).pack(side="left", padx=8)

        # ── Preview: fuente con guías ──
        self._section_label("Imagen fuente · Zonas de recorte", 10)

        src_outer = tk.LabelFrame(
            self,
            text="  ■ Dorado = Clan (16×12)     ■ Cyan = Ally (8×12)  ",
            fg="#7a7aaa", bg="#16213e",
            font=("Segoe UI", 8), relief="groove", bd=2
        )
        src_outer.grid(row=11, column=0, columnspan=3, padx=PAD, pady=(0, 4))

        self.src_canvas = tk.Canvas(
            src_outer, width=SOURCE_PREV_W, height=SOURCE_PREV_H,
            bg="#0a0a1a", highlightthickness=0
        )
        self.src_canvas.pack(padx=6, pady=6)
        self.src_canvas.create_text(
            SOURCE_PREV_W // 2, SOURCE_PREV_H // 2,
            text="Cargá una imagen para ver las zonas de recorte",
            fill="#3a3a6e", font=("Segoe UI", 10)
        )
        self.src_canvas.bind("<Button-1>", self._text_drag_start)
        self.src_canvas.bind("<B1-Motion>", self._text_drag_move)

        # ── Preview: resultado ──
        self._section_label("Resultado (zoom ×20)", 12)

        result_frame = tk.Frame(self, bg="#1a1a2e")
        result_frame.grid(row=13, column=0, columnspan=3, pady=(0, PAD))

        ally_frame = tk.LabelFrame(
            result_frame, text=" Alliance (8×12) ",
            fg="#e0b84a", bg="#16213e",
            font=("Segoe UI", 9, "bold"), relief="groove", bd=2
        )
        ally_frame.pack(side="left", padx=16, pady=4)
        self.ally_canvas = tk.Canvas(
            ally_frame,
            width=ALLY_SIZE[0] * PREVIEW_MULT,
            height=ALLY_SIZE[1] * PREVIEW_MULT,
            bg="#000000", highlightthickness=0
        )
        self.ally_canvas.pack(padx=6, pady=6)

        clan_frame = tk.LabelFrame(
            result_frame, text=" Clan (16×12) ",
            fg="#e0b84a", bg="#16213e",
            font=("Segoe UI", 9, "bold"), relief="groove", bd=2
        )
        clan_frame.pack(side="left", padx=16, pady=4)
        self.clan_canvas = tk.Canvas(
            clan_frame,
            width=CLAN_SIZE[0] * PREVIEW_MULT,
            height=CLAN_SIZE[1] * PREVIEW_MULT,
            bg="#000000", highlightthickness=0
        )
        self.clan_canvas.pack(padx=6, pady=6)

        # ── Status bar ──
        self.status_var = tk.StringVar(value="Listo.")
        tk.Label(
            self, textvariable=self.status_var,
            font=("Segoe UI", 8), fg="#7a7aaa", bg="#1a1a2e", anchor="w"
        ).grid(row=14, column=0, columnspan=3, padx=PAD, pady=(0, PAD), sticky="ew")

        self._apply_entry_style()

    def _section_label(self, text, row):
        tk.Label(
            self, text=text.upper(),
            font=("Segoe UI", 8, "bold"),
            fg="#7a7aaa", bg="#1a1a2e"
        ).grid(row=row, column=0, columnspan=3, padx=12, sticky="w", pady=(8, 0))

    def _btn(self, text, cmd, width=8):
        return tk.Button(
            self, text=text, command=cmd, width=width,
            font=("Segoe UI", 9),
            bg="#2a2a5e", fg="#e0e0ff",
            activebackground="#3a3a8e", activeforeground="#ffffff",
            relief="flat", cursor="hand2", pady=4
        )

    def _apply_entry_style(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "TEntry",
            fieldbackground="#16213e", foreground="#e0e0ff",
            insertcolor="#e0b84a", bordercolor="#3a3a8e",
            lightcolor="#3a3a8e", darkcolor="#3a3a8e",
        )
        style.configure(
            "TCombobox",
            fieldbackground="#16213e", foreground="#e0e0ff",
            selectbackground="#2a2a5e", selectforeground="#e0e0ff",
            arrowcolor="#e0b84a",
        )
        style.map("TCombobox",
                  fieldbackground=[("readonly", "#16213e")],
                  foreground=[("readonly", "#e0e0ff")])

    # ── Fuentes ────────────────────────────────────────────────────────────────

    def _on_font_selected(self, _=None):
        self._refresh_text_preview()

    def _filter_fonts(self, _):
        typed = self.selected_font.get().lower()
        filtered = [n for n in self.font_names if typed in n.lower()]
        self.font_combo["values"] = filtered if filtered else self.font_names

    def _current_font_path(self) -> str:
        return self.font_paths.get(self.selected_font.get(), "")

    # ── Texto ─────────────────────────────────────────────────────────────────

    def _on_text_change(self, *_):
        if self._text_upd:
            return
        self._text_upd = True
        v = self.text_var.get().upper()[:3]
        self.text_var.set(v)
        self._text_upd = False
        self._refresh_text_preview()

    def _set_text_color(self, color: str):
        self.text_color = color
        for c, btn in self._color_btns.items():
            btn.config(relief="sunken" if c == color else "flat")
        self._refresh_text_preview()

    def _refresh_text_preview(self):
        path = self.src_path.get().strip()
        if path and os.path.isfile(path):
            self._update_source_preview(path)

    def _text_drag_start(self, event):
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

    # ── Preview de fuente ──────────────────────────────────────────────────────

    def _update_source_preview(self, src_path: str):
        try:
            img = Image.open(src_path).convert("RGB")
            src_w, src_h = img.size

            scale  = min(SOURCE_PREV_W / src_w, SOURCE_PREV_H / src_h)
            disp_w = int(src_w * scale)
            disp_h = int(src_h * scale)
            off_x  = (SOURCE_PREV_W - disp_w) // 2
            off_y  = (SOURCE_PREV_H - disp_h) // 2
            self._src_disp_rect = (off_x, off_y, disp_w, disp_h)

            bg = Image.new("RGB", (SOURCE_PREV_W, SOURCE_PREV_H), (10, 10, 26))
            bg.paste(img.resize((disp_w, disp_h), Image.LANCZOS), (off_x, off_y))

            def to_canvas(box):
                x1, y1, x2, y2 = box
                return (
                    off_x + int(x1 * scale),
                    off_y + int(y1 * scale),
                    off_x + int(x2 * scale) - 1,
                    off_y + int(y2 * scale) - 1,
                )

            clan_box = to_canvas(_crop_box(src_w, src_h, *CLAN_SIZE, align="right"))
            ally_box = to_canvas(_crop_box(src_w, src_h, *ALLY_SIZE, align="left"))

            overlay = Image.new("RGBA", (SOURCE_PREV_W, SOURCE_PREV_H), (0, 0, 0, 0))
            ov = ImageDraw.Draw(overlay)
            dark = (0, 0, 0, 160)
            cx1, cy1, cx2, cy2 = clan_box
            if cx1 > off_x:
                ov.rectangle([off_x, off_y, cx1 - 1, off_y + disp_h - 1], fill=dark)
            if cx2 < off_x + disp_w - 1:
                ov.rectangle([cx2 + 1, off_y, off_x + disp_w - 1, off_y + disp_h - 1], fill=dark)
            if cy1 > off_y:
                ov.rectangle([off_x, off_y, off_x + disp_w - 1, cy1 - 1], fill=dark)
            if cy2 < off_y + disp_h - 1:
                ov.rectangle([off_x, cy2 + 1, off_x + disp_w - 1, off_y + disp_h - 1], fill=dark)
            ov.rectangle(clan_box, outline=(224, 184, 74, 255), width=2)
            ov.rectangle(ally_box, outline=(74, 221, 224, 255), width=2)

            result_rgba = Image.alpha_composite(bg.convert("RGBA"), overlay)

            text = self.text_var.get().strip()
            if text:
                font_size = max(8, int(disp_h * self.text_size.get() / 100))
                font = _font_from_path(self._current_font_path(), font_size)
                text_layer = Image.new("RGBA", (SOURCE_PREV_W, SOURCE_PREV_H), (0, 0, 0, 0))
                td = ImageDraw.Draw(text_layer)
                tx = off_x + int(self.text_pos[0] * disp_w)
                ty = off_y + int(self.text_pos[1] * disp_h)
                r, g, b = _hex_to_rgb(self.text_color)
                _draw_chars(td, text, font, tx, ty, self.text_spacing.get(), (r, g, b, 255))
                if self.italic_var.get():
                    text_layer = _apply_italic(text_layer)
                result_rgba = Image.alpha_composite(result_rgba, text_layer)

            self._tk_src = ImageTk.PhotoImage(result_rgba.convert("RGB"))
            self.src_canvas.delete("all")
            self.src_canvas.create_image(0, 0, anchor="nw", image=self._tk_src)

        except Exception:
            pass

    # ── Auto-fit ───────────────────────────────────────────────────────────────

    def _auto_fit(self, zone: str):
        """Calcula el tamaño y posición óptimos para que el texto entre en la zona indicada."""
        src = self.src_path.get().strip()
        if not src or not os.path.isfile(src):
            self.status_var.set("Cargá una imagen fuente primero.")
            return
        text = self.text_var.get().strip()
        if not text:
            self.status_var.set("Escribí las letras primero.")
            return
        try:
            with Image.open(src) as img:
                src_w, src_h = img.size

            size  = CLAN_SIZE if zone == "clan" else ALLY_SIZE
            align = "right"   if zone == "clan" else "left"
            box   = _crop_box(src_w, src_h, *size, align=align)
            zone_cx = (box[0] + box[2]) / 2 / src_w
            zone_cy = (box[1] + box[3]) / 2 / src_h

            font_path   = self._current_font_path()
            spacing_pct = self.text_spacing.get()
            chars       = list(text)
            dummy       = Image.new("RGBA", (1, 1))
            dummy_draw  = ImageDraw.Draw(dummy)

            # Medir en espacio super-muestreado (mismo espacio que usa image_to_l2_bmp)
            ss_w = size[0] * SUPER_SAMPLE   # ancho de la zona super-muestreada
            ss_h = size[1] * SUPER_SAMPLE

            best_pct = 10
            for pct in range(95, 5, -1):
                font_size = max(4, int(ss_h * pct / 100))
                font      = _font_from_path(font_path, font_size)
                widths    = [dummy_draw.textbbox((0, 0), c, font=font)[2] for c in chars]
                avg_w     = sum(widths) / len(widths) if widths else 0
                gap       = int(avg_w * spacing_pct / 100)
                total_w   = sum(widths) + gap * (len(chars) - 1)
                if total_w <= ss_w * 0.85:
                    best_pct = pct
                    break

            self.text_size.set(best_pct)
            self.text_pos = (zone_cx, zone_cy)
            self._refresh_text_preview()
            label = "Clan" if zone == "clan" else "Ally"
            self.status_var.set(
                f"Auto {label}: tamaño {best_pct}% · centrado en zona {label}"
            )
        except Exception as e:
            self.status_var.set(f"Error en auto: {e}")

    # ── Callbacks ──────────────────────────────────────────────────────────────

    def _browse_source(self):
        path = filedialog.askopenfilename(
            title="Seleccionar imagen fuente",
            filetypes=[("Imágenes", "*.jpg *.jpeg *.png *.bmp *.tga *.gif *.webp"),
                       ("Todos", "*.*")]
        )
        if path:
            self.src_path.set(path)
            name = os.path.splitext(os.path.basename(path))[0]
            self.clan_path.set(os.path.join(OUTPUT_DIR, name + "_clan.bmp"))
            self.ally_path.set(os.path.join(OUTPUT_DIR, name + "_ally.bmp"))
            self.status_var.set(f"Imagen cargada: {os.path.basename(path)}")
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

    def _preview(self):
        self._run(save=False)

    def _convert(self):
        self._run(save=True)

    def _run(self, save: bool):
        src  = self.src_path.get().strip()
        clan = self.clan_path.get().strip()
        ally = self.ally_path.get().strip()

        if not src:
            messagebox.showerror("Error", "Seleccioná una imagen fuente.")
            return
        if not os.path.isfile(src):
            messagebox.showerror("Error", f"No se encontró el archivo:\n{src}")
            return
        if save and not clan and not ally:
            messagebox.showerror("Error", "Ingresá al menos un archivo de salida.")
            return

        if save:
            os.makedirs(OUTPUT_DIR, exist_ok=True)

        text              = self.text_var.get().strip()
        text_pos          = self.text_pos
        text_size_pct     = self.text_size.get()
        text_spacing_pct  = self.text_spacing.get()
        text_color        = self.text_color
        font_path         = self._current_font_path()
        italic            = self.italic_var.get()
        errors            = []

        # clan
        clan_dest = clan if save else None
        if clan or not save:
            try:
                img_p = image_to_l2_bmp(src, clan_dest, CLAN_SIZE, align="right",
                                         text=text, text_pos=text_pos,
                                         text_size_pct=text_size_pct,
                                         text_color=text_color,
                                         font_path=font_path,
                                         text_spacing_pct=text_spacing_pct,
                                         italic=italic)
                prev = make_preview(img_p, PREVIEW_MULT)
                self._tk_clan = ImageTk.PhotoImage(prev)
                self.clan_canvas.delete("all")
                self.clan_canvas.create_image(0, 0, anchor="nw", image=self._tk_clan)
            except Exception as e:
                errors.append(f"Clan: {e}")

        # ally
        ally_dest = ally if save else None
        if ally or not save:
            try:
                img_p = image_to_l2_bmp(src, ally_dest, ALLY_SIZE, align="left",
                                         text=text, text_pos=text_pos,
                                         text_size_pct=text_size_pct,
                                         text_color=text_color,
                                         font_path=font_path,
                                         text_spacing_pct=text_spacing_pct,
                                         italic=italic)
                prev = make_preview(img_p, PREVIEW_MULT)
                self._tk_ally = ImageTk.PhotoImage(prev)
                self.ally_canvas.delete("all")
                self.ally_canvas.create_image(0, 0, anchor="nw", image=self._tk_ally)
            except Exception as e:
                errors.append(f"Ally: {e}")

        if errors:
            messagebox.showerror("Error" if save else "Error en vista previa",
                                 "\n".join(errors))
        elif save:
            salidas = []
            if clan: salidas.append(os.path.basename(clan))
            if ally: salidas.append(os.path.basename(ally))
            self.status_var.set("✔ Convertido: " + " · ".join(salidas))
            messagebox.showinfo("Listo", "¡Crests generados con éxito!\n\n" + "\n".join(
                ([f"Clan → {clan}"] if clan else []) +
                ([f"Ally → {ally}"] if ally else [])
            ))
        else:
            self.status_var.set("Vista previa generada · los archivos NO fueron guardados")


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = L2CrestApp()
    app.mainloop()
