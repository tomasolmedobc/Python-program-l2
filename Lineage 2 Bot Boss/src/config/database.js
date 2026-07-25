const mongoose = require('mongoose');
const { mongodbUri } = require('./env');
const logger = require('../utils/logger');

async function connectDatabase() {
  mongoose.connection.on('disconnected', () => {
    logger.warn('MongoDB desconectado');
  });

  mongoose.connection.on('error', (err) => {
    logger.error(`Error de conexión a MongoDB: ${err.message}`);
  });

  await mongoose.connect(mongodbUri);
  logger.info(`MongoDB conectado: ${mongoose.connection.name}`);
}

module.exports = { connectDatabase };
