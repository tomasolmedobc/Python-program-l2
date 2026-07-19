"""FilesMixin — explorar/arrastrar imágenes, galería de overlays/plantillas,
archivos recientes, y enviar los BMP generados a la carpeta del juego."""
import os

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk

from L2CrestMaker import (
    OUTPUT_DIR, RECENT_FILE, MAX_RECENT,
    BG0, BG1, BG2, ACC, TXS, RED,
    _hex_to_rgb,
)
import L2CrestMaker as _core  # OVERLAYS_DIR / TEMPLATES_DIR / _save_json son monkeypatcheados en tests


class FilesMixin:

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

    # ── Galería de overlays / plantillas ────────────────────────────────────

    def _open_asset_gallery(self):
        if self._gallery_open:
            return
        try:
            os.makedirs(_core.OVERLAYS_DIR, exist_ok=True)
            os.makedirs(_core.TEMPLATES_DIR, exist_ok=True)
        except OSError as e:
            messagebox.showerror("Galería", f"No se pudo crear la carpeta:\n{e}")
            return
        self._gallery_open = True

        dlg = tk.Toplevel(self, bg=BG0)
        dlg.title("Galería de overlays y plantillas")
        dlg.transient(self)
        dlg.geometry(f"520x560+{self.winfo_x()+100}+{self.winfo_y()+60}")

        canvas = tk.Canvas(dlg, bg=BG0, highlightthickness=0)
        vsb = ttk.Scrollbar(dlg, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=10)

        outer = tk.Frame(canvas, bg=BG0)
        canvas.create_window((0, 0), window=outer, anchor="nw")
        outer.bind("<Configure>",
                   lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<MouseWheel>",
                    lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"))

        def _thumb(path, size=72):
            # Cacheado en self._asset_thumb_cache (vive con la app, no con el
            # diálogo) — si no, el PhotoImage se recolecta apenas termina este
            # método y las miniaturas quedan en blanco.
            if path in self._asset_thumb_cache:
                return self._asset_thumb_cache[path]
            try:
                im = Image.open(path).convert("RGBA")
            except Exception:
                return None
            im.thumbnail((size, size), Image.LANCZOS)
            bg = Image.new("RGBA", (size, size), (*_hex_to_rgb(BG2), 255))
            bg.alpha_composite(im, ((size - im.width) // 2, (size - im.height) // 2))
            ph = ImageTk.PhotoImage(bg)
            self._asset_thumb_cache[path] = ph
            return ph

        def on_close():
            self._gallery_open = False
            dlg.destroy()

        def _select(path):
            self.src_path2.set(path)
            self._refresh_text_preview()
            on_close()

        def _section(title: str, folder: str):
            lf = tk.LabelFrame(outer, text=title, bg=BG1, fg=ACC,
                                font=("Segoe UI", 9, "bold"), bd=1, relief="flat")
            lf.pack(fill="x", pady=(0, 8), padx=(0, 10))
            try:
                names = os.listdir(folder)
            except OSError as e:
                tk.Label(lf, bg=BG1, fg=RED, font=("Segoe UI", 8), justify="left",
                         text=f"No se pudo leer la carpeta:\n{e}").pack(anchor="w", padx=8, pady=8)
                return
            files = sorted(f for f in names
                           if os.path.splitext(f)[1].lower() in (".png", ".bmp", ".gif"))
            if not files:
                tk.Label(lf, bg=BG1, fg=TXS, font=("Segoe UI", 8), justify="left",
                         text=f"Vacío — copiá tus PNGs acá:\n{folder}").pack(anchor="w", padx=8, pady=8)
                return
            grid = tk.Frame(lf, bg=BG1)
            grid.pack(fill="x", padx=6, pady=6)
            for i, fname in enumerate(files):
                path = os.path.join(folder, fname)
                ph = _thumb(path)
                if ph is None:
                    continue
                cell = tk.Frame(grid, bg=BG2)
                cell.grid(row=i // 6, column=i % 6, padx=3, pady=3)
                img_lbl = tk.Label(cell, image=ph, bg=BG2, cursor="hand2")
                img_lbl.pack()
                tk.Label(cell, text=fname[:12], bg=BG2, fg=TXS,
                         font=("Segoe UI", 7)).pack()
                for w in (cell, img_lbl):
                    w.bind("<Button-1>", lambda _e, p=path: _select(p))

        _section("🖼 Overlays", _core.OVERLAYS_DIR)
        _section("🧩 Plantillas / Bordes", _core.TEMPLATES_DIR)

        btn_row = tk.Frame(dlg, bg=BG0)
        btn_row.pack(fill="x", padx=10, pady=(0, 10))
        self._btn(btn_row, "📂 Abrir carpeta Overlays",
                  lambda: os.startfile(_core.OVERLAYS_DIR), bg=BG2, fg=TXS).pack(side="left", padx=(0, 6))
        self._btn(btn_row, "📂 Abrir carpeta Plantillas",
                  lambda: os.startfile(_core.TEMPLATES_DIR), bg=BG2, fg=TXS).pack(side="left")
        dlg.protocol("WM_DELETE_WINDOW", on_close)
        dlg.bind("<Escape>", lambda _: on_close())
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
        _core._save_json(RECENT_FILE, self.recent_files)

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
