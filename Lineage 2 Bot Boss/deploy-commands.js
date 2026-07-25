const { REST, Routes } = require('discord.js');
const { discordToken, discordClientId, discordGuildId } = require('./src/config/env');
const { loadCommands } = require('./src/commands');
const logger = require('./src/utils/logger');

async function deploy() {
  const commands = loadCommands();
  const body = commands.map((command) => command.data.toJSON());
  const rest = new REST().setToken(discordToken);

  const route = discordGuildId
    ? Routes.applicationGuildCommands(discordClientId, discordGuildId)
    : Routes.applicationCommands(discordClientId);

  const data = await rest.put(route, { body });

  logger.info(
    `Se registraron ${data.length} comando(s) ${discordGuildId ? `en el servidor ${discordGuildId}` : 'globalmente'}.`
  );
}

deploy().catch((error) => {
  logger.error(`Error registrando comandos: ${error.stack}`);
  process.exit(1);
});
