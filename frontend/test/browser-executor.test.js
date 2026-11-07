import test from "node:test";
import assert from "node:assert/strict";
import { setTimeout as delay } from "node:timers/promises";
import { BrowserExecutor } from "../src/features/browser-executor/headless.js";
import {
  alarmDeadline,
  remainingTime,
  dateAndTime,
} from "../src/features/browser-executor/lib/time.js";
import { AssistantController } from "../src/widgets/assistant/model/assistant-controller.js";

function setup({ enabled = true, adapters, onAlarm } = {}) {
  const saved = new Map();
  const storage = {
    getItem: (key) => saved.get(key) ?? null,
    setItem: (key, value) => saved.set(key, value),
    removeItem: (key) => saved.delete(key),
  };
  const browser = {
    document: { documentElement: { dataset: {} } },
    localStorage: storage,
    sessionStorage: storage,
  };
  const sound = {
    rings: 0,
    stops: 0,
    unlock: async () => enabled,
    ring() {
      this.rings++;
      return true;
    },
    stop() {
      this.stops++;
    },
  };
  let now = Date.UTC(2026, 10, 7, 12, 0, 0);
  const executor = new BrowserExecutor({ browser, sound, now: () => now, adapters, onAlarm });
  return {
    browser,
    sound,
    executor,
    now: () => now,
    advance: (ms) => {
      now += ms;
    },
  };
}
function command(id, intent, phase = "ready", value = "через минуту") {
  return {
    id,
    text: "тестовая команда",
    intent,
    intent_name: intent,
    phase,
    confidence: 0.9,
    slots: intent === "alarm_set" ? [{ slot: "time", name: "Время", value }] : [],
    question: null,
    spoken_text: "Подтвердите",
    ready_for_execution: phase === "ready",
    execution_confirmed: false,
    operation_id: null,
    execution_message: null,
  };
}
function result(data, receipt) {
  return {
    ...data,
    phase: receipt.success ? "executed" : "execution_failed",
    ready_for_execution: false,
    execution_confirmed: receipt.success,
    spoken_text: receipt.message,
    execution_message: receipt.message,
    operation_id: receipt.operation_id,
  };
}

test("Относительное время переводится в реальный срок, минуты не теряются", () => {
  const now = Date.UTC(2026, 10, 7, 12, 0, 0);
  for (const [text, seconds] of [
    ["через минуту", 60],
    ["через одну минуту", 60],
    ["на минуту вперед", 60],
    ["через десять секунд", 10],
    ["через полчаса", 1800],
    ["через два часа", 7200],
  ])
    assert.equal(alarmDeadline(text, now), now + seconds * 1000, text);
  assert.throws(() => alarmDeadline("через ноль минут", now));
  assert.throws(() => alarmDeadline("99:99", now));
  const base = new Date(2026, 10, 7, 6, 0, 0).getTime();
  const deadline = new Date(alarmDeadline("семь часов десять минут", base));
  assert.equal(deadline.getHours(), 7);
  assert.equal(deadline.getMinutes(), 10);
  assert.equal(remainingTime(now + 60000, now), "01:00");
  assert.equal(remainingTime(now + 60000, now + 1001), "00:59");
});

test("Будильник дожидается срока, сигналит один раз и останавливается", async () => {
  let notifications = 0;
  const f = setup({ onAlarm: () => notifications++ });
  f.advance(400); // Установка между тиками не должна показывать лишнюю секунду.
  const receipt = await f.executor.execute(command(1, "alarm_set"));
  assert.equal(receipt.success, true);
  assert.equal(f.executor.getSnapshot().alarms[0].dueAt, f.now() + 60000);
  assert.equal(
    remainingTime(f.executor.getSnapshot().alarms[0].dueAt, f.executor.getSnapshot().now),
    "01:00",
  );
  f.advance(59000);
  f.executor.tick();
  assert.equal(f.sound.rings, 0);
  f.advance(1000);
  f.executor.tick();
  assert.equal(f.executor.getSnapshot().alarms[0].status, "ringing");
  assert.equal(f.sound.rings, 1);
  assert.equal(notifications, 1);
  f.advance(1000);
  f.executor.tick();
  assert.equal(notifications, 1);
  f.executor.dismissAlarm("alarm-1");
  assert.equal(f.executor.getSnapshot().alarms.length, 0);
  assert.equal(f.sound.stops, 1);
});

test("Повтор и восстановление квитанции не перезапускают минутный отсчёт", async () => {
  const f = setup();
  const data = command(1, "alarm_set");
  const first = await f.executor.execute(data);
  const dueAt = f.executor.getSnapshot().alarms[0].dueAt;
  f.advance(20000);
  assert.deepEqual(await f.executor.execute(data), first);
  assert.equal(f.executor.getSnapshot().alarms[0].dueAt, dueAt);
  const restored = new BrowserExecutor({ browser: f.browser, sound: f.sound, now: f.now });
  assert.deepEqual(await restored.execute(data), first);
  assert.equal(restored.getSnapshot().alarms[0].dueAt, dueAt);
});

test("Без работающего звука установка не подтверждается", async () => {
  const f = setup({ enabled: false });
  const receipt = await f.executor.execute(command(1, "alarm_set"));
  assert.equal(receipt.success, false);
  assert.match(receipt.message, /звук/);
  assert.equal(f.executor.getSnapshot().alarms.length, 0);
});

test("Свет меняет фон до квитанции, дата берётся из часов устройства", async () => {
  const f = setup();
  const off = await f.executor.execute(command(1, "iot_hue_lightoff"));
  assert.equal(off.success, true);
  assert.equal(f.browser.document.documentElement.dataset.light, "off");
  assert.equal(f.executor.getSnapshot().light, "off");
  await f.executor.execute(command(2, "iot_hue_lighton"));
  assert.equal(f.browser.document.documentElement.dataset.light, "on");
  const clock = await f.executor.execute(command(3, "datetime_query"));
  assert.equal(clock.success, true);
  assert.ok(clock.message.includes(dateAndTime(f.now())));
  assert.equal(f.executor.getSnapshot().lastDateTime, clock.message);
});

test("Исполнитель ждёт согласия, затем отправляет настоящую квитанцию в API", async () => {
  const f = setup();
  const calls = [];
  const data = command(5, "iot_hue_lightoff");
  const c = new AssistantController({
    browser: f.browser,
    executor: f.executor,
    api: async (path, options) => {
      assert.equal(f.browser.document.documentElement.dataset.light, "off");
      calls.push(path);
      const receipt = JSON.parse(options.body);
      assert.equal(receipt.success, true);
      return result(data, receipt);
    },
  });
  const disconnect = c.connect();
  try {
    c.render({ ...data, phase: "awaiting_confirmation" }, { readAloud: false });
    assert.equal(f.browser.document.documentElement.dataset.light, "on");
    assert.equal(calls.length, 0);
    c.render(data);
    await delay(0);
    assert.deepEqual(calls, ["/5/execution"]);
    assert.equal(c.getSnapshot().current.execution_confirmed, true);
    assert.match(c.getSnapshot().current.execution_message, /Свет выключен/);
    assert.equal(c.getSnapshot().current.phase, "executed");
    const completedMessage = c.getSnapshot().lastMessage;
    c.alarmFired();
    assert.equal(c.getSnapshot().lastMessage, completedMessage);
    assert.match(c.getSnapshot().screenreaderMessage, /Будильник. Время вышло/);
  } finally {
    disconnect();
  }
});

test("Сбой API не выдаётся за подтверждение; повтор квитанции не повторяет действие", async () => {
  let effects = 0;
  const f = setup({
    adapters: {
      iot_hue_lightoff: ({ setLight }) => {
        effects++;
        setLight("off");
        return "Свет выключен.";
      },
    },
  });
  let posts = 0;
  const receipts = [];
  const data = command(5, "iot_hue_lightoff");
  const c = new AssistantController({
    browser: f.browser,
    executor: f.executor,
    api: async (path, options) => {
      if (!options) return data;
      receipts.push(JSON.parse(options.body));
      if (++posts === 1) throw new Error("Нет связи");
      return result(data, receipts.at(-1));
    },
  });
  const disconnect = c.connect();
  try {
    c.render(data);
    await delay(0);
    assert.equal(c.getSnapshot().current.execution_confirmed, false);
    assert.equal(c.getSnapshot().current.phase, "ready");
    assert.equal(effects, 1);
    await c.poll();
    assert.equal(c.getSnapshot().current.execution_confirmed, true);
    assert.equal(posts, 2);
    assert.equal(effects, 1);
    assert.deepEqual(receipts[0], receipts[1]);
  } finally {
    disconnect();
  }
});
