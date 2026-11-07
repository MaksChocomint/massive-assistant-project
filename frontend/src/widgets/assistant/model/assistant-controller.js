import { dialogueApi, HELLO, ACTIVE_PHASES } from "../../../features/dialogue/headless.js";
import { VoiceSession } from "../../../features/voice/headless.js";
import { readStorage, removeStorage, writeStorage } from "../../../shared/lib/storage.js";

const clean = (text) =>
  text
    .toLowerCase()
    .replace(/ё/g, "е")
    .replace(/[.,!?]/g, "")
    .replace(/\s+/g, " ")
    .trim();

/** Browser side effects and API transitions; React owns rendering through the store. */
export class AssistantController {
  constructor({ browser = globalThis, api = dialogueApi } = {}) {
    this.browser = browser;
    this.api = api;
    this.listeners = new Set();
    this.epoch = 0;
    this.connected = false;
    this.pollTimer = null;
    this.pollInFlight = false;
    this.voice = new VoiceSession({
      browser,
      getState: () => this.state,
      onChange: (values) => this.patch(values),
      onText: (text) => this.send(text),
      canResume: () => !this.state.current || ACTIVE_PHASES.has(this.state.current.phase),
      getQuestion: () => this.state.current?.question,
      isConnected: () => this.connected,
    });
    this.state = {
      current: null,
      busy: false,
      voiceActive: false,
      speaking: false,
      paused: false,
      audioEnabled: false,
      speechRate: this.voice.initialRate,
      lastMessage: HELLO,
      screenreaderMessage: "",
      voiceState: "Микрофон выключен",
      error: null,
      transcript: [],
      input: "",
      textEntryOpen: !this.voice.Recognition,
      voiceSupport: !this.voice.Recognition
        ? "Голосовой ввод в этом браузере недоступен. Можно ввести команду текстом."
        : this.voice.localRecognition
          ? "После фразы сделайте паузу — помощник распознает запись и ответит."
          : "",
      localRecognition: this.voice.localRecognition,
    };
    if (!this.voice.canSpeak) {
      this.state.voiceSupport += " Озвучивание браузером недоступно. Используйте экранный диктор.";
    }
  }

  getSnapshot = () => this.state;
  subscribe = (listener) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };
  patch(values) {
    this.state = { ...this.state, ...values };
    this.listeners.forEach((listener) => listener());
  }
  log(who, text) {
    this.patch({ transcript: [...this.state.transcript, { who, text }] });
  }
  connect() {
    this.connected = true;
    const epoch = ++this.epoch;
    this.restore(epoch);
    return () => {
      this.connected = false;
      this.epoch++;
      this.stopPolling();
      this.stopRecognition();
      this.stopSpeech();
    };
  }
  async restore(epoch) {
    let id;
    id = readStorage(this.browser.localStorage, "massive.dialogue");
    if (!id || !/^\d+$/.test(id)) return;
    try {
      const data = await this.api("/" + id);
      if (
        !this.connected ||
        epoch !== this.epoch ||
        this.state.current ||
        this.state.busy ||
        this.state.voiceActive
      )
        return;
      this.log("Вы", data.text);
      this.render(data, { readAloud: false });
      this.patch({ voiceState: "Диалог восстановлен. Микрофон выключен." });
    } catch {
      if (epoch === this.epoch) {
        removeStorage(this.browser.localStorage, "massive.dialogue");
      }
    }
  }
  setInput = (input) => this.patch({ input });
  setTextEntryOpen = (textEntryOpen) => {
    if (this.state.textEntryOpen !== textEntryOpen) this.patch({ textEntryOpen });
  };
  get Recognition() {
    return this.voice.Recognition;
  }
  get canSpeak() {
    return this.voice.canSpeak;
  }
  setSpeechRate = (value) => this.voice.setSpeechRate(value);
  setAudioEnabled = (value) => this.voice.setAudioEnabled(value);
  pauseVoice = () => this.voice.pauseVoice();
  stopRecognition() {
    this.voice.stopRecognition();
  }
  stopSpeech() {
    this.voice.stopSpeech();
  }
  speak(text, resume = false) {
    this.voice.speak(text, resume);
  }
  startVoice = () => {
    if (!this.Recognition) return;
    if (this.state.voiceActive) {
      this.pauseVoice();
      return;
    }
    if (this.state.busy || this.state.current?.phase === "ready") return;
    if (this.state.current && !ACTIVE_PHASES.has(this.state.current.phase))
      this.reset({ readAloud: false });
    this.voice.start(this.state.current?.spoken_text || HELLO);
  };
  startNewCommand = async () => {
    if (this.state.busy) return;
    const current = this.state.current;
    if (current && ACTIVE_PHASES.has(current.phase)) {
      this.stopRecognition();
      this.stopSpeech();
      this.patch({ busy: true, voiceActive: false, speaking: false, error: null });
      const epoch = this.epoch;
      try {
        await this.api("/" + current.id + "/cancel", { method: "POST" });
        if (!this.connected || epoch !== this.epoch) return;
      } catch (error) {
        if (this.connected && epoch === this.epoch) {
          this.patch({ error: error.message, lastMessage: error.message });
          this.speak(error.message);
        }
        return;
      } finally {
        if (this.connected && epoch === this.epoch) this.patch({ busy: false });
      }
    }
    this.reset({ readAloud: false });
    if (this.Recognition) this.voice.start(HELLO);
    else {
      this.patch({ textEntryOpen: true, audioEnabled: this.canSpeak });
      this.speak(HELLO);
    }
  };
  render(data, { prefix = "", readAloud = true } = {}) {
    writeStorage(this.browser.localStorage, "massive.dialogue", data.id);
    const lastMessage = prefix ? prefix + " " + data.spoken_text : data.spoken_text;
    this.patch({ current: data, lastMessage, screenreaderMessage: lastMessage });
    if (readAloud) {
      this.log("Помощник", lastMessage);
      this.speak(lastMessage, this.state.voiceActive && ACTIVE_PHASES.has(data.phase));
    }
    if (data.phase === "ready") this.startPolling();
    else this.stopPolling();
  }
  stopPolling() {
    if (this.pollTimer) clearInterval(this.pollTimer);
    this.pollTimer = null;
  }
  startPolling() {
    if (this.pollTimer) return;
    this.pollCount = this.pollErrors = 0;
    this.pollTimer = setInterval(() => this.poll(), 3000);
  }
  async poll() {
    const current = this.state.current;
    if (!this.connected || this.pollInFlight || current?.phase !== "ready") return;
    this.pollInFlight = true;
    const epoch = this.epoch;
    try {
      const data = await this.api("/" + current.id);
      if (!this.connected || epoch !== this.epoch || this.state.current?.id !== current.id) return;
      this.pollErrors = 0;
      if (data.phase !== "ready") {
        this.stopPolling();
        this.render(data);
      } else if (++this.pollCount >= 60) {
        this.stopPolling();
        const message =
          "Команда сохранена. Ответ от устройства пока не получен. Кнопка «Повторить вслух» проверит состояние ещё раз.";
        this.patch({ lastMessage: message });
        this.log("Помощник", message);
        this.speak(message);
      }
    } catch (error) {
      if (
        this.connected &&
        epoch === this.epoch &&
        this.state.current?.id === current.id &&
        ++this.pollErrors >= 3
      ) {
        this.stopPolling();
        this.patch({ error: error.message });
        this.speak(error.message);
      }
    } finally {
      this.pollInFlight = false;
    }
  }
  send = async (text) => {
    if (this.state.busy) return;
    text = text.trim();
    if (!text) return;
    const control = clean(text);
    if (["повтори", "повтори вопрос", "повтори сообщение"].includes(control)) {
      await this.repeat();
      return;
    }
    if (["стоп", "пауза"].includes(control)) {
      this.pauseVoice();
      return;
    }
    if (
      ["отмена", "отмени", "отмени команду", "отменить"].includes(control) &&
      this.state.current
    ) {
      await this.cancel();
      return;
    }
    if (this.state.current?.phase === "ready") return;
    this.stopRecognition();
    this.patch({ paused: false, busy: true, error: null, voiceState: "Обрабатываю запрос" });
    this.log("Вы", text);
    const epoch = this.epoch;
    try {
      const current = this.state.current;
      const answering = current && ACTIVE_PHASES.has(current.phase);
      const data = await this.api(answering ? "/" + current.id + "/answer" : "", {
        method: "POST",
        body: JSON.stringify(answering ? { answer: text } : { text }),
      });
      if (!this.connected || epoch !== this.epoch) return;
      this.patch({ busy: false, input: "" });
      this.render(data);
    } catch (error) {
      if (!this.connected || epoch !== this.epoch) return;
      this.patch({ busy: false, error: error.message });
      const current = this.state.current;
      if (current) {
        try {
          const data = await this.api("/" + current.id);
          if (this.connected && epoch === this.epoch) this.render(data, { prefix: error.message });
        } catch {
          this.patch({ lastMessage: error.message });
          this.speak(error.message);
        }
      } else {
        this.patch({ lastMessage: error.message });
        this.speak(error.message, this.state.voiceActive);
      }
    } finally {
      if (this.connected && epoch === this.epoch) this.patch({ busy: false });
    }
  };
  cancel = async () => {
    const current = this.state.current;
    if (this.state.busy || !current || !ACTIVE_PHASES.has(current.phase)) return;
    this.stopRecognition();
    this.stopSpeech();
    this.patch({ busy: true, voiceActive: false, speaking: false });
    const epoch = this.epoch;
    try {
      const data = await this.api("/" + current.id + "/cancel", { method: "POST" });
      if (!this.connected || epoch !== this.epoch) return;
      this.patch({ busy: false });
      this.render(data);
    } catch (error) {
      if (this.connected && epoch === this.epoch) {
        this.patch({ error: error.message });
        this.speak(error.message);
      }
    } finally {
      if (this.connected && epoch === this.epoch) this.patch({ busy: false });
    }
  };
  repeat = async () => {
    if (this.state.busy) return;
    this.patch({ paused: false, audioEnabled: this.canSpeak });
    const epoch = this.epoch;
    if (this.state.current) {
      try {
        const data = await this.api("/" + this.state.current.id);
        if (this.connected && epoch === this.epoch) this.render(data);
      } catch (error) {
        if (this.connected && epoch === this.epoch) {
          this.patch({ error: error.message });
          this.speak(this.state.lastMessage);
        }
      }
    } else this.speak(this.state.lastMessage, this.state.voiceActive);
  };
  reset = ({ readAloud = true } = {}) => {
    if (this.state.busy) return;
    this.epoch++;
    this.stopPolling();
    this.stopRecognition();
    this.stopSpeech();
    removeStorage(this.browser.localStorage, "massive.dialogue");
    this.patch({
      current: null,
      voiceActive: false,
      speaking: false,
      paused: false,
      transcript: [],
      error: null,
      lastMessage: HELLO,
      input: "",
      voiceState: "Микрофон выключен",
    });
    if (readAloud) this.speak(HELLO);
    else this.patch({ screenreaderMessage: HELLO });
  };
}
