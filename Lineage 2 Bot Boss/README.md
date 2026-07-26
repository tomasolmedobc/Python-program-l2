# 🐉 Epic Raid Boss Tracker

Bot de Discord para el servidor de Lineage 2 Chronicle 4 **Server Ares x3**. Registra las muertes de los Epic Raid Bosses (Queen Ant, Core, Orfen, Zaken, Baium, Antharas, Valakas), calcula sus próximas ventanas de spawn y avisa automáticamente cuando un boss entra en horario de aparición.

## Índice

1. [¿Qué hace el bot?](#1-qué-hace-el-bot)
2. [Arquitectura del proyecto](#2-arquitectura-del-proyecto)
3. [Requisitos previos](#3-requisitos-previos)
4. [Instalación local, paso a paso](#4-instalación-local-paso-a-paso)
5. [Comandos disponibles](#5-comandos-disponibles)
6. [Detección automática de texto](#6-detección-automática-de-texto)
7. [Alertas automáticas](#7-alertas-automáticas)
8. [Variables de entorno](#8-variables-de-entorno)
9. [Dejarlo 24/7 en un servidor Windows](#9-dejarlo-247-en-un-servidor-windows)
10. [Mantenimiento y problemas comunes](#10-mantenimiento-y-problemas-comunes)

---

## 1. ¿Qué hace el bot?

- Guarda la muerte de un boss (quién lo registró, cuándo) y calcula sola la ventana en la que puede volver a aparecer, usando el tiempo de respawn base ± la variación de cada boss.
- Muestra el estado de cada boss: 🔴 Muerto, 🟡 Spawn activo (puede salir ya), 🟢 Disponible.
- Detecta automáticamente frases como "QA muerto" o "Matamos Zaken" en un canal configurado, y pide confirmación con botones antes de registrar nada.
- Manda alertas automáticas (mencionando `@everyone` o un rol específico) cuando un boss entra en su horario de spawn, y sigue avisando si nadie confirma la muerte pasado ese horario.
- Lleva estadísticas reales de respawn (promedio, más rápido, más lento) basadas en el historial real del servidor, no solo en la teoría.
- Preparado para varios servidores de Discord a la vez: cada uno tiene su propio catálogo de bosses, canales, rol de alerta y zona horaria.

### Tiempos de respawn configurados

| Boss | Respawn base | Variación |
|---|---|---|
| Queen Ant | 36 h | ± 4 h |
| Core | 60 h | ± 2 h |
| Orfen | 48 h | ± 2 h |
| Zaken | 60 h | ± 4 h |
| Baium | 168 h | ± 5 h |
| Antharas | 264 h | ± 5 h |
| Valakas | 264 h | ± 5 h |

(Se definen en `src/config/bosses.config.js` y se siembran solos en la base de datos la primera vez que el bot entra a un servidor nuevo.)

## 2. Arquitectura del proyecto

```
src/
├── commands/       # Comandos de Discord (capa de presentación, solo leen opciones y responden)
│   └── raid/        # Un archivo por subcomando de /raid
├── events/         # Eventos de discord.js (ready, interactionCreate, messageCreate, guildCreate)
├── models/         # Esquemas de Mongoose (RaidBoss, KillHistory, GuildConfig)
├── services/       # Lógica de negocio, sin nada de Discord.js adentro
├── utils/          # Helpers puros: fechas, texto, permisos, embeds
├── config/         # Conexión a Mongo, variables de entorno, catálogo de bosses
├── client.js       # Arma el Client de discord.js y carga comandos/eventos
└── index.js        # Punto de entrada: conecta la DB y loguea el bot
deploy-commands.js  # Registra los slash commands en la API de Discord
ecosystem.config.js # Configuración de PM2 para correrlo 24/7
```

**Regla de oro:** los comandos nunca hablan directo con la base de datos ni calculan nada — solo llaman a un `service`. Así toda la lógica de negocio se puede reutilizar (por ejemplo, `/raid register` y la confirmación por botones de la detección automática usan exactamente el mismo `raidService.registerKill`).

El estado (🔴/🟡/🟢) de un boss **nunca se guarda** en la base — se calcula al momento, comparando la hora actual contra la ventana del último registro. Esto evita que quede desincronizado.

## 3. Requisitos previos

- **Node.js 18 o superior** ([nodejs.org](https://nodejs.org), o `winget install OpenJS.NodeJS.LTS` en Windows)
- Una cuenta de **MongoDB Atlas** (gratis) o un MongoDB propio
- Una aplicación de bot creada en el **[Discord Developer Portal](https://discord.com/developers/applications)**

## 4. Instalación local, paso a paso

### 4.1 Instalar dependencias

```
npm install
```

### 4.2 Crear la aplicación de Discord

1. Entrá a [discord.com/developers/applications](https://discord.com/developers/applications) → **New Application**.
2. Pestaña **General Information** → copiá el **Application ID** (es el `DISCORD_CLIENT_ID`).
3. Pestaña **Bot**:
   - **Reset Token** → copiá el token (es el `DISCORD_TOKEN`, **solo se muestra una vez**).
   - Activá **Message Content Intent** en "Privileged Gateway Intents" (necesario para la detección automática de texto).
   - En "Flujo de autorización", apagá **"Requiere concesión de código de autorización en OAuth2"** (si no, falla la invitación al servidor con el error "Integration requires code grant").
4. Pestaña **OAuth2 → URL Generator**:
   - Scopes: `bot` y `applications.commands`.
   - Bot Permissions: Ver canales, Enviar mensajes, Insertar enlaces, Leer historial de mensajes, Mencionar a todos, Usar comandos de barra diagonal, Usar aplicaciones externas.
   - Copiá la URL generada, abrila en el navegador y autorizá el bot en tu servidor.

### 4.3 Crear la base de datos en MongoDB Atlas

1. Cuenta gratis en [mongodb.com/cloud/atlas/register](https://mongodb.com/cloud/atlas/register).
2. Cluster gratuito **M0**.
3. **Database Access** → creá un usuario con contraseña.
4. **Network Access** → agregá `0.0.0.0/0` (o tu IP) a la lista de acceso.
5. **Connect → Drivers → Node.js** → copiá el connection string y reemplazá `<password>` por la contraseña real. Agregale el nombre de la base antes de los parámetros, ej: `.../l2-raidboss-bot?retryWrites=true&w=majority`.

### 4.4 Completar el archivo `.env`

Copiá `.env.example` a `.env` y completá:

```
DISCORD_TOKEN=       # el token del paso 4.2
DISCORD_CLIENT_ID=   # el Application ID del paso 4.2
DISCORD_GUILD_ID=    # opcional: ID de tu servidor, para que los comandos se vean al instante (si no, tardan hasta 1h en aparecer)
MONGODB_URI=         # el connection string del paso 4.3
TIMEZONE=America/Argentina/Buenos_Aires
```

**El `.env` nunca se sube a git** (está en `.gitignore`) porque tiene credenciales reales. Si alguna vez un token queda expuesto (por ejemplo, pegado sin querer en un chat), regenéralo de inmediato desde la pestaña Bot del Developer Portal.

### 4.5 Registrar los comandos

```
npm run deploy-commands
```

Si pusiste `DISCORD_GUILD_ID`, los comandos se registran solo en ese servidor (aparecen al instante). Sin esa variable, se registran globalmente (pueden tardar hasta 1 hora en aparecer).

### 4.6 Iniciar el bot

```
npm start
```

o doble click en `start-bot.bat` / el acceso directo del Escritorio.

## 5. Comandos disponibles

Todos son subcomandos de `/raid`. `/raid help` los explica dentro de Discord con ejemplos.

| Comando | Qué hace | Ejemplo | Requiere Admin |
|---|---|---|---|
| `/raid help` | Explica todos los comandos | `/raid help` | No |
| `/raid register` | Registra la muerte de un boss | `/raid register nombre:Queen Ant` | **Sí** |
| `/raid register` (retroactivo) | Registra una muerte pasada, si el bot estaba apagado | `/raid register nombre:Queen Ant fecha_hora:25/07 14:35` | **Sí** |
| `/raid list` | Muestra todos los bosses y su estado | `/raid list` | No |
| `/raid next` | Muestra el boss más próximo a aparecer | `/raid next` | No |
| `/raid stats` | Estadísticas reales de respawn | `/raid stats nombre:Antharas` | No |
| `/raid history` | Últimas muertes registradas | `/raid history nombre:Zaken` | No |
| `/raid delete` | Deshace el último registro de un boss | `/raid delete nombre:Core` | **Sí** |
| `/raid config` | Configura canales, rol de alerta y zona horaria | `/raid config canal_alertas:#alerta-epico` | **Sí** (Gestionar servidor) |

El campo `nombre` tiene autocompletado: al escribir, Discord sugiere los bosses reales del servidor.

### `/raid config`, todas las opciones

| Opción | Para qué sirve |
|---|---|
| `canal_anuncios` | Canal donde se publica el embed cada vez que se registra una muerte |
| `canal_deteccion` | Canal donde el bot lee mensajes buscando frases de muerte (Fase 2) |
| `canal_alertas` | Canal donde se mandan las alertas de spawn activo (Fase 3) |
| `rol_alerta` | Rol a mencionar en las alertas (si no se configura, usa `@everyone`) |
| `zona_horaria` | Zona horaria IANA del servidor, ej. `America/Argentina/Buenos_Aires` |

Corriendo `/raid config` sin ninguna opción, muestra la configuración actual.

## 6. Detección automática de texto

Si configuraste `canal_deteccion`, el bot lee los mensajes de ese canal y busca **una palabra de "muerte" + el nombre o alias de un boss** en el mismo mensaje (ej. "QA muerto", "Zaken down", "Matamos Core", "La reina murió"). Mencionar solo el nombre del boss sin ningún contexto de muerte no dispara nada, para evitar falsos positivos en charla normal.

Cuando detecta una posible muerte, responde con un embed y dos botones:
- **✅ Confirmar** — solo lo puede usar un Administrador; registra la muerte igual que `/raid register`.
- **❌ Cancelar** — lo puede usar cualquiera; descarta el falso positivo.

Si nadie responde en 2 minutos, los botones se desactivan solos.

Los alias de cada boss están en `src/config/bosses.config.js` (campo `aliases`).

## 7. Alertas automáticas

Un cron job (configurable, cada 15 minutos por defecto) revisa todos los bosses de cada servidor con `canal_alertas` configurado:

- **🟡 Spawn activo**: si el boss está dentro de su ventana calculada, manda una alerta y la repite cada 1 hora mientras siga en esa ventana.
- **🔺 Superó su spawn estimado**: si pasó la ventana calculada y nadie registró la muerte, sigue avisando cada 1 hora — a diferencia de `/raid list` (que ya lo muestra como 🟢 Disponible), esta alerta no da por hecho que "no pasó nada".

Ambas alertas se detienen apenas alguien registra la muerte real con `/raid register` (o confirma la detección automática).

## 8. Variables de entorno

| Variable | Obligatoria | Descripción |
|---|---|---|
| `DISCORD_TOKEN` | Sí | Token del bot |
| `DISCORD_CLIENT_ID` | Sí | Application ID |
| `DISCORD_GUILD_ID` | No | Si se define, los comandos se registran solo en ese servidor (propagación instantánea) |
| `MONGODB_URI` | Sí | Connection string de MongoDB |
| `TIMEZONE` | No | Zona horaria por defecto para servidores nuevos (default `America/Bogota`) |
| `ALERT_CHECK_CRON` | No | Expresión cron de cada cuánto se revisan las ventanas activas (default `*/15 * * * *`) |

## 9. Dejarlo 24/7 en un servidor Windows

Para que el bot quede corriendo solo, se reinicie si se cae, y vuelva a arrancar solo si el servidor se reinicia:

1. **Copiar el proyecto al servidor**, incluyendo el `.env` (no viaja por git, hay que copiarlo a mano). No hace falta copiar `node_modules`.
2. **Instalar Node.js** en el servidor, si no lo tiene.
3. Abrir una terminal en la carpeta del proyecto y correr:
   ```
   npm install
   npm install -g pm2
   npm install -g pm2-windows-startup
   pm2-startup install
   ```
4. **Iniciar el bot con PM2** (usa `ecosystem.config.js`, ya incluido en el proyecto):
   ```
   pm2 start ecosystem.config.js
   pm2 save
   ```

Con `pm2 save`, PM2 recuerda qué debe estar corriendo. `pm2-startup install` hace que, al prender el servidor, PM2 arranque solo y reviva el bot — sin que nadie tenga que loguearse ni hacer click en nada.

### Comandos útiles de PM2

```
pm2 list                          # ver si está corriendo
pm2 logs l2-raidboss-bot          # ver logs en vivo
pm2 restart l2-raidboss-bot       # reiniciarlo
pm2 stop l2-raidboss-bot          # detenerlo
```

También podés usar el acceso directo `bot-status.bat` (muestra estado + últimos 50 logs de una).

## 10. Mantenimiento y problemas comunes

- **"Used disallowed intents" al arrancar** → falta activar "Message Content Intent" en la pestaña Bot del Developer Portal.
- **"Integration requires code grant" al invitar el bot** → apagá "Requiere concesión de código de autorización en OAuth2" en la pestaña Bot.
- **El bot no detecta que se unió a un servidor nuevo** → asegurate de haber usado **OAuth2 → URL Generator** con el scope `bot` marcado, no un link de instalación que solo tenga `applications.commands`.
- **Comando duplicado en Discord** → pasa si el comando quedó registrado a la vez global y por servidor. Corré un script puntual con `rest.put(Routes.applicationCommands(clientId), { body: [] })` para vaciar el registro global y dejar solo el de servidor.
- **Corregir un registro de muerte mal cargado** → `/raid delete nombre:<boss>` deshace el último registro de ese boss.
- **Un registro con `fecha_hora` no cambia nada en `/raid list`** → el sistema siempre usa el registro con la fecha de muerte más reciente, no el que se cargó más recientemente en el tiempo real. Si registrás una fecha más vieja que la que ya está activa, el bot lo rechaza y te lo avisa.
- **Cambiar la zona horaria de un servidor ya configurado** → `/raid config zona_horaria:America/Argentina/Buenos_Aires` (o la que corresponda).
- **Rotar el token si quedó expuesto** → Developer Portal → Bot → Reset Token → actualizar `DISCORD_TOKEN` en el `.env` → reiniciar el bot (`pm2 restart l2-raidboss-bot` si está en el servidor).
