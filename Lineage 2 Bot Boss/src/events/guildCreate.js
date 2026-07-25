const logger = require('../utils/logger');
const guildService = require('../services/guildService');

module.exports = {
  name: 'guildCreate',
  once: false,
  async execute(guild) {
    await guildService.ensureGuildSetup(guild.id);
    logger.info(`Bot añadido a nuevo servidor: ${guild.name} (${guild.id})`);
  },
};
