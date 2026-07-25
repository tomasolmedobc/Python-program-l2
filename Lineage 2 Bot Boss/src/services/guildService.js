const GuildConfig = require('../models/GuildConfig');
const RaidBoss = require('../models/RaidBoss');
const bossesConfig = require('../config/bosses.config');
const { timezone: defaultTimezone } = require('../config/env');

/**
 * Se ejecuta cuando el bot arranca (por cada guild) o al unirse a un
 * servidor nuevo: crea la config por defecto y siembra el catálogo de
 * Epic Raid Bosses si el servidor todavía no tiene ninguno.
 */
async function ensureGuildSetup(guildId) {
  await GuildConfig.findOneAndUpdate(
    { guildId },
    { $setOnInsert: { guildId, timezone: defaultTimezone } },
    { upsert: true, new: true }
  );

  const existingCount = await RaidBoss.countDocuments({ guildId });
  if (existingCount === 0) {
    await RaidBoss.insertMany(bossesConfig.map((boss) => ({ ...boss, guildId })));
  }
}

function getGuildConfig(guildId) {
  return GuildConfig.findOne({ guildId });
}

function updateGuildConfig(guildId, updates) {
  return GuildConfig.findOneAndUpdate(
    { guildId },
    { $set: updates },
    { new: true, upsert: true }
  );
}

module.exports = { ensureGuildSetup, getGuildConfig, updateGuildConfig };
