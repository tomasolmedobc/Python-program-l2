const raidService = require('../../services/raidService');
const guildService = require('../../services/guildService');
const { bossListEmbed } = require('../../utils/embeds');

module.exports = async function execute(interaction) {
  const bossesWithStatus = await raidService.getAllBossesWithStatus(interaction.guildId);
  const guildConfig = await guildService.getGuildConfig(interaction.guildId);
  const embed = bossListEmbed(interaction.guild.name, bossesWithStatus, guildConfig?.timezone);
  await interaction.reply({ embeds: [embed] });
};
