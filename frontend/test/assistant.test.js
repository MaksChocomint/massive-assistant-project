import test from "node:test";
import assert from "node:assert/strict";
import { setTimeout as delay } from "node:timers/promises";
import { AssistantController } from "../src/widgets/assistant/model/assistant-controller.js";

import { HELLO } from "../src/features/dialogue/headless.js";

function assistant(options) {
  const executor = {
    supports: () => false,
    enableAudio: async () => false,
    connect: () => () => {},
    disconnect() {},
  };
  return new AssistantController({ executor, ...options });
}
function browser() {
  const saved = new Map();
  const calls = { starts: 0, stops: 0, spoken: [] };
  return {
    calls,
    saved,
    localStorage: {
      getItem: (key) => saved.get(key) ?? null,
      setItem: (key, value) => saved.set(key, value),
      removeItem: (key) => saved.delete(key),
    },
    SpeechRecognition: class {
      start() {
        calls.starts++;
        this.onstart?.();
      }
      abort() {
        calls.stops++;
      }
    },
    SpeechSynthesisUtterance: class {
      constructor(text) {
        this.text = text;
      }
    },
    speechSynthesis: {
      getVoices: () => [],
      cancel() {},
      speak: (u) => {
        calls.spoken.push(u);
        queueMicrotask(() => u.onend?.());
      },
    },
  };
}
function dialogue(phase) {
  return {
    id: 42,
    text: "поставь будильник",
    phase,
    intent: "alarm_set",
    intent_name: "Будильник",
    confidence: 0.9,
    slots: [],
    question: "На какое время поставить будильник?",
    spoken_text: "На какое время поставить будильник?",
    ready_for_execution: phase === "ready",
    execution_confirmed: phase === "executed",
    operation_id: null,
    execution_message: null,
  };
}

test("Говорить после любого завершённого диалога начинает новую запись", async () => {
  for (const phase of ["cancelled", "failed", "executed", "execution_failed"]) {
    const env = browser();
    env.saved.set("massive.dialogue", "42");
    const controller = assistant({ browser: env, api: async () => dialogue(phase) });
    const disconnect = controller.connect();
    await delay(0);
    assert.equal(controller.getSnapshot().current.phase, phase);
    controller.startVoice();
    await delay(280);
    assert.equal(env.calls.starts, 1, phase);
    assert.equal(controller.getSnapshot().current, null);
    assert.equal(controller.getSnapshot().voiceActive, true);
    assert.equal(env.saved.has("massive.dialogue"), false);
    assert.deepEqual(
      env.calls.spoken.map((u) => u.text),
      [HELLO],
    );
    disconnect();
    assert.equal(env.calls.stops, 1);
  }
});

test("Escape во время приветствия не позволяет позднему onend включить микрофон", async () => {
  const env = browser();
  const controller = assistant({ browser: env });
  const disconnect = controller.connect();
  controller.startVoice();
  controller.pauseVoice();
  await delay(280);
  assert.equal(env.calls.starts, 0);
  assert.equal(controller.getSnapshot().voiceActive, false);
  disconnect();
});

test("Старый результат после остановки записи не создаёт команду", async () => {
  const env = browser();
  let requests = 0;
  const controller = assistant({
    browser: env,
    api: async () => {
      requests++;
      return dialogue("clarifying");
    },
  });
  const disconnect = controller.connect();
  controller.startVoice();
  await delay(280);
  const lateResult = controller.voice.recognition.onresult;
  controller.pauseVoice();
  lateResult({ results: [[{ transcript: "поставь будильник" }]], resultIndex: 0 });
  await delay(0);
  assert.equal(requests, 0);
  disconnect();
});

test("Скорость проверяется, сохраняется и применяется к речи", () => {
  const env = browser();
  env.saved.set("massive.speechRate", "NaN");
  const controller = assistant({ browser: env });
  const disconnect = controller.connect();
  assert.equal(controller.getSnapshot().speechRate, 1);
  controller.setSpeechRate("1.4");
  controller.patch({ lastMessage: "Старая ошибка микрофона", error: "Старая ошибка" });
  controller.startVoice();
  assert.equal(env.calls.spoken[0].rate, 1.4);
  assert.equal(controller.getSnapshot().lastMessage, HELLO);
  assert.equal(controller.getSnapshot().error, null);
  assert.equal(env.saved.get("massive.speechRate"), "1.4");
  controller.setSpeechRate("12");
  assert.equal(controller.getSnapshot().speechRate, 1);
  disconnect();
});

test("Повторное нажатие отправки не создаёт второй запрос", async () => {
  const env = browser();
  let finish,
    requests = 0;
  const controller = assistant({
    browser: env,
    api: () => {
      requests++;
      return new Promise((resolve) => {
        finish = resolve;
      });
    },
  });
  const disconnect = controller.connect();
  const pending = controller.send("поставь будильник");
  await controller.send("поставь ещё один");
  assert.equal(requests, 1);
  finish(dialogue("clarifying"));
  await pending;
  assert.equal(controller.getSnapshot().current.id, 42);
  assert.equal(controller.getSnapshot().busy, false);
  disconnect();
});

test("Новая команда доступна сразу и запускает запись после одного приглашения", async () => {
  for (const phase of [
    null,
    "clarifying",
    "awaiting_confirmation",
    "ready",
    "cancelled",
    "executed",
  ]) {
    const env = browser();
    const requests = [];
    const controller = assistant({
      browser: env,
      api: async (path, options) => {
        requests.push({ path, method: options?.method });
        return dialogue("cancelled");
      },
    });
    const disconnect = controller.connect();
    if (phase) controller.render(dialogue(phase), { readAloud: false });
    await controller.startNewCommand();
    await delay(280);
    assert.equal(env.calls.starts, 1, phase ?? "initial");
    assert.equal(controller.getSnapshot().current, null);
    assert.equal(controller.getSnapshot().voiceActive, true);
    assert.equal(env.saved.has("massive.dialogue"), false);
    assert.deepEqual(
      env.calls.spoken.map((u) => u.text),
      [HELLO],
    );
    assert.deepEqual(
      requests,
      ["clarifying", "awaiting_confirmation"].includes(phase)
        ? [{ path: "/42/cancel", method: "POST" }]
        : [],
    );
    disconnect();
  }
});

test("Позднее восстановление не возвращает старый диалог после Новой команды", async () => {
  const env = browser();
  env.saved.set("massive.dialogue", "42");
  let finish;
  const controller = assistant({
    browser: env,
    api: () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  });
  const disconnect = controller.connect();
  await controller.startNewCommand();
  finish(dialogue("cancelled"));
  await delay(280);
  assert.equal(controller.getSnapshot().current, null);
  assert.equal(env.calls.starts, 1);
  assert.equal(controller.getSnapshot().voiceActive, true);
  disconnect();
});

test("Ошибка отмены сохраняет текущий диалог и не включает новый микрофон", async () => {
  const env = browser();
  const controller = assistant({
    browser: env,
    api: async () => {
      throw new Error("Нет связи");
    },
  });
  const disconnect = controller.connect();
  controller.render(dialogue("clarifying"), { readAloud: false });
  await controller.startNewCommand();
  await delay(280);
  assert.equal(controller.getSnapshot().current.id, 42);
  assert.equal(controller.getSnapshot().busy, false);
  assert.equal(controller.getSnapshot().error, "Нет связи");
  assert.equal(env.calls.starts, 0);
  disconnect();
});
