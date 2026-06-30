import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk, ImageFilter, ImageEnhance, ImageDraw
import os
import json
import io
import copy

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False

try:
    import win32clipboard  # type: ignore
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

PREVIEW_SIZE = 512
OUTPUT_SIZE  = 32
RECENT_FILE  = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".l2icon_recent.json")
MAX_RECENT   = 5
MAX_UNDO     = 20

EXPORT_BG = {
    "Transparente": None,
    "Negro":        (0, 0, 0, 255),
    "Magenta":      (255, 0, 255, 255),
}


def _make_checker(size: int, sq: int = 8) -> Image.Image:
    img  = Image.new("RGB", (size, size), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    for y in range(0, size, sq * 2):
        for x in range(0, size, sq * 2):
            draw.rectangle([x,    y,    x+sq-1,   y+sq-1],   fill=(180, 180, 180))
            draw.rectangle([x+sq, y+sq, x+sq*2-1, y+sq*2-1], fill=(180, 180, 180))
    return img


class App:
    def __init__(self, root: tk.Misc) -> None:
        self.root = root
        self.root.title("L2 Icon Creator — 32×32")
        self.root.resizable(False, False)
        self.root.configure(bg="#1e1e2e")

        # Image
        self.original_image: Image.Image | None = None
        self.preview_photo:  ImageTk.PhotoImage | None = None
        self.scale_factor  = 1.0
        self._prev_off     = (0, 0)
        self.current_path: str | None = None

        # Crop
        self.crop_mode  = tk.BooleanVar(value=False)
        self.rect_start: tuple[int, int] | None = None
        self.rect_id:    int | None = None
        self.crop_box:   tuple[int, int, int, int] | None = None

        # Adjustments
        self.brightness_var   = tk.DoubleVar(value=1.0)
        self.contrast_var     = tk.DoubleVar(value=1.0)
        self.saturation_var   = tk.DoubleVar(value=1.0)
        self.pre_sharpen_var  = tk.DoubleVar(value=0.0)
        self.post_sharpen_var = tk.DoubleVar(value=1.0)
        self.supersample_var  = tk.BooleanVar(value=True)

        # Display
        self.export_bg_var  = tk.StringVar(value="Negro")
        self.preview_bg_var = tk.StringVar(value="Cuadriculado")
        self.zoom_var       = tk.IntVar(value=8)
        self.grid_var       = tk.BooleanVar(value=True)

        # Undo
        self.undo_stack: list[dict] = []
        self._pushing = False

        self.recent_files: list[str] = self._load_recent()

        self._build_ui()
        self._setup_dnd()
        self.root.bind("<Escape>",    self._clear_crop)
        self.root.bind("<Control-z>", self._undo)

    # ── UI ───────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("TButton",      background="#313244", foreground="#cdd6f4",
                    font=("Segoe UI", 10), padding=6)
        s.map("TButton", background=[("active", "#45475a")])
        s.configure("TLabel",       background="#1e1e2e", foreground="#cdd6f4",
                    font=("Segoe UI", 10))
        s.configure("TCheckbutton", background="#1e1e2e", foreground="#cdd6f4",
                    font=("Segoe UI", 10))
        s.map("TCheckbutton", background=[("active", "#1e1e2e")])
        s.configure("TFrame",       background="#1e1e2e")
        s.configure("Horizontal.TScale", background="#1e1e2e", troughcolor="#313244")

        # Top toolbar
        top = ttk.Frame(self.root)
        top.pack(fill="x", padx=12, pady=(12, 4))
        ttk.Button(top, text="Cargar imagen",  command=self._load_image).pack(side="left", padx=(0, 4))
        ttk.Button(top, text="Carpeta (lote)", command=self._batch_process).pack(side="left", padx=(0, 8))
        self.recent_btn = ttk.Button(top, text="Recientes ▾", command=self._show_recent_menu)
        self.recent_btn.pack(side="left", padx=(0, 16))
        self.crop_check = ttk.Checkbutton(
            top, text="Modo recorte cuadrado  (Esc = limpiar)",
            variable=self.crop_mode, command=self._toggle_mode)
        self.crop_check.pack(side="left")

        # Middle: adjustment panel + canvas
        mid = ttk.Frame(self.root)
        mid.pack(padx=12, pady=4)

        # ── Adjustment panel ──
        adj_outer = tk.Frame(mid, bg="#181825", bd=1, relief="groove")
        adj_outer.pack(side="left", anchor="n", padx=(0, 8))
        tk.Label(adj_outer, text=" Ajustes ", bg="#181825", fg="#89b4fa",
                 font=("Segoe UI", 9, "bold")).pack(fill="x", pady=(6, 2))

        adj_bg = tk.Frame(adj_outer, bg="#1e1e2e")
        adj_bg.pack(fill="x", padx=2, pady=(0, 6))

        def row(parent, label, var, lo, hi):
            f = tk.Frame(parent, bg="#1e1e2e")
            f.pack(fill="x", padx=8, pady=2)
            tk.Label(f, text=label, bg="#1e1e2e", fg="#cdd6f4",
                     font=("Segoe UI", 9), width=13, anchor="w").pack(side="left")
            sc = ttk.Scale(f, from_=lo, to=hi, variable=var,
                           orient="horizontal", length=130,
                           command=lambda _: self._update_preview())
            sc.pack(side="left")
            sc.bind("<ButtonPress-1>", lambda _: self._push_undo())
            return sc

        row(adj_bg, "Brillo",        self.brightness_var,   0.5, 2.0)
        row(adj_bg, "Contraste",     self.contrast_var,     0.5, 2.0)
        row(adj_bg, "Saturación",    self.saturation_var,   0.0, 3.0)
        tk.Frame(adj_bg, bg="#313244", height=1).pack(fill="x", padx=8, pady=4)
        row(adj_bg, "Pre-nitidez",   self.pre_sharpen_var,  0.0, 3.0)
        row(adj_bg, "Post-nitidez",  self.post_sharpen_var, 0.0, 3.0)
        tk.Frame(adj_bg, bg="#313244", height=1).pack(fill="x", padx=8, pady=4)

        ss_f = tk.Frame(adj_bg, bg="#1e1e2e")
        ss_f.pack(fill="x", padx=8)
        tk.Checkbutton(ss_f, text="Supersampling", variable=self.supersample_var,
                       bg="#1e1e2e", fg="#cdd6f4", selectcolor="#313244",
                       activebackground="#1e1e2e", activeforeground="#cdd6f4",
                       font=("Segoe UI", 9), command=self._update_preview).pack(anchor="w")

        tk.Frame(adj_bg, bg="#313244", height=1).pack(fill="x", padx=8, pady=4)

        btn_f = tk.Frame(adj_bg, bg="#1e1e2e")
        btn_f.pack(fill="x", padx=8, pady=(0, 4))
        ttk.Button(btn_f, text="Resetear", command=self._reset_adj).pack(fill="x", pady=2)
        self.undo_lbl = tk.Label(btn_f, text="Sin historial", bg="#1e1e2e",
                                  fg="#6c7086", font=("Segoe UI", 8))
        self.undo_lbl.pack(anchor="w", pady=2)

        # ── Canvas ──
        cf = tk.Frame(mid, bg="#313244", bd=2, relief="groove")
        cf.pack(side="left")
        self.canvas = tk.Canvas(cf, width=PREVIEW_SIZE, height=PREVIEW_SIZE,
                                bg="#181825", cursor="crosshair", highlightthickness=0)
        self.canvas.pack()
        self.canvas.bind("<ButtonPress-1>",   self._on_press)
        self.canvas.bind("<B1-Motion>",       self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

        # Controls row
        ctrl = ttk.Frame(self.root)
        ctrl.pack(fill="x", padx=12, pady=(4, 2))

        ttk.Label(ctrl, text="Fondo export:").pack(side="left")
        ttk.Combobox(ctrl, textvariable=self.export_bg_var,
                     values=list(EXPORT_BG.keys()), width=12, state="readonly"
                     ).pack(side="left", padx=(4, 16))

        ttk.Label(ctrl, text="Preview bg:").pack(side="left")
        for val, lbl in [("Negro", "Negro"), ("Blanco", "Blanco"), ("Cuadriculado", "Checker")]:
            tk.Radiobutton(ctrl, text=lbl, variable=self.preview_bg_var, value=val,
                           bg="#1e1e2e", fg="#cdd6f4", selectcolor="#313244",
                           activebackground="#1e1e2e", activeforeground="#cdd6f4",
                           font=("Segoe UI", 9),
                           command=self._update_preview).pack(side="left", padx=2)

        ttk.Separator(ctrl, orient="vertical").pack(side="left", fill="y", padx=10)

        ttk.Label(ctrl, text="Zoom:").pack(side="left")
        for val, lbl in [(4, "×4"), (8, "×8"), (16, "×16")]:
            tk.Radiobutton(ctrl, text=lbl, variable=self.zoom_var, value=val,
                           bg="#1e1e2e", fg="#cdd6f4", selectcolor="#313244",
                           activebackground="#1e1e2e", activeforeground="#cdd6f4",
                           font=("Segoe UI", 9),
                           command=self._update_preview).pack(side="left", padx=2)

        tk.Checkbutton(ctrl, text="Grid", variable=self.grid_var,
                       bg="#1e1e2e", fg="#cdd6f4", selectcolor="#313244",
                       activebackground="#1e1e2e", activeforeground="#cdd6f4",
                       font=("Segoe UI", 9),
                       command=self._update_preview).pack(side="left", padx=(8, 0))

        # Preview section: before + after
        prev_outer = ttk.Frame(self.root)
        prev_outer.pack(padx=12, pady=4)

        before_col = ttk.Frame(prev_outer)
        before_col.pack(side="left", padx=(0, 16))
        tk.Label(before_col, text="Sin ajustes", bg="#1e1e2e",
                 fg="#6c7086", font=("Segoe UI", 9)).pack()
        self.before_label = tk.Label(before_col, bg="#181825", relief="groove", bd=2)
        self.before_label.pack()

        after_col = ttk.Frame(prev_outer)
        after_col.pack(side="left")
        tk.Label(after_col, text="Con ajustes", bg="#1e1e2e",
                 fg="#a6e3a1", font=("Segoe UI", 9)).pack()
        self.after_label = tk.Label(after_col, bg="#181825", relief="groove", bd=2)
        self.after_label.pack()

        # Bottom bar
        bot = ttk.Frame(self.root)
        bot.pack(fill="x", padx=12, pady=(4, 12))
        self.status_var = tk.StringVar(value="Carga una imagen o arrástrala aquí.")
        ttk.Label(bot, textvariable=self.status_var, foreground="#a6adc8").pack(side="left")
        ttk.Button(bot, text="Exportar 32/64/128",
                   command=self._export_multi).pack(side="right", padx=(4, 0))
        self.save_btn = ttk.Button(bot, text="Guardar 32×32",
                                   command=self._save_image, state="disabled")
        self.save_btn.pack(side="right", padx=(4, 0))
        self.copy_btn = ttk.Button(bot, text="Copiar",
                                   command=self._copy_to_clipboard, state="disabled")
        self.copy_btn.pack(side="right")

    # ── DnD ──────────────────────────────────────────────────────────────────

    def _setup_dnd(self) -> None:
        if not HAS_DND:
            return
        for w in (self.root, self.canvas):
            w.drop_target_register(DND_FILES)
            w.dnd_bind("<<Drop>>", self._on_drop)

    def _on_drop(self, event) -> None:
        path = event.data.strip().strip("{}")
        if os.path.isfile(path):
            self._load_from_path(path)

    # ── Recent ───────────────────────────────────────────────────────────────

    def _load_recent(self) -> list[str]:
        try:
            if os.path.exists(RECENT_FILE):
                with open(RECENT_FILE) as f:
                    return json.load(f)
        except Exception:
            pass
        return []

    def _save_recent(self) -> None:
        try:
            with open(RECENT_FILE, "w") as f:
                json.dump(self.recent_files, f)
        except Exception:
            pass

    def _add_recent(self, path: str) -> None:
        if path in self.recent_files:
            self.recent_files.remove(path)
        self.recent_files.insert(0, path)
        self.recent_files = self.recent_files[:MAX_RECENT]
        self._save_recent()

    def _show_recent_menu(self) -> None:
        menu = tk.Menu(self.root, tearoff=0, bg="#313244", fg="#cdd6f4",
                       activebackground="#45475a", font=("Segoe UI", 9))
        valid = [p for p in self.recent_files if os.path.exists(p)]
        if not valid:
            menu.add_command(label="Sin archivos recientes", state="disabled")
        else:
            for p in valid:
                menu.add_command(label=os.path.basename(p),
                                 command=lambda x=p: self._load_from_path(x))
        btn = self.recent_btn
        menu.tk_popup(btn.winfo_rootx(), btn.winfo_rooty() + btn.winfo_height())

    # ── Load ─────────────────────────────────────────────────────────────────

    def _load_image(self) -> None:
        path = filedialog.askopenfilename(
            title="Selecciona una imagen",
            filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.bmp *.gif *.tga *.tiff *.webp"),
                       ("Todos", "*.*")])
        if path:
            self._load_from_path(path)

    def _load_from_path(self, path: str) -> None:
        self.original_image = Image.open(path).convert("RGBA")
        self.current_path   = path
        self.crop_box       = None
        if self.rect_id:
            self.canvas.delete(self.rect_id)
            self.rect_id = None
        self._render_canvas()
        self.save_btn.configure(state="normal")
        self.copy_btn.configure(state="normal")
        w, h = self.original_image.size
        self.status_var.set(f"{os.path.basename(path)}  —  {w}×{h}px")
        self._add_recent(path)
        self._update_preview()

    # ── Canvas ───────────────────────────────────────────────────────────────

    def _render_canvas(self) -> None:
        if self.original_image is None:
            return
        img = self.original_image.copy()
        img.thumbnail((PREVIEW_SIZE, PREVIEW_SIZE), Image.LANCZOS)
        padded = Image.new("RGBA", (PREVIEW_SIZE, PREVIEW_SIZE), (24, 24, 37, 255))
        ox = (PREVIEW_SIZE - img.width)  // 2
        oy = (PREVIEW_SIZE - img.height) // 2
        padded.paste(img, (ox, oy), img)
        self._prev_off    = (ox, oy)
        self.scale_factor = img.width / self.original_image.width
        self.preview_photo = ImageTk.PhotoImage(padded)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.preview_photo)
        if self.crop_box and self.crop_mode.get():
            self._draw_rect()

    def _toggle_mode(self) -> None:
        if not self.crop_mode.get():
            self._clear_crop()

    def _clear_crop(self, _=None) -> None:
        self.crop_box = None
        if self.rect_id:
            self.canvas.delete(self.rect_id)
            self.rect_id = None
        self._update_preview()

    def _on_press(self, event) -> None:
        if not self.crop_mode.get() or self.original_image is None:
            return
        self._push_undo()
        self.rect_start = (event.x, event.y)
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(
            event.x, event.y, event.x, event.y,
            outline="#f38ba8", width=2, dash=(4, 3))

    def _on_drag(self, event) -> None:
        if not self.crop_mode.get() or self.rect_start is None:
            return
        x0, y0 = self.rect_start
        dx, dy  = event.x - x0, event.y - y0
        size    = min(abs(dx), abs(dy))
        x1 = x0 + (size if dx >= 0 else -size)
        y1 = y0 + (size if dy >= 0 else -size)
        self.canvas.coords(self.rect_id, x0, y0, x1, y1)

    def _on_release(self, event) -> None:
        if not self.crop_mode.get() or self.rect_start is None:
            return
        x0, y0 = self.rect_start
        dx, dy  = event.x - x0, event.y - y0
        size    = min(abs(dx), abs(dy))
        if size < 4:
            self.rect_start = None
            return
        x1 = x0 + (size if dx >= 0 else -size)
        y1 = y0 + (size if dy >= 0 else -size)

        ox, oy = self._prev_off
        sf = self.scale_factor
        cx0, cy0 = min(x0, x1), min(y0, y1)
        cx1, cy1 = max(x0, x1), max(y0, y1)

        ox0 = max(0, (cx0 - ox) / sf)
        oy0 = max(0, (cy0 - oy) / sf)
        ox1 = min(self.original_image.width,  (cx1 - ox) / sf)
        oy1 = min(self.original_image.height, (cy1 - oy) / sf)

        if ox1 - ox0 < 1 or oy1 - oy0 < 1:
            self.rect_start = None
            return
        self.crop_box   = (int(ox0), int(oy0), int(ox1), int(oy1))
        self.rect_start = None
        self._update_preview()

    def _draw_rect(self) -> None:
        if self.crop_box is None:
            return
        ox, oy = self._prev_off
        sf = self.scale_factor
        x0, y0, x1, y1 = self.crop_box
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(
            int(x0*sf+ox), int(y0*sf+oy), int(x1*sf+ox), int(y1*sf+oy),
            outline="#f38ba8", width=2, dash=(4, 3))

    # ── Undo ─────────────────────────────────────────────────────────────────

    def _state(self) -> dict:
        return {
            "brightness":   self.brightness_var.get(),
            "contrast":     self.contrast_var.get(),
            "saturation":   self.saturation_var.get(),
            "pre_sharpen":  self.pre_sharpen_var.get(),
            "post_sharpen": self.post_sharpen_var.get(),
            "supersample":  self.supersample_var.get(),
            "crop_box":     copy.copy(self.crop_box),
        }

    def _push_undo(self) -> None:
        if self._pushing:
            return
        st = self._state()
        if self.undo_stack and self.undo_stack[-1] == st:
            return
        self.undo_stack.append(st)
        if len(self.undo_stack) > MAX_UNDO:
            self.undo_stack.pop(0)
        self._refresh_undo_label()

    def _undo(self, _=None) -> None:
        if not self.undo_stack:
            return
        self._pushing = True
        st = self.undo_stack.pop()
        self.brightness_var.set(st["brightness"])
        self.contrast_var.set(st["contrast"])
        self.saturation_var.set(st["saturation"])
        self.pre_sharpen_var.set(st["pre_sharpen"])
        self.post_sharpen_var.set(st["post_sharpen"])
        self.supersample_var.set(st["supersample"])
        self.crop_box = st["crop_box"]
        self._pushing = False
        self._render_canvas()
        self._update_preview()
        self._refresh_undo_label()

    def _refresh_undo_label(self) -> None:
        n = len(self.undo_stack)
        self.undo_lbl.configure(
            text=f"Ctrl+Z  ({n} {'paso' if n == 1 else 'pasos'})" if n else "Sin historial")

    def _reset_adj(self) -> None:
        self._push_undo()
        self._pushing = True
        self.brightness_var.set(1.0)
        self.contrast_var.set(1.0)
        self.saturation_var.set(1.0)
        self.pre_sharpen_var.set(0.0)
        self.post_sharpen_var.set(1.0)
        self.supersample_var.set(True)
        self._pushing = False
        self._update_preview()

    # ── Image processing ─────────────────────────────────────────────────────

    def _process(self, source: Image.Image | None = None,
                 adjusted: bool = True,
                 apply_bg: bool = True,
                 target: int = OUTPUT_SIZE) -> Image.Image | None:
        img = source if source is not None else self.original_image
        if img is None:
            return None

        # Crop (only when using original image, not batch source)
        if source is None and self.crop_mode.get() and self.crop_box:
            region = img.crop(self.crop_box)
        else:
            region = img.copy()

        if adjusted:
            b = self.brightness_var.get()
            c = self.contrast_var.get()
            sat = self.saturation_var.get()
            if abs(b - 1.0) > 0.01:
                region = ImageEnhance.Brightness(region).enhance(b)
            if abs(c - 1.0) > 0.01:
                region = ImageEnhance.Contrast(region).enhance(c)
            if abs(sat - 1.0) > 0.01:
                region = ImageEnhance.Color(region).enhance(sat)
            for _ in range(round(self.pre_sharpen_var.get())):
                region = region.filter(
                    ImageFilter.UnsharpMask(radius=1, percent=100, threshold=2))

        # Supersampling: 2-step downscale for large sources
        super_size = target * 4
        if self.supersample_var.get() and max(region.size) > super_size:
            region = region.resize((super_size, super_size), Image.LANCZOS)

        result = region.resize((target, target), Image.LANCZOS)

        if adjusted:
            for _ in range(round(self.post_sharpen_var.get())):
                result = result.filter(
                    ImageFilter.UnsharpMask(radius=0.5, percent=120, threshold=1))

        if apply_bg:
            bg_color = EXPORT_BG[self.export_bg_var.get()]
            if bg_color is not None:
                bg = Image.new("RGBA", (target, target), bg_color)
                bg.paste(result, mask=result.split()[3])
                result = bg.convert("RGB")

        return result

    def _make_preview_tile(self, icon: Image.Image) -> Image.Image:
        zoom = self.zoom_var.get()
        size = OUTPUT_SIZE * zoom
        big  = icon.convert("RGBA").resize((size, size), Image.NEAREST)

        bg_name = self.preview_bg_var.get()
        if bg_name == "Cuadriculado":
            bg = _make_checker(size, sq=max(4, zoom // 2)).convert("RGBA")
        elif bg_name == "Blanco":
            bg = Image.new("RGBA", (size, size), (255, 255, 255, 255))
        else:
            bg = Image.new("RGBA", (size, size), (0, 0, 0, 255))

        bg.paste(big, mask=big.split()[3])
        result = bg.convert("RGB")

        if self.grid_var.get():
            draw = ImageDraw.Draw(result)
            col  = (80, 80, 80) if bg_name == "Negro" else (160, 160, 160)
            for i in range(0, size, zoom):
                draw.line([(i, 0),      (i, size - 1)], fill=col, width=1)
                draw.line([(0, i), (size - 1, i)],      fill=col, width=1)

        return result

    def _update_preview(self) -> None:
        if self.original_image is None:
            return
        raw  = self._process(adjusted=False, apply_bg=False)
        proc = self._process(adjusted=True,  apply_bg=False)
        if raw is None or proc is None:
            return

        zoom = self.zoom_var.get()
        size = OUTPUT_SIZE * zoom

        for img_data, label in [(raw, self.before_label), (proc, self.after_label)]:
            tile  = self._make_preview_tile(img_data)
            photo = ImageTk.PhotoImage(tile)
            label.configure(image=photo, width=size, height=size)
            label._photo = photo  # type: ignore[attr-defined]

    # ── Save / Copy / Export ─────────────────────────────────────────────────

    def _copy_to_clipboard(self) -> None:
        out = self._process(apply_bg=True)
        if out is None:
            return
        if HAS_WIN32:
            buf  = io.BytesIO()
            out.convert("RGB").save(buf, "BMP")
            data = buf.getvalue()[14:]
            buf.close()
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
            win32clipboard.CloseClipboard()
            self.status_var.set("Copiado al portapapeles.")
        else:
            import tempfile, subprocess
            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            out.save(tmp.name)
            tmp.close()
            subprocess.Popen(["explorer", tmp.name])
            self.status_var.set("pywin32 no disponible — abierto en visor.")

    def _save_image(self) -> None:
        if self.original_image is None:
            return
        out  = self._process(apply_bg=True)
        path = filedialog.asksaveasfilename(
            title="Guardar icono 32×32", defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("BMP", "*.bmp"), ("TGA", "*.tga")])
        if not path:
            return
        out.save(path, optimize=True)
        self.status_var.set(f"Guardado: {os.path.basename(path)}")

    def _export_multi(self) -> None:
        if self.original_image is None:
            messagebox.showinfo("Sin imagen", "Carga una imagen primero.")
            return
        folder = filedialog.askdirectory(title="Selecciona carpeta de destino")
        if not folder:
            return
        name = os.path.splitext(os.path.basename(self.current_path or "icon"))[0]
        sizes = [32, 64, 128]
        for sz in sizes:
            out  = self._process(apply_bg=True, target=sz)
            path = os.path.join(folder, f"{name}_{sz}x{sz}.png")
            out.save(path, optimize=True)
        labels = [f"{sz}×{sz}" for sz in sizes]
        messagebox.showinfo("Exportado",
                            f"Guardados: {', '.join(labels)}\nen: {folder}")
        self.status_var.set(f"Exportados {', '.join(labels)}")

    # ── Batch ─────────────────────────────────────────────────────────────────

    def _batch_process(self) -> None:
        folder = filedialog.askdirectory(title="Selecciona carpeta con imágenes")
        if not folder:
            return
        exts  = {".png", ".jpg", ".jpeg", ".bmp", ".tga", ".tiff", ".webp", ".gif"}
        files = [f for f in os.listdir(folder)
                 if os.path.splitext(f)[1].lower() in exts]
        if not files:
            messagebox.showinfo("Sin imágenes", "No se encontraron imágenes en la carpeta.")
            return

        out_dir = os.path.join(folder, "icons_32x32")
        os.makedirs(out_dir, exist_ok=True)

        win = tk.Toplevel(self.root)
        win.title("Procesando lote...")
        win.configure(bg="#1e1e2e")
        win.resizable(False, False)
        win.grab_set()
        ttk.Label(win, text=f"Convirtiendo {len(files)} imágenes...").pack(padx=24, pady=(14, 6))
        bar = ttk.Progressbar(win, length=320, maximum=len(files))
        bar.pack(padx=24, pady=4)
        lbl = ttk.Label(win, text="", foreground="#a6adc8")
        lbl.pack(padx=24, pady=(0, 14))
        win.update()

        done = 0
        for fname in files:
            try:
                src = Image.open(os.path.join(folder, fname)).convert("RGBA")
                out = self._process(source=src, adjusted=True, apply_bg=True)
                out.save(os.path.join(out_dir, os.path.splitext(fname)[0] + ".png"),
                         optimize=True)
                done += 1
            except Exception:
                pass
            bar["value"] = done
            lbl.configure(text=fname)
            win.update()

        win.destroy()
        messagebox.showinfo("Lote completado",
                            f"{done}/{len(files)} convertidas.\nGuardadas en:\n{out_dir}")
        self.status_var.set(f"Lote: {done} iconos guardados en icons_32x32/")


if __name__ == "__main__":
    root = TkinterDnD.Tk() if HAS_DND else tk.Tk()
    App(root)
    root.mainloop()
