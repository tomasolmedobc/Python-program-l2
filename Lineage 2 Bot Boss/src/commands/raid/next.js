const raidService = require('../../services/raidService');
const guildService = require('../../services/guildService');
const { nextSpawnEmbed } = require('../../utils/embeds');

module.exports = async function execute(interaction) {
  const candidates = await raidService.getNextSpawnCandidates(interaction.guildId);
  const guildConfig = await guildService.getGuildConfig(interaction.guildId);
  const embed = nextSpawnEmbed(candidates, guildConfig?.timezone);
  await interaction.reply({ embeds: [embed] });
};
