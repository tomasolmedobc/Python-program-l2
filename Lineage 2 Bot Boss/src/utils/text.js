// Rango Unicode de marcas diacríticas combinantes (U+0300-U+036F), construido
// por código para evitar caracteres combinantes "crudos" en el código fuente.
const DIACRITICS_REGEX = new RegExp(
  `[${String.fromCharCode(0x0300)}-${String.fromCharCode(0x036f)}]`,
  'g'
);

function normalize(text) {
  return text.toLowerCase().normalize('NFD').replace(DIACRITICS_REGEX, '').trim();
}

function escapeRegex(text) {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

module.exports = { normalize, escapeRegex };
