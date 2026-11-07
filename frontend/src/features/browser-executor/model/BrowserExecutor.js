import { readStorage, writeStorage } from "../../../shared/lib/storage.js";
import { AlarmSound } from "../lib/alarm-sound.js";
import { browserAdapters } from "./adapters.js";

const KEY = "massive.browser-execution";
function savedState(storage) {
  try {
    const value = JSON.parse(readStorage(storage, KEY, "{}"));
    return {
      light: value.light === "off" ? "off" : "on",
      alarms: Array.isArray(value.alarms)
        ? value.alarms.filter(
            (a) =>
              typeof a?.id === "string" &&
              Number.isSafeInteger(a.dueAt) &&
              ["pending", "ringing"].includes(a.status),
          )
        : [],
      receipts: Array.isArray(value.receipts)
        ? value.receipts.filter(
            ([id, r]) =>
              typeof id === "string" &&
              typeof r?.operation_id === "string" &&
              typeof r.success === "boolean" &&
              typeof r.message === "string",
          )
        : [],
    };
  } catch {
    return { light: "on", alarms: [], receipts: [] };
  }
}

/** Local targets execute first. Cached receipts make HTTP retries side-effect free. */
export class BrowserExecutor {
  constructor({
    browser = globalThis,
    now = () => Date.now(),
    sound = new AlarmSound(browser),
    onAlarm = () => {},
    adapters = browserAdapters,
  } = {}) {
    Object.assign(this, { browser, now, sound, onAlarm, adapters });
    const saved = savedState(browser.sessionStorage);
    this.receipts = new Map(saved.receipts);
    this.running = new Map();
    this.listeners = new Set();
    this.timer = null;
    this.state = {
      light: saved.light,
      alarms: saved.alarms,
      now: now(),
      soundEnabled: false,
      lastDateTime: "",
    };
  }
  getSnapshot = () => this.state;
  subscribe = (listener) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };
  patch(values, persist = false) {
    this.state = { ...this.state, ...values };
    if (persist) this.persist();
    this.listeners.forEach((listener) => listener());
  }
  persist() {
    writeStorage(
      this.browser.sessionStorage,
      KEY,
      JSON.stringify({
        light: this.state.light,
        alarms: this.state.alarms,
        receipts: [...this.receipts],
      }),
    );
  }
  connect() {
    this.applyLight(this.state.light);
    this.tick();
    this.timer = setInterval(() => this.tick(), 1000);
    return () => this.disconnect();
  }
  disconnect() {
    clearInterval(this.timer);
    this.timer = null;
    this.sound.stop();
  }
  supports(intent) {
    return Object.hasOwn(this.adapters, intent);
  }
  enableAudio = async () => {
    const enabled = await this.sound.unlock();
    this.patch({ soundEnabled: enabled });
    if (enabled && this.state.alarms.some((a) => a.status === "ringing")) this.sound.ring();
    return enabled;
  };
  applyLight(mode) {
    if (!this.browser.document?.documentElement)
      throw new Error("Не удалось изменить фон страницы.");
    this.browser.document.documentElement.dataset.light = mode;
  }
  setLight = (mode) => {
    this.applyLight(mode);
    this.patch({ light: mode }, true);
  };
  scheduleAlarm = ({ id, dueAt }) => {
    const existing = this.state.alarms.find((a) => a.id === id);
    if (existing) return existing;
    const alarm = { id, dueAt, status: "pending" };
    this.patch({ alarms: [...this.state.alarms, alarm], now: this.now() }, true);
    return alarm;
  };
  dismissAlarm = (id) => {
    this.patch({ alarms: this.state.alarms.filter((a) => a.id !== id) }, true);
    if (!this.state.alarms.some((a) => a.status === "ringing")) this.sound.stop();
  };
  tick() {
    const now = this.now();
    const fired = this.state.alarms.filter((a) => a.status === "pending" && a.dueAt <= now);
    if (fired.length) {
      const ids = new Set(fired.map((a) => a.id));
      const alarms = this.state.alarms.map((a) =>
        ids.has(a.id) ? { ...a, status: "ringing" } : a,
      );
      this.patch({ now, alarms, soundEnabled: this.sound.ring() }, true);
      this.onAlarm(fired[0]);
    } else this.patch({ now });
  }
  execute(command) {
    const key = String(command.id);
    if (this.receipts.has(key)) return Promise.resolve(this.receipts.get(key));
    if (this.running.has(key)) return this.running.get(key);
    const task = this.perform(command).finally(() => this.running.delete(key));
    this.running.set(key, task);
    return task;
  }
  async perform(command) {
    let receipt;
    try {
      if (!this.supports(command.intent))
        throw new Error("Для этой команды пока нет браузерного исполнителя.");
      const message = await this.adapters[command.intent]({
        command,
        now: this.now,
        enableAudio: this.enableAudio,
        scheduleAlarm: this.scheduleAlarm,
        setLight: this.setLight,
        setDateTime: (value) => this.patch({ lastDateTime: value }),
      });
      receipt = { operation_id: "browser-" + command.id, success: true, message };
    } catch (error) {
      receipt = {
        operation_id: "browser-" + command.id,
        success: false,
        message: error.message || "Не удалось выполнить команду.",
      };
    }
    this.receipts.set(String(command.id), receipt);
    this.persist();
    return receipt;
  }
}
