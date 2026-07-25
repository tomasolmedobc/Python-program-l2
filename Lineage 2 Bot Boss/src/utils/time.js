/**
 * Formatea una fecha a "DD/MM/AAAA HH:mm" en la zona horaria indicada.
 */
function formatDate(date, timezone = 'America/Bogota') {
  const parts = new Intl.DateTimeFormat('es-CO', {
    timeZone: timezone,
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
    .formatToParts(date)
    .reduce((acc, part) => {
      acc[part.type] = part.value;
      return acc;
    }, {});

  return `${parts.day}/${parts.month}/${parts.year} ${parts.hour}:${parts.minute}`;
}

/**
 * Formatea solo la hora "HH:mm" en la zona horaria indicada.
 */
function formatTime(date, timezone = 'America/Bogota') {
  return new Intl.DateTimeFormat('es-CO', {
    timeZone: timezone,
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date);
}

/**
 * Formatea "DD/MM HH:mm" (sin año) para listados compactos donde la
 * ventana de spawn puede cruzar varios días (ej. Antharas, Baium, Valakas).
 */
function formatShortDateTime(date, timezone = 'America/Bogota') {
  const parts = new Intl.DateTimeFormat('es-CO', {
    timeZone: timezone,
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
    .formatToParts(date)
    .reduce((acc, part) => {
      acc[part.type] = part.value;
      return acc;
    }, {});

  return `${parts.day}/${parts.month} ${parts.hour}:${parts.minute}`;
}

/**
 * Convierte una duración en milisegundos a "X horas Y minutos".
 */
function formatDuration(ms) {
  const totalMinutes = Math.round(ms / 60000);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return `${hours} horas ${minutes} minutos`;
}

/**
 * Offset (en minutos) de una zona horaria respecto a UTC, para un instante
 * dado. Se calcula por fecha (no fijo) para cubrir zonas con horario de
 * verano; América/Bogotá no lo tiene, pero esto deja la función genérica.
 */
function getTimezoneOffsetMinutes(date, timezone) {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: timezone,
    timeZoneName: 'shortOffset',
  }).formatToParts(date);

  const offsetName = parts.find((part) => part.type === 'timeZoneName')?.value || 'GMT+0';
  const match = offsetName.match(/GMT([+-])(\d{1,2})(?::(\d{2}))?/);
  if (!match) return 0;

  const sign = match[1] === '-' ? -1 : 1;
  const hours = Number(match[2]);
  const minutes = match[3] ? Number(match[3]) : 0;
  return sign * (hours * 60 + minutes);
}

function isValidCalendarDate(day, month, year) {
  const date = new Date(Date.UTC(year, month - 1, day));
  return (
    date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day
  );
}

/**
 * Parsea "DD/MM HH:mm" o "DD/MM/AAAA HH:mm" interpretado en la zona horaria
 * del servidor (para registrar muertes ocurridas mientras el bot estaba
 * apagado). Si se omite el año, usa el año actual. Devuelve null si el
 * formato o la fecha calendario no son válidos.
 */
function parseDateTime(input, timezone = 'America/Bogota', now = new Date()) {
  const match = input
    .trim()
    .match(/^(\d{1,2})\/(\d{1,2})(?:\/(\d{2,4}))?\s+(\d{1,2}):(\d{2})$/);

  if (!match) return null;

  const [, dayStr, monthStr, yearStr, hourStr, minuteStr] = match;
  const day = Number(dayStr);
  const month = Number(monthStr);
  const year = yearStr ? (yearStr.length === 2 ? 2000 + Number(yearStr) : Number(yearStr)) : now.getUTCFullYear();
  const hour = Number(hourStr);
  const minute = Number(minuteStr);

  if (month < 1 || month > 12 || hour > 23 || minute > 59) return null;
  if (!isValidCalendarDate(day, month, year)) return null;

  const naiveUtcMs = Date.UTC(year, month - 1, day, hour, minute);
  const offsetMinutes = getTimezoneOffsetMinutes(new Date(naiveUtcMs), timezone);
  return new Date(naiveUtcMs - offsetMinutes * 60000);
}

module.exports = { formatDate, formatTime, formatShortDateTime, formatDuration, parseDateTime };
