const raidService = require('../../services/raidService');
const guildService = require('../../services/guildService');
const { killRegisteredEmbed } = require('../../utils/embeds');
const { parseDateTime } = require('../../utils/time');
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
  const fechaHoraInput = interaction.options.getString('fecha_hora');

  try {
    const guildConfig = await guildService.getGuildConfig(interaction.guildId);
    const timezone = guildConfig?.timezone || 'America/Bogota';

    let deathTime = new Date();

    // Permite registrar retroactivamente una muerte ocurrida mientras el
    // bot estaba apagado, en vez de asumir "ahora" como hora de muerte.
    if (fechaHoraInput) {
      const parsed = parseDateTime(fechaHoraInput, timezone);

      if (!parsed) {
        await interaction.reply({
          content:
            'Formato de fecha inválido. Usá "DD/MM HH:mm" o "DD/MM/AAAA HH:mm", ej: 25/07 14:35',
          ephemeral: true,
        });
        return;
      }

      if (parsed.getTime() > Date.now()) {
        await interaction.reply({
          content: 'La fecha de muerte no puede estar en el futuro.',
          ephemeral: true,
        });
        return;
      }

      deathTime = parsed;
    }

    const { boss, kill } = await raidService.registerKill(
      interaction.guildId,
      nombre,
      { userId: interaction.user.id, username: interaction.user.username },
      deathTime
    );

    const embed = killRegisteredEmbed(boss, kill, timezone);
    await interaction.reply({ embeds: [embed] });

    // Si hay un canal de anuncios configurado y es distinto al canal actual,
    // también se publica ahí para que todo el clan lo vea.
    if (guildConfig?.announceChannelId && guildConfig.announceChannelId !== interaction.channelId) {
      const channel = await interaction.guild.channels.fetch(guildConfig.announceChannelId).catch(() => null);
      if (channel?.isTextBased()) {
        await channel.send({ embeds: [embed] });
      }
    }
  } catch (error) {
    await interaction.reply({ content: error.message, ephemeral: true });
  }
};
