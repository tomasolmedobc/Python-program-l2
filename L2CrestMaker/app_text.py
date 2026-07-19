"""TextMixin — texto/iniciales: color, degradado, contorno, multi-font,
selector de fuentes, smart layout, y el drag de posición del texto."""
import os
import colorsys

import tkinter as tk
from tkinter import ttk, colorchooser
from PIL import Image, ImageDraw, ImageEnhance, ImageTk

from L2CrestMaker import (
    _apply_hue_shift, _combined_base, _hex_to_rgb, _make_gradient, _font_from_path,
    BG0, BG1, BG2, ACC, TXS, TXP, GRN,
    CLAN_SIZE, ALLY_SIZE, SUPER_SAMPLE,
)
import L2CrestMaker as _core  # _split_ratio es un global mutable compartido entre módulos


class TextMixin:

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
            split = bx1 + bw * _core._split_ratio
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
            split = bx1 + bw * _core._split_ratio
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

    # ── Multi-font ────────────────────────────────────────────────────────────

    def _on_multi_font_toggle(self):
        if self.multi_font_var.get():
            self._single_font_section.pack_forget()
            self._mf_frame.pack(fill="x", before=self._mf_toggle_row)
            if self._smart_layout_active:
                self._clear_smart_layout()
        else:
            self._mf_frame.pack_forget()
            self._single_font_section.pack(fill="x", before=self._mf_toggle_row)
        self._refresh_text_preview()

    def _on_mf_change(self, idx: int):
        if self._mf_upd:
            return
        self._mf_upd = True
        v = self.mf_chars[idx].get()[:1].upper()
        self.mf_chars[idx].set(v)
        self._mf_upd = False
        self._refresh_text_preview()

    def _mf_text(self) -> str:
        return "".join(v.get().strip().upper() for v in self.mf_chars if v.get().strip())

    def _mf_font_paths(self) -> list:
        return [self.font_paths.get(vf.get(), "")
                for vc, vf in zip(self.mf_chars, self.mf_fonts)
                if vc.get().strip()]

    def _mf_size_pcts(self) -> list:
        return [vs.get()
                for vc, vs in zip(self.mf_chars, self.mf_sizes)
                if vc.get().strip()]

    def _mf_y_offsets(self) -> list:
        return [vo.get()
                for vc, vo in zip(self.mf_chars, self.mf_offsets_y)
                if vc.get().strip()]

    def _open_font_picker_slot(self, i: int):
        self._open_font_picker(target_var=self.mf_fonts[i])

    def _refresh_text_preview_debounced(self, *_):
        if self._mf_preview_after:
            self.after_cancel(self._mf_preview_after)
        self._mf_preview_after = self.after(120, self._refresh_text_preview)

    def _mf_export_texts(self):
        """Texto final + kwargs de fuente-por-letra, según multi-font esté on/off."""
        if self.multi_font_var.get():
            t = self._mf_text()
            return (t,
                    self._mf_font_paths() if t else None,
                    self._mf_size_pcts()  if t else None,
                    self._mf_y_offsets()  if t else None)
        return (self.text_var.get().strip(), None, None, None)

    # ── Fuentes ───────────────────────────────────────────────────────────────

    def _on_font_selected(self, _=None):
        self._refresh_text_preview()
        self._update_font_preview()

    def _filter_fonts(self, _):
        typed = self.selected_font.get().lower()
        filtered = [n for n in self.font_names if typed in n.lower()]
        self.font_combo["values"] = filtered if filtered else self.font_names

    def _open_font_picker(self, target_var=None):
        if self._font_picker_open:
            return
        self._font_picker_open = True

        cur_sel = (lambda: target_var.get()) if target_var is not None else self.selected_font.get

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
            selected = (name == cur_sel())
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
                is_sel  = (name == cur_sel())
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
            if target_var is not None:
                target_var.set(name)
            else:
                self.selected_font.set(name)
                self._font_thumb_cache.clear()
                self._on_font_selected()
            self._refresh_text_preview()
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
        dlg.bind("<Escape>", lambda _: on_close())

        # ── Construir lista inicial y centrar en fuente seleccionada ───────
        rebuild(list(self.font_names))
        sel = cur_sel()
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
                cl_split   = bx1 + bw * _core._split_ratio
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
