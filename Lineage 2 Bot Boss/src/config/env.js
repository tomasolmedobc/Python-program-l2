require('dotenv').config();

const required = ['DISCORD_TOKEN', 'DISCORD_CLIENT_ID', 'MONGODB_URI'];

const missing = required.filter((key) => !process.env[key]);
if (missing.length > 0) {
  throw new Error(`Faltan variables de entorno requeridas: ${missing.join(', ')}`);
}

module.exports = {
  discordToken: process.env.DISCORD_TOKEN,
  discordClientId: process.env.DISCORD_CLIENT_ID,
  // Opcional: si se define, deploy-commands.js registra los comandos solo
  // en este servidor (propagación instantánea, ideal para desarrollo).
  discordGuildId: process.env.DISCORD_GUILD_ID || null,
  mongodbUri: process.env.MONGODB_URI,
  timezone: process.env.TIMEZONE || 'America/Bogota',
  // Expresión cron de qué tan seguido se revisa si algún boss entró en
  // ventana activa. Por defecto cada 15 min; para probar rápido se puede
  // bajar a '*/1 * * * *' (cada 1 min) en el .env.
  alertCheckCron: process.env.ALERT_CHECK_CRON || '*/15 * * * *',
};
