const raidService = require('../../services/raidService');
const guildService = require('../../services/guildService');
const { historyEmbed } = require('../../utils/embeds');

module.exports = async function execute(interaction) {
  const nombre = interaction.options.getString('nombre', true);

  try {
    const { boss, kills } = await raidService.getHistory(interaction.guildId, nombre);
    const guildConfig = await guildService.getGuildConfig(interaction.guildId);
    const embed = historyEmbed(boss, kills, guildConfig?.timezone);
    await interaction.reply({ embeds: [embed] });
  } catch (error) {
    await interaction.reply({ content: error.message, ephemeral: true });
  }
};
