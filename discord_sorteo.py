import discord
import random
import re
import asyncio

# ─── CONFIGURACIÓN ────────────────────────────────────────────────
TOKEN = "TU_TOKEN_AQUI"   # Token del bot de Discord
PREFIX = "!"
# ──────────────────────────────────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

client = discord.Client(intents=intents)


def parse_message_link(link: str):
    """Extrae guild_id, channel_id y message_id de un enlace de Discord."""
    match = re.search(r"discord(?:app)?\.com/channels/(\d+)/(\d+)/(\d+)", link)
    if match:
        return int(match.group(1)), int(match.group(2)), int(match.group(3))
    return None, None, None


@client.event
async def on_ready():
    print(f"Bot conectado como {client.user}")


@client.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.content.startswith(PREFIX + "sorteo"):
        return

    # Uso: !sorteo <enlace_del_mensaje> [emoji]
    parts = message.content.split()
    if len(parts) < 2:
        await message.channel.send(
            "**Uso:** `!sorteo <enlace_del_mensaje> [emoji]`\n"
            "Ejemplo: `!sorteo https://discord.com/channels/.../... 🎉`"
        )
        return

    link = parts[1]
    emoji_filtro = parts[2] if len(parts) >= 3 else None

    guild_id, channel_id, message_id = parse_message_link(link)
    if not message_id:
        await message.channel.send("No pude leer el enlace. Asegúrate de copiar el enlace completo del mensaje.")
        return

    channel = client.get_channel(channel_id)
    if channel is None:
        await message.channel.send("No tengo acceso a ese canal.")
        return

    try:
        target_msg = await channel.fetch_message(message_id)
    except discord.NotFound:
        await message.channel.send("No encontré ese mensaje.")
        return
    except discord.Forbidden:
        await message.channel.send("No tengo permisos para leer ese mensaje.")
        return

    if not target_msg.reactions:
        await message.channel.send("Ese mensaje no tiene reacciones.")
        return

    # Recopilar participantes (sin bots y sin duplicados)
    participantes: set[discord.User] = set()

    for reaction in target_msg.reactions:
        # Si se especificó un emoji, filtrar solo ese
        if emoji_filtro and str(reaction.emoji) != emoji_filtro:
            continue
        async for user in reaction.users():
            if not user.bot:
                participantes.add(user)

    if not participantes:
        filtro_txt = f" con la reacción {emoji_filtro}" if emoji_filtro else ""
        await message.channel.send(f"No hay participantes válidos{filtro_txt}.")
        return

    ganador = random.choice(list(participantes))

    emoji_txt = f" ({emoji_filtro})" if emoji_filtro else ""
    embed = discord.Embed(
        title="🎉 ¡Sorteo finalizado!",
        color=discord.Color.gold(),
    )
    embed.add_field(name="Reacción sorteada", value=emoji_txt or "todas", inline=True)
    embed.add_field(name="Participantes", value=str(len(participantes)), inline=True)
    embed.add_field(name="🏆 Ganador", value=ganador.mention, inline=False)
    embed.set_footer(text=f"Solicitado por {message.author.display_name}")

    await message.channel.send(embed=embed)


client.run(TOKEN)
