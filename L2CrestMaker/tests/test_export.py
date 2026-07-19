import os

from PIL import Image

import L2CrestMaker as m
import app_export


def _make_source(folder, name="src.png", size=(200, 200), color=(30, 120, 200, 255)):
    os.makedirs(str(folder), exist_ok=True)
    path = os.path.join(str(folder), name)
    Image.new("RGBA", size, color).save(path)
    return path


def test_run_save_writes_clan_and_ally_bmp(app, tmp_path):
    src = _make_source(tmp_path)
    app.src_path.set(src)
    clan_dest = tmp_path / "clan.bmp"
    ally_dest = tmp_path / "ally.bmp"
    app.clan_path.set(str(clan_dest))
    app.ally_path.set(str(ally_dest))

    app._run(save=True)

    assert clan_dest.exists()
    assert ally_dest.exists()
    assert "Convertido" in app.status_var.get()


def test_run_preview_does_not_write_files(app, tmp_path):
    src = _make_source(tmp_path)
    app.src_path.set(src)
    clan_dest = tmp_path / "clan.bmp"
    app.clan_path.set(str(clan_dest))
    app.ally_path.set(str(tmp_path / "ally.bmp"))

    app._run(save=False)

    assert not clan_dest.exists()
    assert app._last_clan_img is not None
    assert app._last_ally_img is not None


def test_run_without_source_shows_error_and_writes_nothing(app, monkeypatch):
    errors = []
    monkeypatch.setattr(m.messagebox, "showerror", lambda *a, **k: errors.append(a))
    app.src_path.set("")

    app._run(save=True)

    assert errors


def test_run_appends_to_export_history_on_successful_save(app, tmp_path):
    src = _make_source(tmp_path)
    app.src_path.set(src)
    app.clan_path.set(str(tmp_path / "clan.bmp"))
    app.ally_path.set(str(tmp_path / "ally.bmp"))
    app._export_history = []

    app._run(save=True)

    assert len(app._export_history) == 1
    assert app._export_history[0]["src"] == src


def test_process_batch_converts_every_image_in_folder(app, tmp_path, monkeypatch):
    src_dir = tmp_path / "srcs"
    out_dir = tmp_path / "out"
    for i in range(3):
        _make_source(src_dir, name=f"img{i}.png")
    monkeypatch.setattr(app_export, "OUTPUT_DIR", str(out_dir))
    monkeypatch.setattr(m.filedialog, "askdirectory", lambda **kw: str(src_dir))

    app._process_batch()

    files = os.listdir(out_dir)
    assert sum(f.endswith("_clan.bmp") for f in files) == 3
    assert sum(f.endswith("_ally.bmp") for f in files) == 3
    assert "3 OK" in app.status_var.get()


def test_process_batch_no_folder_selected_does_nothing(app, monkeypatch):
    monkeypatch.setattr(m.filedialog, "askdirectory", lambda **kw: "")
    app._process_batch()  # must not raise


def test_process_batch_empty_folder_shows_info_and_does_not_crash(app, tmp_path, monkeypatch):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    monkeypatch.setattr(m.filedialog, "askdirectory", lambda **kw: str(empty_dir))
    infos = []
    monkeypatch.setattr(m.messagebox, "showinfo", lambda *a, **k: infos.append(a))

    app._process_batch()

    assert infos
