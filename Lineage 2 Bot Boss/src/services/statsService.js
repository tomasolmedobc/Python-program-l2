const KillHistory = require('../models/KillHistory');

/**
 * Calcula estadísticas reales de respawn a partir del historial: la
 * diferencia observada entre cada muerte y la siguiente (no la ventana
 * teórica configurada), lo que refleja el comportamiento real del servidor.
 */
async function getBossStats(guildId, raidBossId) {
  const kills = await KillHistory.find({ guildId, raidBoss: raidBossId })
    .sort({ deathTime: 1 })
    .lean();

  const totalKills = kills.length;
  const gapsMs = [];
  for (let i = 1; i < kills.length; i += 1) {
    gapsMs.push(kills[i].deathTime.getTime() - kills[i - 1].deathTime.getTime());
  }

  if (gapsMs.length === 0) {
    return { totalKills, avgRespawnMs: null, fastestMs: null, slowestMs: null };
  }

  const avgRespawnMs = gapsMs.reduce((sum, gap) => sum + gap, 0) / gapsMs.length;

  return {
    totalKills,
    avgRespawnMs,
    fastestMs: Math.min(...gapsMs),
    slowestMs: Math.max(...gapsMs),
  };
}

module.exports = { getBossStats };
