const { ActionRowBuilder, ButtonBuilder, ButtonStyle, ComponentType } = require('discord.js');
const guildService = require('../services/guildService');
const raidService = require('../services/raidService');
const detectionService = require('../services/detectionService');
const { detectionConfirmEmbed, killRegisteredEmbed } = require('../utils/embeds');
const { isAdmin } = require('../utils/permissions');
const logger = require('../utils/logger');

const CONFIRMATION_TIMEOUT_MS = 2 * 60 * 1000;

module.exports = {
  name: 'messageCreate',
  once: false,
  async execute(message) {
    if (message.author.bot || !message.guildId) return;

    const guildConfig = await guildService.getGuildConfig(message.guildId);
    if (!guildConfig?.detectionChannelId || guildConfig.detectionChannelId !== message.channelId) {
      return;
    }

    try {
      const boss = await detectionService.detectBossMention(message.guildId, message.content);
      if (!boss) return;

      const row = new ActionRowBuilder().addComponents(
        new ButtonBuilder()
          .setCustomId('confirm_kill')
          .setLabel('Confirmar')
          .setEmoji('✅')
          .setStyle(ButtonStyle.Success),
        new ButtonBuilder()
          .setCustomId('cancel_kill')
          .setLabel('Cancelar')
          .setEmoji('❌')
          .setStyle(ButtonStyle.Danger)
      );

      const sent = await message.reply({ embeds: [detectionConfirmEmbed(boss)], components: [row] });

      const collector = sent.createMessageComponentCollector({
        componentType: ComponentType.Button,
        time: CONFIRMATION_TIMEOUT_MS,
      });

      collector.on('collect', async (buttonInteraction) => {
        if (buttonInteraction.customId === 'cancel_kill') {
          await buttonInteraction.update({ content: 'Registro cancelado.', embeds: [], components: [] });
          collector.stop();
          return;
        }

        if (buttonInteraction.customId !== 'confirm_kill') return;

        if (!isAdmin(buttonInteraction)) {
          await buttonInteraction.reply({
            content: 'Necesitás permisos de Administrador para confirmar el registro.',
            ephemeral: true,
          });
          return;
        }

        try {
          const { kill } = await raidService.registerKill(message.guildId, boss.name, {
            userId: buttonInteraction.user.id,
            username: buttonInteraction.user.username,
          });

          const embed = killRegisteredEmbed(boss, kill, guildConfig.timezone);
          await buttonInteraction.update({ embeds: [embed], components: [] });
        } catch (error) {
          logger.error(`Error confirmando muerte detectada: ${error.stack}`);
          await buttonInteraction.update({ content: error.message, embeds: [], components: [] });
        }

        collector.stop();
      });

      collector.on('end', async (collected) => {
        if (collected.size === 0) {
          await sent.edit({ components: [] }).catch(() => {});
        }
      });
    } catch (error) {
      logger.error(`Error en detección automática de muertes: ${error.stack}`);
    }
  },
};
