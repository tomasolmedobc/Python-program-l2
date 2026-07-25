const logger = require('../utils/logger');
const guildService = require('../services/guildService');
const { startAlertScheduler } = require('../services/alertService');

module.exports = {
  name: 'clientReady',
  once: true,
  async execute(client) {
    logger.info(`Bot conectado como ${client.user.tag}`);

    for (const guild of client.guilds.cache.values()) {
      await guildService.ensureGuildSetup(guild.id);
    }

    logger.info(`Setup verificado para ${client.guilds.cache.size} servidor(es).`);

    startAlertScheduler(client);
  },
};
