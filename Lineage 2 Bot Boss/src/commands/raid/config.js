const { PermissionFlagsBits } = require('discord.js');
const guildService = require('../../services/guildService');

function isValidTimezone(timezone) {
  try {
    new Intl.DateTimeFormat('en-US', { timeZone: timezone });
    return true;
  } catch {
    return false;
  }
}

module.exports = async function execute(interaction) {
  if (!interaction.memberPermissions?.has(PermissionFlagsBits.ManageGuild)) {
    await interaction.reply({
      content: 'Necesitas el permiso "Gestionar servidor" para usar este comando.',
      ephemeral: true,
    });
    return;
  }

  const announceChannel = interaction.options.getChannel('canal_anuncios');
  const detectionChannel = interaction.options.getChannel('canal_deteccion');
  const alertChannel = interaction.options.getChannel('canal_alertas');
  const alertRole = interaction.options.getRole('rol_alerta');
  const timezoneInput = interaction.options.getString('zona_horaria');

  if (timezoneInput && !isValidTimezone(timezoneInput)) {
    await interaction.reply({
      content:
        'Zona horaria inválida. Usá un identificador IANA, ej: "America/Argentina/Buenos_Aires", "America/Bogota".',
      ephemeral: true,
    });
    return;
  }

  const updates = {};
  if (announceChannel) updates.announceChannelId = announceChannel.id;
  if (detectionChannel) updates.detectionChannelId = detectionChannel.id;
  if (alertChannel) updates.alertChannelId = alertChannel.id;
  if (alertRole) updates.alertRoleId = alertRole.id;
  if (timezoneInput) updates.timezone = timezoneInput;

  if (Object.keys(updates).length === 0) {
    const current = await guildService.getGuildConfig(interaction.guildId);
    await interaction.reply({
      content: [
        '**Configuración actual:**',
        `Canal de anuncios: ${current?.announceChannelId ? `<#${current.announceChannelId}>` : 'sin configurar'}`,
        `Canal de detección: ${current?.detectionChannelId ? `<#${current.detectionChannelId}>` : 'sin configurar'}`,
        `Canal de alertas: ${current?.alertChannelId ? `<#${current.alertChannelId}>` : 'sin configurar'}`,
        `Rol para alertas: ${current?.alertRoleId ? `<@&${current.alertRoleId}>` : '@everyone (por defecto)'}`,
        `Zona horaria: ${current?.timezone || 'sin configurar'}`,
      ].join('\n'),
      ephemeral: true,
    });
    return;
  }

  await guildService.updateGuildConfig(interaction.guildId, updates);
  await interaction.reply({ content: 'Configuración actualizada correctamente.', ephemeral: true });
};
