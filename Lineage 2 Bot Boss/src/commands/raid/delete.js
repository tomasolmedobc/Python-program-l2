const raidService = require('../../services/raidService');
const { isAdmin } = require('../../utils/permissions');

module.exports = async function execute(interaction) {
  if (!isAdmin(interaction)) {
    await interaction.reply({
      content: 'Necesitás permisos de Administrador para usar este comando.',
      ephemeral: true,
    });
    return;
  }

  const nombre = interaction.options.getString('nombre', true);

  try {
    const boss = await raidService.deleteLatestKill(interaction.guildId, nombre);
    await interaction.reply({
      content: `Se eliminó el último registro de muerte de ${boss.emoji} ${boss.name}. Vuelve a estar 🟢 Disponible.`,
    });
  } catch (error) {
    await interaction.reply({ content: error.message, ephemeral: true });
  }
};
