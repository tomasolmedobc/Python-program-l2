"""Bot de Discord que sigue lo que suena en la cuenta de Spotify del dueno.

Comandos:
    !sync       - el dueno debe estar en un canal de voz; el bot se une y
                  empieza a reproducir ahi lo mismo que suena en su Spotify.
    !play <q>   - cualquiera puede pedir una cancion puntual de YouTube;
                  pausa el sync mientras suena y lo retoma al terminar.
    !skip       - corta el pedido de !play que esta sonando.
    !nowplaying - muestra que esta sonando en el Spotify seguido.
    !stopsync   - corta el sync y desconecta al bot del canal de voz.
"""

import asyncio
import os
import time
from typing import Optional

import discord
from discord.ext import commands
from dotenv import load_dotenv

from spotify_client import SpotifyClient, TrackInfo
from youtube_source import FFMPEG_EXECUTABLE, FFMPEG_OPTIONS, search_audio_url

load_dotenv()

OWNER_DISCORD_ID = int(os.environ["OWNER_DISCORD_ID"])
POLL_INTERVAL_SECONDS = 3
DRIFT_THRESHOLD_SECONDS = 5

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
spotify = SpotifyClient()

_sync_task: Optional[asyncio.Task] = None
_manual_override = False


def _is_owner(ctx: commands.Context) -> bool:
    return ctx.author.id == OWNER_DISCORD_ID


def _format_mmss(seconds: float) -> str:
    total = int(seconds)
    return f"{total // 60}:{total % 60:02d}"


async def _play_track(voice_client: discord.VoiceClient, track: TrackInfo, seek_seconds: float) -> None:
    loop = asyncio.get_running_loop()
    url = await loop.run_in_executor(None, search_audio_url, track.query)
    before_options = f"{FFMPEG_OPTIONS['before_options']} -ss {seek_seconds:.1f}"
    source = discord.FFmpegPCMAudio(
        url, executable=FFMPEG_EXECUTABLE, before_options=before_options, options=FFMPEG_OPTIONS["options"]
    )
    if voice_client.is_playing() or voice_client.is_paused():
        voice_client.stop()
    voice_client.play(source)


async def _sync_loop(voice_client: discord.VoiceClient, text_channel: discord.abc.Messageable) -> None:
    loop = asyncio.get_running_loop()
    last_track_id: Optional[str] = None
    track_started_at: Optional[float] = None
    expected_progress_at_start = 0.0

    while True:
        if _manual_override:
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            continue

        try:
            track = await loop.run_in_executor(None, spotify.get_current_playback)
        except Exception as exc:
            await text_channel.send(f"Error consultando Spotify: {exc}")
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            continue

        if track is None or not track.is_playing:
            if voice_client.is_playing():
                voice_client.pause()
            last_track_id = None
            track_started_at = None
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            continue

        if voice_client.is_paused():
            voice_client.resume()

        progress_seconds = track.progress_ms / 1000

        if track.track_id != last_track_id:
            try:
                await _play_track(voice_client, track, progress_seconds)
            except Exception as exc:
                await text_channel.send(f"No pude reproducir '{track.query}': {exc}")
                await asyncio.sleep(POLL_INTERVAL_SECONDS)
                continue
            await text_channel.send(f"Sonando ahora: **{track.query}**")
            last_track_id = track.track_id
            track_started_at = time.monotonic()
            expected_progress_at_start = progress_seconds
        elif track_started_at is not None:
            elapsed = time.monotonic() - track_started_at
            expected = expected_progress_at_start + elapsed
            stalled = not voice_client.is_playing() and not voice_client.is_paused()
            if stalled or abs(progress_seconds - expected) > DRIFT_THRESHOLD_SECONDS:
                try:
                    await _play_track(voice_client, track, progress_seconds)
                except Exception as exc:
                    await text_channel.send(f"No pude re-sincronizar: {exc}")
                    await asyncio.sleep(POLL_INTERVAL_SECONDS)
                    continue
                track_started_at = time.monotonic()
                expected_progress_at_start = progress_seconds

        await asyncio.sleep(POLL_INTERVAL_SECONDS)


@bot.command(name="sync")
async def sync_command(ctx: commands.Context) -> None:
    global _sync_task

    if not _is_owner(ctx):
        await ctx.send("Solo el dueno del bot puede usar este comando.")
        return

    if ctx.author.voice is None or ctx.author.voice.channel is None:
        await ctx.send("Tenes que estar en un canal de voz primero.")
        return

    if _sync_task is not None and not _sync_task.done():
        await ctx.send("Ya estoy sincronizando. Usa !stopsync para cortar.")
        return

    channel = ctx.author.voice.channel
    voice_client = ctx.voice_client or await channel.connect()
    if voice_client.channel != channel:
        await voice_client.move_to(channel)

    await ctx.send(f"Conectado a **{channel.name}**. Siguiendo tu Spotify...")
    _sync_task = asyncio.create_task(_sync_loop(voice_client, ctx.channel))


@bot.command(name="stopsync")
async def stopsync_command(ctx: commands.Context) -> None:
    global _sync_task

    if not _is_owner(ctx):
        await ctx.send("Solo el dueno del bot puede usar este comando.")
        return

    if _sync_task is not None:
        _sync_task.cancel()
        _sync_task = None

    if ctx.voice_client is not None:
        await ctx.voice_client.disconnect()

    await ctx.send("Sync detenido.")


@bot.command(name="play")
async def play_command(ctx: commands.Context, *, query: str) -> None:
    global _manual_override

    if ctx.author.voice is None or ctx.author.voice.channel is None:
        await ctx.send("Tenes que estar en un canal de voz primero.")
        return

    channel = ctx.author.voice.channel
    voice_client = ctx.voice_client or await channel.connect()
    if voice_client.channel != channel:
        await voice_client.move_to(channel)

    try:
        loop = asyncio.get_running_loop()
        url = await loop.run_in_executor(None, search_audio_url, query)
    except Exception as exc:
        await ctx.send(f"No pude encontrar '{query}': {exc}")
        return

    _manual_override = True
    if voice_client.is_playing() or voice_client.is_paused():
        voice_client.stop()

    finished = asyncio.Event()

    def _on_finished(error: Optional[Exception]) -> None:
        bot.loop.call_soon_threadsafe(finished.set)

    source = discord.FFmpegPCMAudio(
        url, executable=FFMPEG_EXECUTABLE, before_options=FFMPEG_OPTIONS["before_options"], options=FFMPEG_OPTIONS["options"]
    )
    voice_client.play(source, after=_on_finished)
    await ctx.send(f"Reproduciendo pedido de {ctx.author.display_name}: **{query}**")

    await finished.wait()
    _manual_override = False
    if _sync_task is not None and not _sync_task.done():
        await ctx.send("Listo, retomo el sync con Spotify.")


@bot.command(name="skip")
async def skip_command(ctx: commands.Context) -> None:
    voice_client = ctx.voice_client
    if voice_client is None or not (voice_client.is_playing() or voice_client.is_paused()):
        await ctx.send("No hay nada sonando ahora mismo.")
        return

    if not _manual_override:
        await ctx.send(
            "Estoy siguiendo tu Spotify, no un pedido de !play. "
            "Para saltar esta cancion, cambiala desde Spotify y te sigo."
        )
        return

    voice_client.stop()
    await ctx.send("Salteado.")


@bot.command(name="nowplaying")
async def nowplaying_command(ctx: commands.Context) -> None:
    if not _is_owner(ctx):
        await ctx.send("Solo el dueno del bot puede usar este comando.")
        return

    loop = asyncio.get_running_loop()
    track = await loop.run_in_executor(None, spotify.get_current_playback)
    if track is None:
        await ctx.send("No hay nada sonando en Spotify ahora mismo.")
        return

    estado = "sonando" if track.is_playing else "pausado"
    progreso = _format_mmss(track.progress_ms / 1000)
    duracion = _format_mmss(track.duration_ms / 1000)
    await ctx.send(f"**{track.query}** ({estado}) — {progreso} / {duracion}")


@bot.event
async def on_ready() -> None:
    print(f"Conectado como {bot.user}")


if __name__ == "__main__":
    bot.run(os.environ["DISCORD_TOKEN"])
