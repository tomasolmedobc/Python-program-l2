"""Script de un solo uso: hace el login OAuth con Spotify y cachea el token.

Correr con: python setup_spotify.py
Abre el navegador, pide loguearse con Spotify, y guarda el refresh token
en .spotify_cache. Una vez hecho esto, bot.py puede refrescar el token
automaticamente sin volver a pedir login.
"""

import os

from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyOAuth

from spotify_client import SCOPE, CACHE_PATH

load_dotenv()


def main() -> None:
    client_id = os.environ["SPOTIFY_CLIENT_ID"]
    client_secret = os.environ["SPOTIFY_CLIENT_SECRET"]
    redirect_uri = os.environ["SPOTIFY_REDIRECT_URI"]

    auth_manager = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=SCOPE,
        cache_path=CACHE_PATH,
        open_browser=True,
    )

    # Esto dispara el flujo de login en el navegador y cachea el token.
    auth_manager.get_access_token(as_dict=False)
    print(f"Listo. Token cacheado en {CACHE_PATH}. Ya podes correr bot.py.")


if __name__ == "__main__":
    main()
