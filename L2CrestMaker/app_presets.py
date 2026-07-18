"""PresetsMixin — guardar/cargar/borrar/exportar/importar presets de texto+ajustes."""
import os
from tkinter import messagebox, filedialog

from L2CrestMaker import _load_json
import L2CrestMaker as _core  # PRESETS_FILE / _save_json son monkeypatcheados en tests


class PresetsMixin:

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
            "multi_font":     self.multi_font_var.get(),
            "mf_chars":       [v.get() for v in self.mf_chars],
            "mf_fonts":       [v.get() for v in self.mf_fonts],
            "mf_sizes":       [v.get() for v in self.mf_sizes],
            "mf_offsets_y":   [v.get() for v in self.mf_offsets_y],
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
        _saved_mf = s.get("multi_font", False)
        if _saved_mf != self.multi_font_var.get():
            self.multi_font_var.set(_saved_mf)
            self._on_multi_font_toggle()
        for i, v in enumerate(self.mf_chars):
            v.set(s.get("mf_chars", ["", "", ""])[i] if i < len(s.get("mf_chars", [])) else "")
        for i, v in enumerate(self.mf_fonts):
            fn = s.get("mf_fonts", [None, None, None])
            fn = fn[i] if i < len(fn) else None
            v.set(fn if fn and fn in self.font_names else self.selected_font.get())
        for i, v in enumerate(self.mf_sizes):
            saved = s.get("mf_sizes", [60, 60, 60])
            v.set(saved[i] if i < len(saved) else 60)
        for i, v in enumerate(self.mf_offsets_y):
            saved = s.get("mf_offsets_y", [0, 0, 0])
            v.set(saved[i] if i < len(saved) else 0)
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
        self.preset_combo["values"] = list(self.presets.keys())
        if _core._save_json(_core.PRESETS_FILE, self.presets):
            self.status_var.set(f"Preset '{name}' guardado.")
        else:
            self.status_var.set(f"⚠ No se pudo guardar el preset '{name}' en disco.")

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
            self.preset_combo["values"] = list(self.presets.keys())
            self.preset_name.set("")
            if _core._save_json(_core.PRESETS_FILE, self.presets):
                self.status_var.set(f"Preset '{name}' eliminado.")
            else:
                self.status_var.set(f"⚠ '{name}' se quitó de la lista pero no se pudo guardar el cambio en disco.")

    def _export_preset(self):
        name = self.preset_name.get().strip()
        if name not in self.presets:
            messagebox.showwarning("Preset", f"No existe el preset '{name}' guardado. Guardalo primero.")
            return
        path = filedialog.asksaveasfilename(
            title="Exportar preset", defaultextension=".json",
            initialfile=f"{name}.json",
            filetypes=[("Preset L2CrestMaker", "*.json")],
        )
        if not path:
            return
        if _core._save_json(path, {name: self.presets[name]}):
            self.status_var.set(f"Preset '{name}' exportado a {path}")
        else:
            messagebox.showerror("Preset", f"No se pudo escribir el archivo:\n{path}")

    def _import_preset(self):
        path = filedialog.askopenfilename(
            title="Importar preset(s)",
            filetypes=[("Preset L2CrestMaker", "*.json")],
        )
        if not path:
            return
        data = _load_json(path, None)
        if not isinstance(data, dict) or not data or not all(isinstance(v, dict) for v in data.values()):
            messagebox.showerror("Preset", "El archivo no contiene presets válidos.")
            return
        overwritten = [n for n in data if n in self.presets]
        if overwritten and not messagebox.askyesno(
            "Preset",
            f"{len(overwritten)} preset(s) ya existen y se van a sobrescribir:\n"
            + ", ".join(overwritten) + "\n\n¿Continuar? (los demás se importan igual)"
        ):
            data = {n: v for n, v in data.items() if n not in overwritten}
            if not data:
                return
        self.presets.update(data)
        self.preset_combo["values"] = list(self.presets.keys())
        if _core._save_json(_core.PRESETS_FILE, self.presets):
            self.status_var.set(f"{len(data)} preset(s) importado(s) desde {os.path.basename(path)}.")
        else:
            self.status_var.set("⚠ Se importaron en memoria pero no se pudo guardar en disco.")
