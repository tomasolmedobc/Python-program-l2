const fs = require('fs');
const path = require('path');
const { Collection } = require('discord.js');

/**
 * Carga los comandos de nivel superior (un archivo = un comando con sus
 * subcomandos, ej. raid.js). Las subcarpetas (ej. raid/) son handlers
 * internos y no se cargan como comandos independientes.
 */
function loadCommands() {
  const commands = new Collection();
  const commandsPath = __dirname;

  const files = fs
    .readdirSync(commandsPath, { withFileTypes: true })
    .filter((entry) => entry.isFile() && entry.name.endsWith('.js') && entry.name !== 'index.js')
    .map((entry) => entry.name);

  for (const file of files) {
    const command = require(path.join(commandsPath, file));
    if (!command.data || !command.execute) continue;
    commands.set(command.data.name, command);
  }

  return commands;
}

module.exports = { loadCommands };
