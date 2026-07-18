"""Busca una cancion en YouTube y devuelve la URL directa del audio."""

import glob
import os
import shutil

import yt_dlp

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}


def _find_winget_binary(package_glob: str, binary_name: str) -> str:
    found = shutil.which(binary_name)
    if found:
        return found
    # Recien instalado via winget en esta sesion: el PATH del proceso actual
    # todavia no se actualizo, buscamos el binario directo como fallback.
    candidates = glob.glob(os.path.expandvars(package_glob))
    return candidates[0] if candidates else binary_name


FFMPEG_EXECUTABLE = _find_winget_binary(
    r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg_*\ffmpeg-*\bin\ffmpeg.exe", "ffmpeg"
)
DENO_EXECUTABLE = _find_winget_binary(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\DenoLand.Deno_*\deno.exe", "deno")

_YDL_OPTS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "default_search": "ytsearch1",
    "extract_flat": False,
    "js_runtimes": {"deno": {"path": DENO_EXECUTABLE}},
}


def search_audio_url(query: str) -> str:
    with yt_dlp.YoutubeDL(_YDL_OPTS) as ydl:
        info = ydl.extract_info(query, download=False)
        if "entries" in info:
            info = info["entries"][0]
        return info["url"]
