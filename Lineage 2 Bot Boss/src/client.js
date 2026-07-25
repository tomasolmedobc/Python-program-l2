const { Client, GatewayIntentBits, Partials } = require('discord.js');
const { loadCommands } = require('./commands');
const { loadEvents } = require('./events');

function createClient() {
  const client = new Client({
    intents: [
      GatewayIntentBits.Guilds,
      GatewayIntentBits.GuildMessages,
      GatewayIntentBits.MessageContent, // Fase 2: detección de texto en el canal configurado
    ],
    partials: [Partials.Message, Partials.Channel],
  });

  client.commands = loadCommands();
  loadEvents(client);

  return client;
}

module.exports = { createClient };
