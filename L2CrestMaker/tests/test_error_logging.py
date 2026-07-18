import json

import L2CrestMaker as m


def test_save_json_success_returns_true_and_writes_file(tmp_path):
    path = tmp_path / "data.json"
    ok = m._save_json(str(path), {"a": 1})
    assert ok is True
    assert json.loads(path.read_text(encoding="utf-8")) == {"a": 1}


def test_save_json_failure_returns_false_and_logs(tmp_path, monkeypatch):
    log_path = tmp_path / "errors.log"
    monkeypatch.setattr(m, "ERROR_LOG_FILE", str(log_path))
    # A directory that doesn't exist as a parent makes the write fail.
    bad_path = str(tmp_path / "no_such_dir" / "data.json")

    ok = m._save_json(bad_path, {"a": 1})

    assert ok is False
    assert log_path.exists()
    assert "_save_json" in log_path.read_text(encoding="utf-8")


def test_log_error_appends_context_and_message(tmp_path, monkeypatch):
    log_path = tmp_path / "errors.log"
    monkeypatch.setattr(m, "ERROR_LOG_FILE", str(log_path))

    m._log_error("some_context", ValueError("boom"))
    m._log_error("some_context", ValueError("boom again"))

    content = log_path.read_text(encoding="utf-8")
    assert content.count("some_context") == 2
    assert "boom" in content and "boom again" in content


def test_log_error_never_raises_even_if_log_path_is_unwritable(tmp_path, monkeypatch):
    # Point the log at a path whose parent directory doesn't exist.
    monkeypatch.setattr(m, "ERROR_LOG_FILE", str(tmp_path / "missing" / "errors.log"))
    m._log_error("ctx", ValueError("boom"))  # must not raise


def test_save_current_preset_reports_failure_in_status_bar(app, monkeypatch):
    monkeypatch.setattr(m, "_save_json", lambda *a, **k: False)
    app.preset_name.set("Rojo")

    app._save_current_preset()

    assert "no se pudo" in app.status_var.get().lower()
    assert "Rojo" in app.presets  # kept in memory even though the disk write failed


def test_export_preset_shows_error_dialog_on_write_failure(app, tmp_path, monkeypatch):
    app.presets["Rojo"] = {"text_color": "#ff0000"}
    app.preset_name.set("Rojo")
    monkeypatch.setattr(m.filedialog, "asksaveasfilename",
                         lambda **kw: str(tmp_path / "out.json"))
    monkeypatch.setattr(m, "_save_json", lambda *a, **k: False)
    errors = []
    monkeypatch.setattr(m.messagebox, "showerror", lambda *a, **k: errors.append(a))

    app._export_preset()

    assert errors


def test_import_preset_reports_failure_in_status_bar(app, tmp_path, monkeypatch):
    src = tmp_path / "shared.json"
    src.write_text(json.dumps({"Nuevo": {"text_color": "#333333"}}), encoding="utf-8")
    monkeypatch.setattr(m.filedialog, "askopenfilename", lambda **kw: str(src))
    monkeypatch.setattr(m, "_save_json", lambda *a, **k: False)

    app._import_preset()

    assert "no se pudo" in app.status_var.get().lower()
    assert "Nuevo" in app.presets  # merged in memory even though the disk write failed
