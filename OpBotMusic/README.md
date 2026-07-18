# OpBotMusic

Bot de Discord que sigue lo que suena en tu cuenta de Spotify: detecta la
cancion actual via la API de Spotify y la reproduce en un canal de voz de
Discord (buscandola en YouTube), para que tus amigos la escuchen con vos.

Spotify no permite extraer el audio real por API, asi que esto es un
**sync por metadata**: mismo tema, misma posicion aproximada, pero el audio
sale de YouTube, no directamente de Spotify.

## 1. Requisitos

- Python 3.11+
- [ffmpeg](https://ffmpeg.org/download.html) instalado y en el PATH
  (`ffmpeg -version` debe funcionar en una terminal)

```
pip install -r requirements.txt
```

## 2. Crear la app de Discord

1. Anda a https://discord.com/developers/applications > New Application.
2. Seccion **Bot** > Add Bot. Copia el **Token** (va en `DISCORD_TOKEN`).
3. Activa el intent **Message Content Intent** (necesario para los comandos `!sync`).
4. Seccion **OAuth2 > URL Generator**: marca scopes `bot`, y permisos
   `Connect`, `Speak`, `Send Messages`, `View Channels`. Abri la URL generada
   para invitar el bot a tu servidor.
5. Tu Discord user ID (activa "Modo desarrollador" en Discord > click derecho
   en tu nombre > Copy User ID) va en `OWNER_DISCORD_ID`.

## 3. Crear la app de Spotify

1. Anda a https://developer.spotify.com/dashboard > Create app.
2. Redirect URI: `http://127.0.0.1:8888/callback` (debe coincidir exacto con `.env`).
3. Copia **Client ID** y **Client Secret**.

## 4. Configurar

Copia `.env.example` a `.env` y completa los valores:

```
DISCORD_TOKEN=...
SPOTIFY_CLIENT_ID=...
SPOTIFY_CLIENT_SECRET=...
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
OWNER_DISCORD_ID=...
```

## 5. Login de Spotify (una sola vez)

```
python setup_spotify.py
```

Se abre el navegador, logueas con tu cuenta de Spotify y se guarda el token
en `.spotify_cache`. No hace falta repetirlo salvo que borres ese archivo.

## 6. Correr el bot

```
python bot.py
```

En Discord, con algo sonando en tu Spotify:

- Unite a un canal de voz y escribi `!sync` — el bot se une y empieza a
  reproducir lo mismo que escuchas.
- `!nowplaying` muestra la cancion actual y el progreso.
- `!stopsync` para cortar y desconectar al bot.

Solo el usuario configurado en `OWNER_DISCORD_ID` puede usar `!sync`,
`!stopsync` y `!nowplaying`.

`!play <nombre o link de YouTube>` lo puede usar cualquiera en el server:
pide una cancion puntual, pausa el sync mientras suena, y lo retoma
automaticamente al terminar. `!skip` corta ese pedido antes de que termine
(no aplica durante el sync normal con Spotify — ahi hay que cambiar la
cancion desde el propio Spotify).
