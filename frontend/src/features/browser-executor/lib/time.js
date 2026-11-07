const SMALL = {
  ноль: 0,
  нуль: 0,
  один: 1,
  одна: 1,
  одну: 1,
  два: 2,
  две: 2,
  три: 3,
  четыре: 4,
  пять: 5,
  шесть: 6,
  семь: 7,
  восемь: 8,
  девять: 9,
  десять: 10,
  одиннадцать: 11,
  двенадцать: 12,
  тринадцать: 13,
  четырнадцать: 14,
  пятнадцать: 15,
  шестнадцать: 16,
  семнадцать: 17,
  восемнадцать: 18,
  девятнадцать: 19,
};
const TENS = {
  двадцать: 20,
  тридцать: 30,
  сорок: 40,
  пятьдесят: 50,
  шестьдесят: 60,
  семьдесят: 70,
  восемьдесят: 80,
  девяносто: 90,
};
export function numberValue(value) {
  if (/^\d+$/.test(value)) {
    const n = Number(value);
    return Number.isSafeInteger(n) ? n : null;
  }
  if (Object.hasOwn(SMALL, value)) return SMALL[value];
  if (Object.hasOwn(TENS, value)) return TENS[value];
  const [tens, unit, extra] = value.split(" ");
  if (!extra && TENS[tens] && SMALL[unit] > 0 && SMALL[unit] < 10) return TENS[tens] + SMALL[unit];
  return null;
}

export function alarmDeadline(text, now = Date.now()) {
  const value = text.toLowerCase().replace(/ё/g, "е").replace(/\s+/g, " ").trim();
  const relative = value.match(/^через (.+)$/) || value.match(/^на (.+) вперед$/);
  if (relative) {
    const bare = { минуту: 60, час: 3600, полчаса: 1800, секунду: 1 };
    let seconds = bare[relative[1]];
    if (!seconds) {
      const match = relative[1].match(/^(.+) (секунд(?:а|у|ы)?|минут(?:а|у|ы)?|час(?:а|ов)?)$/);
      const amount = match && numberValue(match[1]);
      if (!amount || amount <= 0) throw new Error("Укажите положительное время до будильника.");
      const multiplier = match[2].startsWith("секунд")
        ? 1
        : match[2].startsWith("минут")
          ? 60
          : 3600;
      seconds = amount * multiplier;
    }
    const dueAt = now + seconds * 1000;
    if (!Number.isSafeInteger(dueAt) || !Number.isFinite(new Date(dueAt).getTime())) {
      throw new Error("Это время слишком далеко. Выберите более близкое время.");
    }
    return dueAt;
  }
  let hour,
    minute = 0,
    period;
  const clock = value.match(/^(\d{1,2})[:.](\d{2})$/);
  const spoken = value.match(
    /^(.+?) час(?:а|ов)?(?: (.+?) минут(?:а|у|ы)?)?(?: (утра|дня|вечера|ночи))?$/,
  );
  const daypart = value.match(/^(.+) (утра|дня|вечера|ночи)$/);
  if (clock) {
    hour = Number(clock[1]);
    minute = Number(clock[2]);
  } else if (spoken) {
    hour = numberValue(spoken[1]);
    minute = spoken[2] ? numberValue(spoken[2]) : 0;
    period = spoken[3];
  } else if (daypart) {
    hour = numberValue(daypart[1]);
    period = daypart[2];
  } else if (value === "полдень") hour = 12;
  else if (value === "полночь") hour = 0;
  else throw new Error("Для будильника скажите, например: «через минуту» или «в 07:10».");
  if (hour === null || minute === null || hour < 0 || hour > 23 || minute < 0 || minute > 59) {
    throw new Error("Проверьте часы и минуты будильника.");
  }
  if (period) {
    if (hour > 12) throw new Error("Уточните время в 24-часовом формате.");
    if (["вечера", "дня"].includes(period) && hour < 12) hour += 12;
    if (["утра", "ночи"].includes(period) && hour === 12) hour = 0;
  }
  const result = new Date(now);
  result.setHours(hour, minute, 0, 0);
  if (result.getTime() <= now) result.setDate(result.getDate() + 1);
  return result.getTime();
}

export function clockTime(timestamp) {
  return new Intl.DateTimeFormat("ru-RU", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(timestamp);
}
export function dateAndTime(timestamp) {
  return new Intl.DateTimeFormat("ru-RU", { dateStyle: "full", timeStyle: "medium" }).format(
    timestamp,
  );
}
export function remainingTime(dueAt, now) {
  const total = Math.max(0, Math.ceil((dueAt - now) / 1000));
  const seconds = String(total % 60).padStart(2, "0");
  const minutes = String(Math.floor(total / 60) % 60).padStart(2, "0");
  const hours = Math.floor(total / 3600);
  return hours ? hours + ":" + minutes + ":" + seconds : minutes + ":" + seconds;
}
