const { Schema, model } = require('mongoose');

const killHistorySchema = new Schema(
  {
    guildId: { type: String, required: true, index: true },
    raidBoss: { type: Schema.Types.ObjectId, ref: 'RaidBoss', required: true, index: true },
    killedBy: {
      userId: { type: String, required: true },
      username: { type: String, required: true },
    },
    deathTime: { type: Date, required: true },
    spawnMin: { type: Date, required: true },
    spawnMax: { type: Date, required: true },
    spawnEstimate: { type: Date, required: true },
    // Throttle de alertas automáticas (Fase 3): última vez que se avisó
    // que este registro está en ventana activa.
    lastAlertAt: { type: Date, default: null },
  },
  { timestamps: true }
);

// El historial y el "estado actual" de un boss se consultan siempre
// por el más reciente: guildId + raidBoss ordenado por deathTime desc.
killHistorySchema.index({ guildId: 1, raidBoss: 1, deathTime: -1 });

module.exports = model('KillHistory', killHistorySchema);
