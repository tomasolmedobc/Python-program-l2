# L2 Crest Maker

Herramienta de escritorio (Tkinter) para generar crests de clan/alianza de
Lineage 2 a partir de una imagen fuente: recorta, convierte a BMP de 256
colores en las medidas exactas que usa el juego (Clan 16×12, Ally 8×12),
permite agregar texto/iniciales con múltiples fuentes, degradados, contorno,
overlays, plantillas, ajustes de color y exportación por lote.

## Requisitos

- Python 3.10+
- Windows (usa `winreg`, `ctypes` para portapapeles, y accesos directos
  `.lnk` — no es portable a otros SO tal cual está)

## Correr desde código fuente

```
pip install -r requirements.txt
python L2CrestMaker.py
```

`tkinterdnd2` (listado en `requirements.txt`) es opcional: sin él la app
funciona igual, solo se pierde el drag&drop de imágenes sobre la ventana.

### Variables de entorno (opcionales)

| Variable | Default | Uso |
|---|---|---|
| `L2CREST_OUTPUT_DIR` | `E:\L2CyA` | Carpeta donde se guardan los BMP generados |
| `L2CREST_FONTS_DIR` | `C:\Windows\Fonts` | Carpeta de búsqueda de fuentes del sistema |
| `L2CREST_OVERLAYS_DIR` | `<carpeta de la app>\overlays` | Galería de overlays |
| `L2CREST_TEMPLATES_DIR` | `<carpeta de la app>\templates` | Galería de plantillas |

Los defaults de `OUTPUT_DIR`/`FONTS_DIR` reflejan la máquina original de
desarrollo — ajustalos con estas variables si corrés la app en otra PC.

## Tests

```
pip install -r requirements-dev.txt
pytest
```

## Empaquetar como .exe

El repo incluye `L2CrestMaker.spec`, ya configurado para incluir los datos
que `tkinterdnd2` necesita (si no se incluyen, el import falla silenciosamente
y la app pierde el drag&drop).

```
pip install pyinstaller
python -m PyInstaller L2CrestMaker.spec
```

Esto genera `dist/L2CrestMaker/L2CrestMaker.exe` (modo *onedir*: el `.exe`
más una carpeta `_internal/` con las dependencias). **Onedir** se eligió
sobre *onefile* porque la app lee/escribe archivos junto al ejecutable
(presets, sesión, historial reciente, galerías de overlays/plantillas) — con
onefile esos datos vivirían en una carpeta temporal que Windows borra al
cerrar el proceso.

Después del build, copiá manualmente estos archivos/carpetas a
`dist/L2CrestMaker/` (mismo nivel que el `.exe`, **no** dentro de
`_internal/`, que PyInstaller trata como de solo lectura):

```
l2crest.ico
overlays/
templates/
```

Opcionalmente, si querés que el `.exe` arranque con tus presets/recientes
actuales en vez de vacío:

```
l2crest_presets.json
l2crest_recent.json
```

La app resuelve `_HERE` (dónde busca/guarda todo esto) como la carpeta del
`.exe` cuando corre empaquetada, así que una vez copiados esos archivos el
`.exe` es autocontenido y movible como carpeta completa.

Para volver a generar el `.exe` tras cambios en el código, repetí el comando
de PyInstaller — no hace falta repetir la copia manual si ya está hecha una
vez y el build no borra `dist/` (usá `--noconfirm` si querés que sobrescriba
sin preguntar).

## Estructura del código

- `L2CrestMaker.py` — constantes, funciones puras de procesamiento de imagen,
  y el shell de la clase principal (`__init__`, sesión, cierre, acceso directo).
- `app_presets.py`, `app_files.py`, `app_export.py`, `app_editing.py`,
  `app_text.py`, `app_preview.py`, `app_ui.py` — mixins que componen
  `L2CrestApp`, cada uno con una responsabilidad (presets, archivos/galería,
  exportación, edición de imagen, texto, previews, construcción de UI).
- `tests/` — suite de pytest (cobertura automatizada actual: presets y
  galería de archivos; el resto de las funciones se verifica manualmente).
