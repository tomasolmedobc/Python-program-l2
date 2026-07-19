"""ExportMixin — la conversión final (preview/exportar BMP), batch processing,
y el historial de exportaciones de la sesión."""
import os
import datetime

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk

from L2CrestMaker import (
    OUTPUT_DIR, PREVIEW_MULT, CLAN_SIZE, ALLY_SIZE,
    image_to_l2_bmp, make_preview,
    BG0, BG1, BG2, TXS, TXP, ACC,
)


class ExportMixin:

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
        errors = []

        _t, _cfp, _csp, _cyo = self._mf_export_texts()

        if _t and self._smart_layout_active and not self.multi_font_var.get():
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
                texts=texts, texts_are_crop_relative=texts_rel,
                char_font_paths=_cfp, char_size_pcts=_csp,
                char_y_offsets_pct=_cyo, **common_kw
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
                self._last_clan_img = make_preview(img_p, PREVIEW_MULT)
            except Exception as e:
                errors.append(f"Clan: {e}")

        ally_dest = ally if save else None
        if ally or not save:
            try:
                img_p = _process(ally_dest, ALLY_SIZE, "ally", _texts_ally, _texts_relative)
                self._last_ally_img = make_preview(img_p, PREVIEW_MULT)
            except Exception as e:
                errors.append(f"Ally: {e}")

        self._redraw_result_canvases()

        if save and not errors and self._last_clan_img and self._last_ally_img:
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
            self.status_var.set("Vista previa lista  |  Ctrl+P = preview  |  Ctrl+Enter = convertir  |  Ctrl+Z/Y = deshacer/rehacer")

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
        error_details = []
        _bt, _bcfp, _bcsp, _bcyo = self._mf_export_texts()
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
                                    texts=_batch_texts,
                                    char_font_paths=_bcfp, char_size_pcts=_bcsp,
                                    char_y_offsets_pct=_bcyo, **common_kw)
                ok += 1
            except Exception as e:
                errors += 1
                error_details.append(f"{fname}: {e}")
                print(f"Error en {fname}: {e}")
            self._batch_progress["value"] = i
            self.update_idletasks()

        self._batch_progress.pack_forget()
        self.status_var.set(f"Batch listo: {ok} OK · {errors} errores → {OUTPUT_DIR}")
        msg = f"✔ {ok} imagen(es) convertidas\n✖ {errors} error(es)\n\nSalida: {OUTPUT_DIR}"
        if error_details:
            _shown = error_details[:10]
            msg += "\n\nDetalle:\n" + "\n".join(_shown)
            if len(error_details) > len(_shown):
                msg += f"\n… y {len(error_details) - len(_shown)} más (ver consola)."
        messagebox.showinfo("Batch completado", msg)

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
