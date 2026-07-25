const raidService = require('../../services/raidService');
const statsService = require('../../services/statsService');
const { statsEmbed } = require('../../utils/embeds');

module.exports = async function execute(interaction) {
  const nombre = interaction.options.getString('nombre', true);

  const boss = await raidService.findBoss(interaction.guildId, nombre);
  if (!boss) {
    await interaction.reply({
      content: `No se encontró ningún Raid Boss que coincida con "${nombre}".`,
      ephemeral: true,
    });
    return;
  }

  const stats = await statsService.getBossStats(interaction.guildId, boss._id);
  await interaction.reply({ embeds: [statsEmbed(boss, stats)] });
};
