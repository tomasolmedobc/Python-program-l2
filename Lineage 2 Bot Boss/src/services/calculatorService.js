const STATUS = {
  DEAD: 'DEAD', // 🔴 registrado recientemente, aún no entra en ventana
  ACTIVE_WINDOW: 'ACTIVE_WINDOW', // 🟡 dentro del rango posible de aparición
  AVAILABLE: 'AVAILABLE', // 🟢 sin registro reciente o ventana ya pasada
};

/**
 * Calcula la ventana de spawn a partir de la hora de muerte y la
 * configuración de respawn del boss. Función pura: no toca la DB ni Discord.
 */
function computeSpawnWindow(deathTime, respawnHours, variationHours) {
  const deathMs = deathTime.getTime();
  const respawnMs = respawnHours * 60 * 60 * 1000;
  const variationMs = variationHours * 60 * 60 * 1000;

  return {
    spawnMin: new Date(deathMs + respawnMs - variationMs),
    spawnEstimate: new Date(deathMs + respawnMs),
    spawnMax: new Date(deathMs + respawnMs + variationMs),
  };
}

/**
 * Determina el estado actual de un boss según su último kill registrado.
 * El estado nunca se guarda: siempre se deriva de "now" vs la ventana.
 */
function computeStatus(lastKill, now = new Date()) {
  if (!lastKill) return STATUS.AVAILABLE;
  if (now < lastKill.spawnMin) return STATUS.DEAD;
  if (now <= lastKill.spawnMax) return STATUS.ACTIVE_WINDOW;
  return STATUS.AVAILABLE;
}

module.exports = { computeSpawnWindow, computeStatus, STATUS };
