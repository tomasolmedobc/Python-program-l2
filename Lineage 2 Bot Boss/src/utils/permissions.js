const { PermissionFlagsBits } = require('discord.js');

function isAdmin(interaction) {
  return Boolean(interaction.memberPermissions?.has(PermissionFlagsBits.Administrator));
}

module.exports = { isAdmin };
