const { Schema, model } = require('mongoose');

const guildConfigSchema = new Schema(
  {
    guildId: { type: String, required: true, unique: true },
    announceChannelId: { type: String, default: null }, // embed al registrar una muerte
    detectionChannelId: { type: String, default: null }, // Fase 2: canal leído para detección
    alertChannelId: { type: String, default: null }, // Fase 3: canal de alertas de ventana
    alertRoleId: { type: String, default: null }, // rol a mencionar en alertas; null = @everyone
    timezone: { type: String, default: 'America/Bogota' },
  },
  { timestamps: true }
);

module.exports = model('GuildConfig', guildConfigSchema);
