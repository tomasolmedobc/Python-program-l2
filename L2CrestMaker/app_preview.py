"""PreviewMixin — renderizado del preview de fuente/resultado, zoom, copiar al
portapapeles, auto-fit de texto, paleta del BMP, antes/después, y el mockup
de cómo se ve el crest en el juego."""
import os

import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageDraw, ImageEnhance, ImageTk, ImageFont

from L2CrestMaker import (
    _apply_hue_shift, _hex_to_rgb, _combined_base, _crop_box, _make_gradient,
    _font_from_path, _per_char_fonts, _draw_chars, _apply_italic,
    _copy_image_to_clipboard, _log_error, image_to_l2_bmp,
    CLAN_SIZE, ALLY_SIZE, SUPER_SAMPLE, PREVIEW_MULT, ZOOM_MULT, FONTS_DIR,
    BG0, ACC, TXS,
)
import L2CrestMaker as _core  # _split_ratio es un global mutable compartido entre módulos


class PreviewMixin:

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
                if self.multi_font_var.get():
                    zt = self._mf_text()
                    _mf_fp = self._mf_font_paths() if zt else None
                else:
                    zt = self.text_var.get().strip()
                    _mf_fp = None
                if zt:
                    # Build list of (char_str, px_x, px_y, font, bold_stroke, per_char_fonts)
                    _items = []
                    if self._smart_layout_active and not self.multi_font_var.get():
                        for _ch, (_rx, _ry), _spct in self._get_smart_layout_texts(zt):
                            _itx = off_x + int(_rx * disp_w)
                            _ity = off_y + int(_ry * disp_h)
                            _ifs = max(8, int(disp_h * _spct / 100))
                            _ibsw = max(1, _ifs // 45) if _bold else 0
                            _items.append((_ch, _itx, _ity, _font_from_path(fp, _ifs), _ibsw, None, None))
                    else:
                        _fs  = max(8, int(disp_h * self.text_size.get() / 100))
                        _itx = off_x + int(self.text_pos[0] * disp_w)
                        _ity = off_y + int(self.text_pos[1] * disp_h)
                        _bsw = max(1, _fs // 45) if _bold else 0
                        if _mf_fp:
                            _cfnts, _cyoffs = _per_char_fonts(
                                zt, _mf_fp, self._mf_size_pcts(), self._mf_y_offsets(),
                                self.text_size.get(),
                                lambda pct: max(8, int(disp_h * pct / 100)),
                                lambda pct: int(disp_h * pct / 100),
                                _font_from_path(fp, _fs))
                        else:
                            _cfnts  = None
                            _cyoffs = None
                        _items.append((zt, _itx, _ity, _font_from_path(fp, _fs), _bsw, _cfnts, _cyoffs))

                    for _ch, _itx, _ity, _fnt, _bsw, _cfnts, _cyoffs in _items:
                        if self.shadow_var.get():
                            sr2, sg2, sb2 = _hex_to_rgb(self.shadow_color)
                            _draw_chars(td, _ch, _fnt,
                                        _itx + self.shadow_x.get(),
                                        _ity + self.shadow_y.get(),
                                        sp, (sr2, sg2, sb2, 180), stroke_w=_bsw,
                                        fonts=_cfnts, y_offsets=_cyoffs)
                        if self.text_gradient_var.get():
                            _fl = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
                            _fd = ImageDraw.Draw(_fl)
                            _draw_chars(_fd, _ch, _fnt, _itx, _ity, sp,
                                        (255, 255, 255, 255), stroke_w=_bsw,
                                        fonts=_cfnts, y_offsets=_cyoffs)
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
                                        (r, g, b, 255), stroke_w=_bsw,
                                        fonts=_cfnts, y_offsets=_cyoffs)
                if self.text_rotation_var.get() != 0:
                    text_layer = text_layer.rotate(-self.text_rotation_var.get(), expand=False, resample=Image.BICUBIC)
                if self.italic_var.get():
                    text_layer = _apply_italic(text_layer)
                result_rgba = Image.alpha_composite(result_rgba, text_layer)
                if zt:
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
                _split_x_src = _bx1 + _bw * _core._split_ratio
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
        except Exception as e:
            # Fires on every keystroke/slider change — too noisy for a popup
            # or a log line per keystroke, but a silent preview freeze with
            # zero trace is worse. Log just the first occurrence per session.
            if not self._preview_error_logged:
                self._preview_error_logged = True
                _log_error("_refresh_text_preview", e)

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
        pal_data    = img_p.getpalette() or []
        if len(pal_data) < 768:
            pal_data = pal_data + [0] * (768 - len(pal_data))
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
