import json

import L2CrestMaker as m


def test_export_preset_writes_selected_preset_only(app, tmp_path, monkeypatch):
    app.presets["Rojo"] = {"text_color": "#ff0000"}
    app.presets["Azul"] = {"text_color": "#0000ff"}
    app.preset_name.set("Rojo")

    dest = tmp_path / "rojo_export.json"
    monkeypatch.setattr(m.filedialog, "asksaveasfilename", lambda **kw: str(dest))

    app._export_preset()

    data = json.loads(dest.read_text(encoding="utf-8"))
    assert data == {"Rojo": {"text_color": "#ff0000"}}


def test_export_preset_without_saved_preset_shows_warning(app, monkeypatch):
    app.preset_name.set("NoExiste")
    warned = []
    monkeypatch.setattr(m.messagebox, "showwarning", lambda *a, **k: warned.append(a))

    app._export_preset()

    assert warned


def test_import_preset_merges_into_existing_presets(app, tmp_path, monkeypatch):
    src = tmp_path / "shared.json"
    src.write_text(json.dumps({"DelClan": {"text_color": "#00ff00"}}), encoding="utf-8")
    monkeypatch.setattr(m.filedialog, "askopenfilename", lambda **kw: str(src))

    app._import_preset()

    assert app.presets["DelClan"] == {"text_color": "#00ff00"}
    assert "DelClan" in app.preset_combo["values"]


def test_import_preset_rejects_invalid_file(app, tmp_path, monkeypatch):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(["not", "a", "dict"]), encoding="utf-8")
    monkeypatch.setattr(m.filedialog, "askopenfilename", lambda **kw: str(bad))
    errors = []
    monkeypatch.setattr(m.messagebox, "showerror", lambda *a, **k: errors.append(a))

    before = dict(app.presets)
    app._import_preset()

    assert errors
    assert app.presets == before


def test_import_preset_asks_before_overwriting_existing_name(app, tmp_path, monkeypatch):
    app.presets["DelClan"] = {"text_color": "#111111"}
    src = tmp_path / "shared.json"
    src.write_text(json.dumps({"DelClan": {"text_color": "#222222"}}), encoding="utf-8")
    monkeypatch.setattr(m.filedialog, "askopenfilename", lambda **kw: str(src))

    asked = []
    monkeypatch.setattr(m.messagebox, "askyesno",
                         lambda *a, **k: asked.append(a) or False)

    app._import_preset()

    assert asked
    assert app.presets["DelClan"] == {"text_color": "#111111"}  # declined → unchanged


def test_import_preset_applies_when_overwrite_accepted(app, tmp_path, monkeypatch):
    app.presets["DelClan"] = {"text_color": "#111111"}
    src = tmp_path / "shared.json"
    src.write_text(json.dumps({"DelClan": {"text_color": "#222222"}}), encoding="utf-8")
    monkeypatch.setattr(m.filedialog, "askopenfilename", lambda **kw: str(src))
    monkeypatch.setattr(m.messagebox, "askyesno", lambda *a, **k: True)

    app._import_preset()

    assert app.presets["DelClan"] == {"text_color": "#222222"}  # accepted → overwritten


def test_import_preset_declining_overwrite_still_imports_non_colliding_ones(app, tmp_path, monkeypatch):
    app.presets["DelClan"] = {"text_color": "#111111"}
    src = tmp_path / "shared.json"
    src.write_text(json.dumps({
        "DelClan": {"text_color": "#222222"},
        "Nuevo":   {"text_color": "#333333"},
    }), encoding="utf-8")
    monkeypatch.setattr(m.filedialog, "askopenfilename", lambda **kw: str(src))
    monkeypatch.setattr(m.messagebox, "askyesno", lambda *a, **k: False)

    app._import_preset()

    assert app.presets["DelClan"] == {"text_color": "#111111"}  # declined → unchanged
    assert app.presets["Nuevo"] == {"text_color": "#333333"}    # not colliding → imported anyway


def test_export_preset_cancel_dialog_does_nothing(app, tmp_path, monkeypatch):
    app.presets["Rojo"] = {"text_color": "#ff0000"}
    app.preset_name.set("Rojo")
    monkeypatch.setattr(m.filedialog, "asksaveasfilename", lambda **kw: "")

    app._export_preset()  # should return silently, no exception

    assert list(tmp_path.iterdir()) == []


def test_import_preset_cancel_dialog_does_nothing(app, monkeypatch):
    monkeypatch.setattr(m.filedialog, "askopenfilename", lambda **kw: "")
    before = dict(app.presets)

    app._import_preset()  # should return silently, no exception

    assert app.presets == before
