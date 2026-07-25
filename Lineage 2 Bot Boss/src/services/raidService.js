const RaidBoss = require('../models/RaidBoss');
const KillHistory = require('../models/KillHistory');
const { computeSpawnWindow, computeStatus, STATUS } = require('./calculatorService');
const { normalize } = require('../utils/text');

/**
 * Busca un RaidBoss del servidor por nombre exacto o por alias.
 */
async function findBoss(guildId, query) {
  const bosses = await RaidBoss.find({ guildId });
  const normalizedQuery = normalize(query);

  return (
    bosses.find((boss) => normalize(boss.name) === normalizedQuery) ||
    bosses.find((boss) => boss.aliases.some((alias) => normalize(alias) === normalizedQuery)) ||
    null
  );
}

async function getLatestKill(guildId, raidBossId) {
  return KillHistory.findOne({ guildId, raidBoss: raidBossId }).sort({ deathTime: -1 });
}

/**
 * Lista los bosses del servidor cuyo nombre coincide parcialmente con
 * `query` (usado para el autocompletado del parámetro "nombre").
 */
async function listBosses(guildId, query = '') {
  const bosses = await RaidBoss.find({ guildId }).sort({ name: 1 });
  const normalizedQuery = normalize(query);

  return bosses.filter((boss) => normalize(boss.name).includes(normalizedQuery));
}

/**
 * Registra la muerte de un boss y calcula su próxima ventana de spawn.
 * Devuelve { boss, kill }. Lanza error si el boss no existe en el catálogo.
 */
async function registerKill(guildId, bossQuery, killedBy, deathTime = new Date()) {
  const boss = await findBoss(guildId, bossQuery);
  if (!boss) {
    throw new Error(`No se encontró ningún Raid Boss que coincida con "${bossQuery}".`);
  }

  const latest = await getLatestKill(guildId, boss._id);
  if (latest && deathTime <= latest.deathTime) {
    throw new Error(
      `Ya hay un registro de muerte más reciente para "${boss.name}". ` +
        `Si te equivocaste de fecha, borrá ese registro primero con /raid delete nombre:${boss.name}.`
    );
  }

  const { spawnMin, spawnMax, spawnEstimate } = computeSpawnWindow(
    deathTime,
    boss.respawnHours,
    boss.variationHours
  );

  const kill = await KillHistory.create({
    guildId,
    raidBoss: boss._id,
    killedBy,
    deathTime,
    spawnMin,
    spawnMax,
    spawnEstimate,
  });

  return { boss, kill };
}

/**
 * Elimina el registro de muerte más reciente de un boss (deshace el
 * último /raid register), dejando al boss como 🟢 Disponible de nuevo.
 */
async function deleteLatestKill(guildId, bossQuery) {
  const boss = await findBoss(guildId, bossQuery);
  if (!boss) {
    throw new Error(`No se encontró ningún Raid Boss que coincida con "${bossQuery}".`);
  }

  const latest = await getLatestKill(guildId, boss._id);
  if (!latest) {
    throw new Error(`"${boss.name}" no tiene ningún registro de muerte para eliminar.`);
  }

  await latest.deleteOne();
  return boss;
}

/**
 * Devuelve todos los bosses del servidor junto a su último kill (si existe)
 * y su estado actual (derivado, nunca almacenado).
 */
async function getAllBossesWithStatus(guildId, now = new Date()) {
  const bosses = await RaidBoss.find({ guildId }).sort({ name: 1 });

  return Promise.all(
    bosses.map(async (boss) => {
      const lastKill = await getLatestKill(guildId, boss._id);
      return { boss, lastKill, status: computeStatus(lastKill, now) };
    })
  );
}

/**
 * Ordena los bosses con predicción pendiente (🟡 antes que 🔴, y dentro de
 * cada grupo el spawnMin más cercano primero). Los 🟢 se excluyen: sin
 * historial reciente no hay ventana que predecir.
 */
async function getNextSpawnCandidates(guildId, now = new Date()) {
  const bossesWithStatus = await getAllBossesWithStatus(guildId, now);
  const priority = { [STATUS.ACTIVE_WINDOW]: 0, [STATUS.DEAD]: 1 };

  return bossesWithStatus
    .filter((entry) => entry.status !== STATUS.AVAILABLE)
    .sort((a, b) => {
      if (priority[a.status] !== priority[b.status]) {
        return priority[a.status] - priority[b.status];
      }
      return a.lastKill.spawnMin - b.lastKill.spawnMin;
    });
}

async function getHistory(guildId, bossQuery, limit = 10) {
  const boss = await findBoss(guildId, bossQuery);
  if (!boss) {
    throw new Error(`No se encontró ningún Raid Boss que coincida con "${bossQuery}".`);
  }

  const kills = await KillHistory.find({ guildId, raidBoss: boss._id })
    .sort({ deathTime: -1 })
    .limit(limit);

  return { boss, kills };
}

module.exports = {
  findBoss,
  listBosses,
  getLatestKill,
  registerKill,
  deleteLatestKill,
  getAllBossesWithStatus,
  getNextSpawnCandidates,
  getHistory,
};
