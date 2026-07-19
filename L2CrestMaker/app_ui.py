"""UIBuilderMixin — construcción de toda la UI: cards, helpers de widgets,
y el manejo de pantalla completa / resize del canvas de preview."""
import os

import tkinter as tk
from tkinter import ttk

from L2CrestMaker import (
    _HAS_DND, _DND_FILES,
    BG0, BG1, BG2, ACC, AC2, TXP, TXS, GRN, RED,
    SOURCE_PREV_W, SOURCE_PREV_H, CLAN_SIZE, ALLY_SIZE, PREVIEW_MULT, COMBINED_W,
)


class UIBuilderMixin:

    # ── Construcción UI ───────────────────────────────────────────────────────

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # Panel principal con divisor arrastrable entre izquierda y derecha
        self._main_pane = ttk.PanedWindow(self, orient="horizontal")
        self._main_pane.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)

        # ── Columna izquierda: scrollable ────────────────────────────────────
        self._left_outer = left_outer = tk.Frame(self._main_pane, bg=BG0)
        left_outer.rowconfigure(0, weight=1)
        left_outer.columnconfigure(0, weight=1)
        left_outer.bind("<Configure>", self._enforce_min_left_pane)

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
        right = tk.Frame(self._main_pane, bg=BG0)

        self._main_pane.add(left_outer, weight=0)
        self._main_pane.add(right, weight=1)

        self._build_header(left)
        self._build_files_card(left)
        self._build_transform_card(left)
        self._build_adjust_card(left)
        self._build_hue_zone_card(left)
        self._build_text_card(left)
        self._build_presets_card(left)
        self._build_actions_card(left)

        self._build_source_preview(right)
        self._build_result_preview(right)

        # Status bar
        self.status_var = tk.StringVar(
            value="Listo.  |  Ctrl+P = preview  |  Ctrl+Enter = convertir  |  "
                  "Ctrl+Z/Y = deshacer/rehacer  |  F11 = pantalla completa"
        )
        tk.Label(
            self, textvariable=self.status_var,
            font=("Segoe UI", 8), fg=TXS, bg=BG0, anchor="w", padx=12
        ).grid(row=1, column=0, sticky="ew", pady=(0, 6))

        self._apply_styles()
        # Posición inicial del divisor y minsize de ventana tras layout inicial
        self.after_idle(self._lock_left_width)

    def _lock_left_width(self):
        self.update_idletasks()
        lw = self._left_inner.winfo_reqwidth() + 20   # ancho natural + scrollbar
        self._left_canvas.configure(width=lw)
        self._left_min_width = lw + 24
        try:
            self._main_pane.sashpos(0, self._left_min_width)
        except tk.TclError:
            pass
        self.minsize(lw + SOURCE_PREV_W // 2, 560)

    def _enforce_min_left_pane(self, _event=None):
        # Debounced like the other resize handlers below — this fires on
        # every <Configure> of left_outer, which happens continuously while
        # the window is being live-resized, so doing the sashpos() check
        # synchronously on each one adds unnecessary work during the drag.
        if self._enforce_min_pane_after:
            self.after_cancel(self._enforce_min_pane_after)
        self._enforce_min_pane_after = self.after(150, self._do_enforce_min_left_pane)

    def _do_enforce_min_left_pane(self):
        self._enforce_min_pane_after = None
        # ttk.PanedWindow has no per-pane minsize option, so the sash can be
        # dragged past the left panel's natural content width, clipping it
        # (no horizontal scrollbar exists). Snap it back if that happens.
        lw = getattr(self, "_left_min_width", None)
        if lw is None:
            return
        try:
            if self._main_pane.sashpos(0) < lw:
                self._main_pane.sashpos(0, lw)
        except tk.TclError:
            pass

    # ── Helpers de UI ─────────────────────────────────────────────────────────

    def _card(self, parent, title: str, accent=ACC, collapsible=False, start_open=True,
              build_fn=None) -> tk.Frame:
        """build_fn, si se pasa, recibe `inner` y arma su contenido recién la
        primera vez que la card se abre — para cards que empiezan cerradas y
        rara vez se usan, evita construir sus widgets (y su costo de layout)
        en cada arranque si el usuario nunca las despliega. Sin build_fn, el
        contenido se arma de una (como antes): el caller llena `inner` él
        mismo apenas _card() retorna."""
        lf = tk.LabelFrame(parent, bg=BG1, bd=1, relief="solid")
        inner = tk.Frame(lf, bg=BG1)
        built = {"done": False}

        def _ensure_built():
            if not built["done"]:
                built["done"] = True
                if build_fn is not None:
                    build_fn(inner)

        if collapsible:
            hdr = tk.Frame(lf, bg=BG1, cursor="hand2")
            state = {"open": start_open}
            arrow = tk.Label(hdr, text=("▾" if start_open else "▸"),
                              font=("Segoe UI", 9, "bold"), fg=accent, bg=BG1, cursor="hand2")
            arrow.pack(side="left")
            tk.Label(hdr, text=f" {title}  ", font=("Segoe UI", 9, "bold"),
                     fg=accent, bg=BG1, cursor="hand2").pack(side="left")
            lf.configure(labelwidget=hdr)
            if start_open:
                _ensure_built()
                inner.pack(fill="x", padx=10, pady=8)

            def _toggle(_=None):
                if state["open"]:
                    inner.pack_forget()
                    arrow.config(text="▸")
                else:
                    _ensure_built()
                    inner.pack(fill="x", padx=10, pady=8)
                    arrow.config(text="▾")
                state["open"] = not state["open"]

            hdr.bind("<Button-1>", _toggle)
            for child in hdr.winfo_children():
                child.bind("<Button-1>", _toggle)
        else:
            lf.configure(text=f"  {title}  ", font=("Segoe UI", 9, "bold"),
                         fg=accent, labelanchor="nw")
            inner.pack(fill="x", padx=10, pady=8)
            _ensure_built()

        lf.pack(fill="x", pady=(0, 8))
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

    def _add_tooltip(self, widget, text):
        tip = {"win": None}

        def _show(event):
            tw = tk.Toplevel(widget)
            tip["win"] = tw
            tw.wm_overrideredirect(True)
            tw.wm_geometry(f"+{event.x_root + 12}+{event.y_root + 12}")
            tk.Label(
                tw, text=text, bg="#1c2128", fg=TXP,
                font=("Segoe UI", 8), relief="solid", bd=1, padx=6, pady=3
            ).pack()

        def _hide(_event=None):
            if tip["win"] is not None:
                tip["win"].destroy()
                tip["win"] = None

        widget.bind("<Enter>", _show, add="+")
        widget.bind("<Leave>", _hide, add="+")
        widget.bind("<Button-1>", _hide, add="+")

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
        p = self._card(parent, "📁  Archivos", collapsible=True)

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
        _clear_src2_btn = self._btn(r2, "✕", lambda: self.src_path2.set(""), width=3,
                  bg="#3d1f1f", fg=RED)
        _clear_src2_btn.pack(side="left", padx=(0, 8))
        self._add_tooltip(_clear_src2_btn, "Quitar Fuente 2")
        self._btn(r2, "⇅ Swap capas", self._swap_sources,
                  bg="#2a1f3d", fg="#c084fc").pack(side="left", padx=(0, 4))
        self._btn(r2, "🖼 Galería", self._open_asset_gallery,
                  bg=BG2, fg=ACC).pack(side="left")

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
        p = self._card(parent, "🔄  Transformaciones", collapsible=True)
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
        p = self._card(parent, "🎨  Ajustes de imagen", collapsible=True)

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

    # ── Feature 9: zona de tono ──────────────────────────────────────────────

    def _build_hue_zone_card(self, parent):
        # Empieza cerrada y no tiene ningún widget referenciado desde afuera
        # (a diferencia de las otras cards) — se arma recién al abrirla la
        # primera vez, así no suma su costo de layout en cada arranque para
        # quien nunca la usa.
        self._card(parent, "🎯  Zona de tono", collapsible=True, start_open=False,
                   build_fn=self._populate_hue_zone_card)

    def _populate_hue_zone_card(self, p):
        r = self._row(p)
        self._chk(r, "Activar", self.hue_zone_enabled_var,
                  cmd=self._refresh_text_preview).pack(side="left", padx=(0, 12))
        self._lbl(r, "Forma:", fg=TXS).pack(side="left")
        for lbl, val in [("🫧 Burbuja", "circle"), ("▭ Rectángulo", "rect")]:
            tk.Radiobutton(
                r, text=lbl, variable=self.hue_zone_shape_var, value=val,
                font=("Segoe UI", 9), fg=TXP, bg=BG1,
                selectcolor=BG2, activebackground=BG1, cursor="hand2",
                command=self._refresh_text_preview
            ).pack(side="left", padx=(4, 0))

        r_inv = self._row(p, pady=(2, 0))
        self._chk(r_inv, "Invertir (afectar afuera de la forma)", self.hue_zone_invert_var,
                  cmd=self._refresh_text_preview).pack(side="left")

        r2 = self._row(p, pady=(4, 2))
        self._lbl(r2, "Tono (hue):", w=12).pack(side="left")
        self._scale(r2, self.hue_zone_hue_var, -180, 180, length=180, res=1).pack(side="left", padx=(4, 0))
        self._lbl(r2, "°").pack(side="left", padx=(2, 0))

        r3 = self._row(p, pady=(4, 0))
        self._btn(r3, "↺ Reset zona", self._reset_hue_zone, bg=BG2, fg=TXS).pack(side="left")
        self._lbl(r3, "  arrastrá la forma en la vista previa para moverla · el punto en la esquina la agranda/achica",
                  fg=TXS).pack(side="left")

    # ── Texto / Iniciales ─────────────────────────────────────────────────────

    def _build_text_card(self, parent):
        p = self._card(parent, "✏️  Texto / Iniciales")

        nb = ttk.Notebook(p)
        nb.pack(fill="x")
        tab_content  = tk.Frame(nb, bg=BG1)
        tab_color    = tk.Frame(nb, bg=BG1)
        tab_effects  = tk.Frame(nb, bg=BG1)
        tab_position = tk.Frame(nb, bg=BG1)
        for tab, label in [
            (tab_content, "Contenido"), (tab_color, "Color"),
            (tab_effects, "Efectos"), (tab_position, "Posición"),
        ]:
            tab.pack_propagate(True)
            nb.add(tab, text=label)

        self._build_text_content_tab(tab_content)
        self._build_text_color_tab(tab_color)
        self._build_text_effects_tab(tab_effects)
        self._build_text_position_tab(tab_position)

        # Initialize font preview
        self.after_idle(self._update_font_preview)

    def _build_text_content_tab(self, p):
        # ── Modo single-font (default) ────────────────────────────────────
        self._single_font_section = tk.Frame(p, bg=BG1)
        self._single_font_section.pack(fill="x")
        sf = self._single_font_section

        vcmd = (self.register(lambda P: len(P) <= 3), "%P")
        r = self._row(sf, pady=3)
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

        ttk.Separator(sf, orient="horizontal").pack(fill="x", pady=6)

        # Fuente
        r = self._row(sf)
        self._lbl(r, "Fuente:", w=12).pack(side="left")
        self.font_combo = ttk.Combobox(
            r, textvariable=self.selected_font,
            values=self.font_names, width=22
        )
        self.font_combo.pack(side="left", padx=(4, 4))
        self.font_combo.bind("<<ComboboxSelected>>", self._on_font_selected)
        self.font_combo.bind("<KeyRelease>", self._filter_fonts)
        _fp_btn = self._btn(r, "🔤", self._open_font_picker, bg=BG2, fg=AC2, width=3)
        _fp_btn.pack(side="left", padx=(0, 6))
        self._add_tooltip(_fp_btn, "Buscar fuentes (ventana completa con vista previa)")
        self._lbl(r, f"({len(self.font_names)})").pack(side="left")

        # Font preview label
        self._font_prev_lbl = tk.Label(sf, bg=BG2, relief="flat", bd=0)
        self._font_prev_lbl.pack(fill="x", padx=12, pady=(2, 4))
        self._tk_font_prev_img = None

        # ── Toggle multi-font ─────────────────────────────────────────────
        self._mf_toggle_row = self._row(p, pady=(2, 2))
        self._chk(self._mf_toggle_row, "🎨 Multi-font (font por letra)",
                  self.multi_font_var, cmd=self._on_multi_font_toggle).pack(side="left")

        # ── Panel multi-font (oculto por defecto) ─────────────────────────
        self._mf_frame = tk.Frame(p, bg=BG1)
        # NOT packed yet; revealed by _on_multi_font_toggle
        vcmd1 = (self.register(lambda P: len(P) <= 1), "%P")
        for i in range(3):
            col = tk.Frame(self._mf_frame, bg=BG2, relief="flat", bd=0)
            col.pack(side="left", expand=True, fill="x", padx=5, pady=4)
            self._lbl(col, f"Letra {i+1}", fg=ACC).pack(pady=(4, 2))
            tk.Entry(
                col, textvariable=self.mf_chars[i], width=3,
                validate="key", validatecommand=vcmd1,
                font=("Segoe UI", 18, "bold"),
                bg=BG1, fg=ACC, insertbackground=ACC,
                relief="flat", bd=4, justify="center"
            ).pack(pady=(0, 4))
            ttk.Combobox(
                col, textvariable=self.mf_fonts[i],
                values=self.font_names, state="readonly", width=14,
                font=("Segoe UI", 8)
            ).pack(pady=(0, 2), padx=4)
            _mf_fp_btn = self._btn(col, "🔤", lambda idx=i: self._open_font_picker_slot(idx),
                      bg=BG1, fg=AC2)
            _mf_fp_btn.pack(pady=(2, 4))
            self._add_tooltip(_mf_fp_btn, f"Elegir fuente para la letra {i+1}")
            sz_row = tk.Frame(col, bg=BG2)
            sz_row.pack(pady=(0, 2))
            self._lbl(sz_row, "Tam:", fg=TXS).pack(side="left")
            tk.Spinbox(
                sz_row, textvariable=self.mf_sizes[i],
                from_=10, to=200, width=4,
                bg=BG1, fg=TXP, relief="flat", bd=2,
                font=("Segoe UI", 9), buttonbackground=BG2
            ).pack(side="left", padx=(2, 0))
            self._lbl(sz_row, "%", fg=TXS).pack(side="left", padx=(2, 0))
            yo_row = tk.Frame(col, bg=BG2)
            yo_row.pack(pady=(0, 6))
            self._lbl(yo_row, "↕ Y:", fg=TXS).pack(side="left")
            tk.Spinbox(
                yo_row, textvariable=self.mf_offsets_y[i],
                from_=-50, to=50, width=4,
                bg=BG1, fg=TXP, relief="flat", bd=2,
                font=("Segoe UI", 9), buttonbackground=BG2
            ).pack(side="left", padx=(2, 0))
        # Traces for live preview
        for i in range(3):
            self.mf_chars[i].trace_add("write", lambda *_, idx=i: self._on_mf_change(idx))
            self.mf_fonts[i].trace_add("write",     lambda *_: self._refresh_text_preview())
            self.mf_sizes[i].trace_add("write",     self._refresh_text_preview_debounced)
            self.mf_offsets_y[i].trace_add("write", self._refresh_text_preview_debounced)

    def _build_text_color_tab(self, p):
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

        ttk.Separator(p, orient="horizontal").pack(fill="x", pady=(6, 4))

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
        self._add_tooltip(self._grad_btn1, "Color inicial del degradado")
        tk.Label(r, text="→", font=("Segoe UI", 10), fg=TXS, bg=BG1).pack(side="left", padx=2)
        self._grad_btn2 = tk.Button(
            r, text="  ", width=3, bg=self._gradient_color2,
            relief="flat", cursor="hand2", font=("Segoe UI", 8),
            command=self._pick_gradient_color2
        )
        self._grad_btn2.pack(side="left", padx=(0, 10))
        self._add_tooltip(self._grad_btn2, "Color final del degradado")
        self._lbl(r, "Dir:").pack(side="left")
        ttk.Combobox(
            r, textvariable=self.gradient_dir_var,
            values=["vertical", "horizontal", "diagonal ↘", "diagonal ↗", "radial"],
            state="readonly", width=12,
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

    def _build_text_effects_tab(self, p):
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

    def _build_text_position_tab(self, p):
        r = self._row(p, pady=(6, 0))
        self._lbl(r, "Posición:", w=12).pack(side="left")
        grid = tk.Frame(r, bg=BG1)
        grid.pack(side="left", padx=4)
        anchor_names = {
            "nw": "Arriba-izquierda", "n": "Arriba-centro", "ne": "Arriba-derecha",
            "w": "Centro-izquierda", "c": "Centro", "e": "Centro-derecha",
            "sw": "Abajo-izquierda", "s": "Abajo-centro", "se": "Abajo-derecha",
        }
        for i, (sym, anchor) in enumerate([
            ("↖","nw"),("↑","n"),("↗","ne"),
            ("←","w"), ("⊙","c"),("→","e"),
            ("↙","sw"),("↓","s"),("↘","se"),
        ]):
            _pos_btn = tk.Button(
                grid, text=sym, width=2,
                bg=BG2, fg=TXP, relief="flat", cursor="hand2",
                font=("Segoe UI", 9),
                command=lambda a=anchor: self._snap_text_pos(a)
            )
            _pos_btn.grid(row=i//3, column=i%3, padx=1, pady=1)
            self._add_tooltip(_pos_btn, anchor_names[anchor])

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
        r2 = self._row(p, pady=(2, 0))
        self._btn(r2, "⬆ Exportar…", self._export_preset, bg=BG2, fg=TXS).pack(side="left", padx=2)
        self._btn(r2, "⬇ Importar…", self._import_preset, bg=BG2, fg=TXS).pack(side="left", padx=2)

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
        self.src_canvas.bind("<Button-1>", self._on_canvas_button1)
        self.src_canvas.bind("<B1-Motion>", self._on_canvas_motion1)
        self.src_canvas.bind("<ButtonRelease-1>", self._on_canvas_release1)
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
        self._add_tooltip(
            self.src_canvas,
            "Arrastrar = mover texto  ·  Shift+click = tomar color\n"
            "Ctrl+click = reemplazar color  ·  Clic-derecho = mover split"
        )
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

        self._results_frame = frames_row = tk.Frame(parent, bg=BG0)
        frames_row.pack(fill="both", expand=True)

        ally_lf = tk.LabelFrame(
            frames_row, text=" Alliance (8×12) ",
            fg=AC2, bg=BG1, font=("Segoe UI", 9, "bold"), relief="solid", bd=1
        )
        ally_lf.pack(side="left", padx=(0, 12))
        self.ally_canvas = tk.Canvas(
            ally_lf,
            width=ALLY_SIZE[0] * PREVIEW_MULT,
            height=ALLY_SIZE[1] * PREVIEW_MULT,
            bg="black", highlightthickness=0, cursor="hand2"
        )
        self.ally_canvas.pack(padx=6, pady=6)
        self.ally_canvas.bind("<Button-1>", lambda _: self._show_zoom_popup("ally"))
        self._add_tooltip(self.ally_canvas, "Click para zoom")

        clan_lf = tk.LabelFrame(
            frames_row, text=" Clan (16×12) ",
            fg=ACC, bg=BG1, font=("Segoe UI", 9, "bold"), relief="solid", bd=1
        )
        clan_lf.pack(side="left")
        self.clan_canvas = tk.Canvas(
            clan_lf,
            width=CLAN_SIZE[0] * PREVIEW_MULT,
            height=CLAN_SIZE[1] * PREVIEW_MULT,
            bg="black", highlightthickness=0, cursor="hand2"
        )
        self.clan_canvas.pack(padx=6, pady=6)
        self.clan_canvas.bind("<Button-1>", lambda _: self._show_zoom_popup("clan"))
        self._add_tooltip(self.clan_canvas, "Click para zoom")

        frames_row.bind("<Configure>", self._on_results_resize)

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
        style.configure("TNotebook", background=BG1, borderwidth=0)
        style.configure("TNotebook.Tab",
                        background=BG2, foreground=TXS,
                        padding=(10, 4), font=("Segoe UI", 9))
        style.map("TNotebook.Tab",
                  background=[("selected", BG1)],
                  foreground=[("selected", ACC)])

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

    def _on_results_resize(self, event):
        if self._results_resize_after:
            self.after_cancel(self._results_resize_after)
        self._results_resize_after = self.after(
            150, self._do_results_resize, event.width, event.height
        )

    def _do_results_resize(self, w, h):
        self._results_resize_after = None
        # padding/gap allowance around the two LabelFrames (borders + padx/pady)
        avail_w = max(0, w - 40)
        avail_h = max(0, h - 20)
        if avail_w < 20 or avail_h < 20:
            return
        mult = max(6, min(60, min(avail_w / COMBINED_W, avail_h / ALLY_SIZE[1])))
        if abs(mult - self._result_disp_mult) < 0.5:
            return
        self._result_disp_mult = mult
        self.ally_canvas.config(
            width=int(ALLY_SIZE[0] * mult), height=int(ALLY_SIZE[1] * mult))
        self.clan_canvas.config(
            width=int(CLAN_SIZE[0] * mult), height=int(CLAN_SIZE[1] * mult))
        self._redraw_result_canvases()
