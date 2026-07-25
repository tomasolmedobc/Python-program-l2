const { Schema, model } = require('mongoose');

const raidBossSchema = new Schema(
  {
    guildId: { type: String, required: true, index: true },
    name: { type: String, required: true, trim: true },
    aliases: { type: [String], default: [] },
    respawnHours: { type: Number, required: true },
    variationHours: { type: Number, required: true },
    emoji: { type: String, default: '⚔️' },
  },
  { timestamps: true }
);

// Un boss con el mismo nombre no puede repetirse dentro del mismo servidor.
raidBossSchema.index({ guildId: 1, name: 1 }, { unique: true });

module.exports = model('RaidBoss', raidBossSchema);
