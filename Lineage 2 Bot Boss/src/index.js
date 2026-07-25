const { connectDatabase } = require('./config/database');
const { createClient } = require('./client');
const { discordToken } = require('./config/env');
const logger = require('./utils/logger');

async function main() {
  await connectDatabase();

  const client = createClient();
  await client.login(discordToken);
}

main().catch((error) => {
  logger.error(`Error fatal al iniciar el bot: ${error.stack}`);
  process.exit(1);
});
