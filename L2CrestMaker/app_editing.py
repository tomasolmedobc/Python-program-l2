"""EditingMixin — undo/redo, nudge de texto, eyedropper, reemplazo de color,
auto-ajuste de brillo/contraste, y el drag manual del split ally|clan."""
import os

import tkinter as tk
from tkinter import colorchooser
from PIL import Image, ImageEnhance

from L2CrestMaker import _apply_hue_shift, BG0, BG1, BG2, TXS, TXP, ACC, RED
import L2CrestMaker as _core  # _split_ratio es un global mutable compartido entre módulos


class EditingMixin:

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

    # ── Feature 8: Crop manual con drag del split ─────────────────────────────

    def _split_drag_start(self, event):
        if not self._src_disp_rect:
            return
        off_x, off_y, disp_w, disp_h = self._src_disp_rect
        split_x = off_x + int(_core._split_ratio * disp_w)
        if abs(event.x - split_x) <= 14:
            self._dragging_split = True
            self.src_canvas.config(cursor="sb_h_double_arrow")

    def _split_drag_move(self, event):
        if not self._dragging_split or not self._src_disp_rect:
            return
        off_x, off_y, disp_w, disp_h = self._src_disp_rect
        ratio = (event.x - off_x) / max(disp_w, 1)
        _core._split_ratio = max(0.15, min(0.55, ratio))
        self._refresh_text_preview()

    def _split_drag_end(self, event):
        if self._dragging_split:
            self._dragging_split = False
            self.src_canvas.config(cursor="")
            self._run(save=False)

    def _reset_split(self):
        _core._split_ratio = 8 / 24
        self._refresh_text_preview()
        self._run(save=False)
