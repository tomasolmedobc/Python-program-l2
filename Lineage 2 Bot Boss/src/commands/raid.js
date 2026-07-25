const { SlashCommandBuilder } = require('discord.js');
const raidService = require('../services/raidService');

const register = require('./raid/register');
const list = require('./raid/list');
const deleteCommand = require('./raid/delete');
const history = require('./raid/history');
const next = require('./raid/next');
const stats = require('./raid/stats');
const config = require('./raid/config');
const help = require('./raid/help');

const data = new SlashCommandBuilder()
  .setName('raid')
  .setDescription('Epic Raid Boss Tracker')
  .addSubcommand((sub) =>
    sub.setName('help').setDescription('Muestra qué hace cada comando, con ejemplos')
  )
  .addSubcommand((sub) =>
    sub
      .setName('register')
      .setDescription('Registra la muerte de un Raid Boss')
      .addStringOption((opt) =>
        opt
          .setName('nombre')
          .setDescription('Nombre del Raid Boss')
          .setRequired(true)
          .setAutocomplete(true)
      )
      .addStringOption((opt) =>
        opt
          .setName('fecha_hora')
          .setDescription('Si el bot estaba apagado: hora real de la muerte, ej. 25/07 14:35')
          .setRequired(false)
      )
  )
  .addSubcommand((sub) =>
    sub.setName('list').setDescription('Muestra todos los Raid Bosses y su estado actual')
  )
  .addSubcommand((sub) =>
    sub
      .setName('delete')
      .setDescription('Elimina el último registro de muerte de un Raid Boss')
      .addStringOption((opt) =>
        opt
          .setName('nombre')
          .setDescription('Nombre del Raid Boss')
          .setRequired(true)
          .setAutocomplete(true)
      )
  )
  .addSubcommand((sub) =>
    sub
      .setName('history')
      .setDescription('Muestra el historial de muertes de un Raid Boss')
      .addStringOption((opt) =>
        opt
          .setName('nombre')
          .setDescription('Nombre del Raid Boss')
          .setRequired(true)
          .setAutocomplete(true)
      )
  )
  .addSubcommand((sub) =>
    sub.setName('next').setDescription('Muestra cuál es el próximo Raid Boss que puede aparecer')
  )
  .addSubcommand((sub) =>
    sub
      .setName('stats')
      .setDescription('Muestra estadísticas reales de respawn de un Raid Boss')
      .addStringOption((opt) =>
        opt
          .setName('nombre')
          .setDescription('Nombre del Raid Boss')
          .setRequired(true)
          .setAutocomplete(true)
      )
  )
  .addSubcommand((sub) =>
    sub
      .setName('config')
      .setDescription('Configura los canales del tracker para este servidor (requiere Gestionar servidor)')
      .addChannelOption((opt) =>
        opt.setName('canal_anuncios').setDescription('Canal donde se publican los registros de muerte')
      )
      .addChannelOption((opt) =>
        opt.setName('canal_deteccion').setDescription('Canal donde el bot detecta menciones de muertes')
      )
      .addChannelOption((opt) =>
        opt.setName('canal_alertas').setDescription('Canal donde se envían las alertas de spawn activo')
      )
      .addRoleOption((opt) =>
        opt
          .setName('rol_alerta')
          .setDescription('Rol a mencionar en las alertas (si no se configura, se usa @everyone)')
      )
      .addStringOption((opt) =>
        opt
          .setName('zona_horaria')
          .setDescription('Zona horaria IANA del servidor, ej: America/Argentina/Buenos_Aires')
      )
  );

const handlers = {
  help,
  register,
  list,
  delete: deleteCommand,
  history,
  next,
  stats,
  config,
};

async function execute(interaction) {
  const subcommand = interaction.options.getSubcommand();
  const handler = handlers[subcommand];

  if (!handler) {
    await interaction.reply({ content: 'Subcomando no reconocido.', ephemeral: true });
    return;
  }

  await handler(interaction);
}

async function autocomplete(interaction) {
  const focused = interaction.options.getFocused();
  const bosses = await raidService.listBosses(interaction.guildId, focused);

  await interaction.respond(
    bosses.slice(0, 25).map((boss) => ({ name: `${boss.emoji} ${boss.name}`, value: boss.name }))
  );
}

module.exports = { data, execute, autocomplete };
