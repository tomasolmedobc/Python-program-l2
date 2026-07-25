const cron = require('node-cron');
const GuildConfig = require('../models/GuildConfig');
const raidService = require('./raidService');
const { STATUS } = require('./calculatorService');
const { windowAlertEmbed, overdueAlertEmbed } = require('../utils/embeds');
const { alertCheckCron } = require('../config/env');
const logger = require('../utils/logger');

// No se reenvía una alerta para el mismo kill antes de que pase esta cantidad
// de tiempo, aunque el cron corra con más frecuencia que esto.
const ALERT_THROTTLE_MS = 60 * 60 * 1000;

async function checkGuildAlerts(client, guildConfig) {
  const channel = await client.channels.fetch(guildConfig.alertChannelId).catch(() => null);
  if (!channel?.isTextBased()) return;

  const bossesWithStatus = await raidService.getAllBossesWithStatus(guildConfig.guildId);
  const now = new Date();

  for (const { boss, lastKill, status } of bossesWithStatus) {
    const isActiveWindow = status === STATUS.ACTIVE_WINDOW;
    // 🔺 Superó spawnMax sin que nadie registrara la muerte: sigue avisando
    // (a diferencia de /raid list, que ahí ya lo muestra como 🟢 Disponible).
    const isOverdue = status === STATUS.AVAILABLE && lastKill !== null;

    if (!isActiveWindow && !isOverdue) continue;

    const alreadyAlerted = lastKill.lastAlertAt && now - lastKill.lastAlertAt < ALERT_THROTTLE_MS;
    if (alreadyAlerted) continue;

    const embed = isActiveWindow
      ? windowAlertEmbed(boss, lastKill, guildConfig.timezone)
      : overdueAlertEmbed(boss, lastKill, guildConfig.timezone);

    const mention = guildConfig.alertRoleId ? `<@&${guildConfig.alertRoleId}>` : '@everyone';
    const allowedMentions = guildConfig.alertRoleId
      ? { roles: [guildConfig.alertRoleId] }
      : { parse: ['everyone'] };

    await channel.send({ content: mention, embeds: [embed], allowedMentions });

    lastKill.lastAlertAt = now;
    await lastKill.save();
  }
}

function startAlertScheduler(client) {
  cron.schedule(alertCheckCron, async () => {
    try {
      const guildConfigs = await GuildConfig.find({ alertChannelId: { $ne: null } });
      for (const guildConfig of guildConfigs) {
        await checkGuildAlerts(client, guildConfig);
      }
    } catch (error) {
      logger.error(`Error revisando alertas de ventana activa: ${error.stack}`);
    }
  });

  logger.info(`Scheduler de alertas iniciado (cron: "${alertCheckCron}").`);
}

module.exports = { startAlertScheduler, checkGuildAlerts };
