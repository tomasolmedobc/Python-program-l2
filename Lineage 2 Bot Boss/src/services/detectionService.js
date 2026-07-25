const RaidBoss = require('../models/RaidBoss');
const { normalize, escapeRegex } = require('../utils/text');

// Palabras que indican que alguien está reportando una muerte, en cualquier
// forma común de escritura (español/inglés, con o sin tilde).
const DEATH_TRIGGERS = [
  'muri[oó]',
  'muert[oa]',
  'down',
  'mat(?:amos|aron|[oó])',
  'cay[oó]',
  'dead',
  'kill(?:ed)?',
];
const DEATH_REGEX = new RegExp(`\\b(?:${DEATH_TRIGGERS.join('|')})\\b`);

/**
 * Busca en el texto de un mensaje si hay una posible mención de muerte de
 * algún Raid Boss del servidor: requiere una palabra "gatillo" (muerto,
 * down, matamos, etc.) Y el nombre o alias de un boss en el mismo mensaje.
 * Devuelve el RaidBoss encontrado o null.
 */
async function detectBossMention(guildId, content) {
  const normalizedContent = normalize(content);
  if (!DEATH_REGEX.test(normalizedContent)) return null;

  const bosses = await RaidBoss.find({ guildId });

  for (const boss of bosses) {
    const candidates = [boss.name, ...boss.aliases];
    const hasMatch = candidates.some((alias) => {
      const pattern = new RegExp(`\\b${escapeRegex(normalize(alias))}\\b`);
      return pattern.test(normalizedContent);
    });

    if (hasMatch) return boss;
  }

  return null;
}

module.exports = { detectBossMention };
