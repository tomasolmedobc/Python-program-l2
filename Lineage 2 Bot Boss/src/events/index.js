const fs = require('fs');
const path = require('path');

/**
 * Carga y registra en el client todos los archivos de evento de esta carpeta.
 * Cada archivo exporta { name, once, execute }.
 */
function loadEvents(client) {
  const eventsPath = __dirname;

  const files = fs
    .readdirSync(eventsPath, { withFileTypes: true })
    .filter((entry) => entry.isFile() && entry.name.endsWith('.js') && entry.name !== 'index.js')
    .map((entry) => entry.name);

  for (const file of files) {
    const event = require(path.join(eventsPath, file));

    if (event.once) {
      client.once(event.name, (...args) => event.execute(...args));
    } else {
      client.on(event.name, (...args) => event.execute(...args));
    }
  }
}

module.exports = { loadEvents };
