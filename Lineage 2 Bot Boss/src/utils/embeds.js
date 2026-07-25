const { EmbedBuilder } = require('discord.js');
const { STATUS } = require('../services/calculatorService');
const { formatDate, formatTime, formatShortDateTime, formatDuration } = require('./time');

const STATUS_LABELS = {
  [STATUS.DEAD]: '🔴 Muerto',
  [STATUS.ACTIVE_WINDOW]: '🟡 Spawn activo',
  [STATUS.AVAILABLE]: '🟢 Disponible',
};

const COLORS = {
  [STATUS.DEAD]: 0xed4245,
  [STATUS.ACTIVE_WINDOW]: 0xfee75c,
  [STATUS.AVAILABLE]: 0x57f287,
};

function killRegisteredEmbed(boss, kill, timezone) {
  return new EmbedBuilder()
    .setColor(COLORS[STATUS.DEAD])
    .setTitle(`${boss.emoji} ${boss.name} derrotada`)
    .addFields(
      { name: 'Registrado por', value: kill.killedBy.username, inline: true },
      { name: 'Hora de muerte', value: formatDate(kill.deathTime, timezone), inline: true },
      { name: 'Próximo spawn estimado', value: formatDate(kill.spawnEstimate, timezone) },
      {
        name: 'Spawn posible',
        value: `${formatTime(kill.spawnMin, timezone)} - ${formatTime(kill.spawnMax, timezone)}`,
      },
      { name: 'Estado actual', value: STATUS_LABELS[STATUS.DEAD] }
    )
    .setTimestamp(kill.deathTime);
}

function bossListEmbed(guildName, bossesWithStatus, timezone) {
  const embed = new EmbedBuilder()
    .setColor(0x5865f2)
    .setTitle(`Epic Raid Bosses — ${guildName}`)
    .setTimestamp();

  for (const { boss, lastKill, status } of bossesWithStatus) {
    const lines = [`Estado: ${STATUS_LABELS[status]}`];

    if (lastKill) {
      lines.push(`Muerte: ${formatDate(lastKill.deathTime, timezone)}`);
      lines.push(
        `Próximamente: ${formatShortDateTime(lastKill.spawnMin, timezone)} - ${formatShortDateTime(lastKill.spawnMax, timezone)}`
      );
    } else {
      lines.push('Sin registros de muerte todavía.');
    }

    embed.addFields({ name: `${boss.emoji} ${boss.name}`, value: lines.join('\n') });
  }

  return embed;
}

function historyEmbed(boss, kills, timezone) {
  const embed = new EmbedBuilder()
    .setColor(0x5865f2)
    .setTitle(`${boss.emoji} Historial de ${boss.name}`)
    .setTimestamp();

  if (kills.length === 0) {
    embed.setDescription('No hay muertes registradas todavía.');
    return embed;
  }

  const lines = kills.map(
    (kill, index) =>
      `**${index + 1}.** ${formatDate(kill.deathTime, timezone)} — por ${kill.killedBy.username}`
  );

  embed.setDescription(lines.join('\n'));
  return embed;
}

function nextSpawnEmbed(candidates, timezone) {
  const embed = new EmbedBuilder().setColor(0x5865f2).setTitle('Próximo Raid Boss').setTimestamp();

  if (candidates.length === 0) {
    embed.setDescription('No hay ningún boss con spawn pendiente. Todos están 🟢 disponibles.');
    return embed;
  }

  const { boss, lastKill, status } = candidates[0];
  embed
    .setDescription(`${boss.emoji} **${boss.name}**`)
    .addFields(
      { name: 'Estado', value: STATUS_LABELS[status] },
      {
        name: 'Spawn posible',
        value: `${formatDate(lastKill.spawnMin, timezone)} - ${formatDate(lastKill.spawnMax, timezone)}`,
      }
    );

  return embed;
}

function statsEmbed(boss, stats) {
  const embed = new EmbedBuilder()
    .setColor(0x5865f2)
    .setTitle(`${boss.emoji} Estadísticas de ${boss.name}`)
    .addFields({ name: 'Cantidad de muertes', value: `${stats.totalKills}` })
    .setTimestamp();

  if (stats.avgRespawnMs === null) {
    embed.addFields({
      name: 'Respawn real',
      value: 'Se necesitan al menos 2 muertes registradas para calcular estadísticas de respawn.',
    });
    return embed;
  }

  embed.addFields(
    { name: 'Promedio real de respawn', value: formatDuration(stats.avgRespawnMs) },
    { name: 'Spawn más rápido', value: formatDuration(stats.fastestMs) },
    { name: 'Spawn más lento', value: formatDuration(stats.slowestMs) }
  );

  return embed;
}

function helpEmbed() {
  return new EmbedBuilder()
    .setColor(0x5865f2)
    .setTitle('🐉 Epic Raid Boss Tracker — Ayuda')
    .setDescription(
      'Lleva la cuenta de cuándo pueden volver a aparecer Queen Ant, Core, Orfen, Zaken, Baium, Antharas y Valakas.'
    )
    .addFields(
      {
        name: '📌 /raid register',
        value:
          'Anotá que un boss acaba de morir. El bot calcula solo cuándo puede volver a salir.\n' +
          '**Ejemplo:** `/raid register nombre:Queen Ant`\n' +
          'Si se murió mientras el bot estaba apagado, agregá la hora real:\n' +
          '`/raid register nombre:Queen Ant fecha_hora:25/07 14:35`',
      },
      {
        name: '📋 /raid list',
        value:
          'Muestra todos los bosses y su estado: 🔴 Muerto, 🟡 Spawn activo (puede salir ya) o 🟢 Disponible.\n' +
          '**Ejemplo:** `/raid list`',
      },
      {
        name: '⏭️ /raid next',
        value: 'Te dice cuál boss está más cerca de aparecer.\n**Ejemplo:** `/raid next`',
      },
      {
        name: '📊 /raid stats',
        value:
          'Muestra cada cuánto sale realmente ese boss en el servidor (promedio, más rápido y más lento registrado).\n' +
          '**Ejemplo:** `/raid stats nombre:Antharas`',
      },
      {
        name: '🕑 /raid history',
        value: 'Muestra las últimas muertes registradas de un boss.\n**Ejemplo:** `/raid history nombre:Zaken`',
      },
      {
        name: '↩️ /raid delete',
        value:
          'Deshace el último registro de un boss (por si alguien lo anotó mal).\n**Ejemplo:** `/raid delete nombre:Core`',
      },
      {
        name: '⚙️ /raid config (solo administradores)',
        value:
          'Configura en qué canal se avisa cuando muere un boss, dónde llegan las alertas de spawn, ' +
          'qué rol se menciona, en qué canal detecta mensajes tipo "QA muerto", y la zona horaria del servidor.\n' +
          '**Ejemplo:** `/raid config canal_alertas:#alerta-epico`',
      }
    )
    .setFooter({ text: 'Tip: también podés escribir "QA muerto" en el canal configurado y confirmar con un botón.' });
}

function detectionConfirmEmbed(boss) {
  return new EmbedBuilder()
    .setColor(0x5865f2)
    .setDescription(`${boss.emoji} Detecté una posible muerte de **${boss.name}**.\n¿Confirmar registro?`);
}

function windowAlertEmbed(boss, lastKill, timezone) {
  return new EmbedBuilder()
    .setColor(COLORS[STATUS.ACTIVE_WINDOW])
    .setTitle(`⚠️ ${boss.emoji} ${boss.name} está dentro de su horario de aparición`)
    .setDescription('Puede aparecer en cualquier momento.')
    .addFields({
      name: 'Próximamente',
      value: `${formatDate(lastKill.spawnMin, timezone)} - ${formatDate(lastKill.spawnMax, timezone)}`,
    })
    .setTimestamp();
}

function overdueAlertEmbed(boss, lastKill, timezone) {
  return new EmbedBuilder()
    .setColor(COLORS[STATUS.DEAD])
    .setTitle(`🔺 ${boss.emoji} ${boss.name} superó su spawn estimado`)
    .setDescription(
      'Nadie registró una nueva muerte. Puede que ya haya aparecido sin ser campeado, o que el cálculo se haya desviado — revisen el spawn.'
    )
    .addFields({
      name: 'Spawn que se esperaba',
      value: `${formatDate(lastKill.spawnMin, timezone)} - ${formatDate(lastKill.spawnMax, timezone)}`,
    })
    .setTimestamp();
}

module.exports = {
  STATUS_LABELS,
  killRegisteredEmbed,
  bossListEmbed,
  historyEmbed,
  nextSpawnEmbed,
  statsEmbed,
  windowAlertEmbed,
  overdueAlertEmbed,
  detectionConfirmEmbed,
  helpEmbed,
};
