const { helpEmbed } = require('../../utils/embeds');

module.exports = async function execute(interaction) {
  await interaction.reply({ embeds: [helpEmbed()], ephemeral: true });
};
