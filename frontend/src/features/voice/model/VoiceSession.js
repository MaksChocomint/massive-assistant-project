import { LocalSpeechRecognition } from "../lib/speech-recognition.js";
import { readStorage, speechRate as normalizeRate } from "../../../shared/lib/storage.js";

/** Audio transport and speech lifecycle; knows nothing about dialogue phases or React. */
export class VoiceSession {
  constructor({ browser, getState, onChange, onText, canResume, getQuestion, isConnected }) {
    Object.assign(this, {
      browser,
      getState,
      onChange,
      onText,
      canResume,
      getQuestion,
      isConnected,
    });
    const native = browser.SpeechRecognition || browser.webkitSpeechRecognition;
    this.Recognition =
      native || (LocalSpeechRecognition.supported() ? LocalSpeechRecognition : null);
    this.localRecognition = Boolean(this.Recognition && !native);
    this.canSpeak =
      typeof browser.speechSynthesis?.speak === "function" &&
      typeof browser.SpeechSynthesisUtterance === "function";
    this.initialRate = normalizeRate(readStorage(browser.localStorage, "massive.speechRate", 1));
    this.recognitionEpoch = this.speechEpoch = this.noSpeechCount = 0;
    this.recognition = null;
  }
  dispose() {
    this.stopRecognition();
    this.stopSpeech();
  }
  start(prompt) {
    if (!this.Recognition || this.getState().busy) return;
    this.noSpeechCount = 0;
    this.onChange({
      paused: false,
      voiceActive: true,
      error: null,
      audioEnabled: this.canSpeak,
      lastMessage: prompt,
    });
    this.speak(prompt, true);
    if (!this.canSpeak) {
      this.onChange({ voiceActive: true });
      this.startListening();
    }
  }
  setSpeechRate = (value) => {
    const speechRate = normalizeRate(value);
    this.onChange({ speechRate });
    try {
      this.browser.localStorage.setItem("massive.speechRate", String(speechRate));
    } catch {}
  };
  setAudioEnabled = (audioEnabled) => {
    this.onChange({ audioEnabled, paused: false });
    if (!audioEnabled) {
      this.pauseVoice();
      this.onChange({ screenreaderMessage: this.getState().lastMessage });
    }
  };
  stopRecognition() {
    this.recognitionEpoch++;
    const previous = this.recognition;
    this.recognition = null;
    if (previous) {
      previous.onstart =
        previous.onresult =
        previous.onerror =
        previous.onend =
        previous.onaudioend =
          null;
      try {
        previous.abort();
      } catch {}
    }
  }
  stopSpeech() {
    this.speechEpoch++;
    if (this.canSpeak) this.browser.speechSynthesis.cancel();
  }
  pauseVoice = () => {
    this.stopRecognition();
    this.stopSpeech();
    this.onChange({
      voiceActive: false,
      speaking: false,
      paused: true,
      voiceState: "Пауза.",
    });
  };
  speak(text, resume = false) {
    this.stopRecognition();
    this.stopSpeech();
    this.onChange({ screenreaderMessage: text, speaking: false });
    if (!this.getState().audioEnabled || !this.canSpeak || this.getState().paused) {
      this.onChange({
        voiceActive: false,
        voiceState: "Микрофон выключен.",
      });
      return;
    }
    const epoch = ++this.speechEpoch;
    const utterance = new this.browser.SpeechSynthesisUtterance(text);
    utterance.lang = "ru-RU";
    utterance.rate = this.getState().speechRate;
    const voices = this.browser.speechSynthesis.getVoices().filter((v) => /^ru/i.test(v.lang));
    utterance.voice = voices.find((v) => v.localService) || voices[0] || null;
    this.onChange({ speaking: true, voiceState: "Помощник говорит" });
    utterance.onend = () => {
      if (!this.isConnected() || epoch !== this.speechEpoch) return;
      this.onChange({ speaking: false });
      const { voiceActive } = this.getState();
      if (resume && voiceActive && this.canResume()) {
        this.onChange({ voiceState: "Включаю микрофон" });
        setTimeout(() => {
          if (epoch === this.speechEpoch && this.isConnected()) this.startListening();
        }, 250);
      } else {
        this.onChange({ voiceActive: false, voiceState: "Микрофон выключен" });
      }
    };
    utterance.onerror = () => {
      if (epoch !== this.speechEpoch) return;
      this.onChange({
        speaking: false,
        voiceActive: false,
        paused: true,
        screenreaderMessage: text,
        voiceState: "Озвучивание недоступно.",
      });
    };
    this.browser.speechSynthesis.speak(utterance);
  }
  recognitionFailure(code) {
    this.stopRecognition();
    if (code === "aborted") return;
    const errors = {
      "not-allowed": "Нет доступа к микрофону.",
      "service-not-allowed": "Распознавание речи недоступно.",
      "audio-capture": "Микрофон не найден или занят.",
      network: "Нет связи с распознаванием речи.",
      "language-not-supported": "Распознавание русской речи недоступно в этом браузере.",
    };
    if (errors[code]) {
      this.onChange({
        voiceActive: false,
        textEntryOpen: true,
        error: errors[code],
        lastMessage: errors[code],
      });
      this.speak(errors[code]);
      return;
    }
    this.noSpeechCount++;
    const retry = this.getState().voiceActive && this.noSpeechCount < 3;
    const question = this.getQuestion() || "Повторите.";
    const message = retry ? "Не расслышал. " + question : "Не расслышал. Запись остановлена.";
    this.onChange({
      error: message,
      lastMessage: message,
      ...(retry ? {} : { voiceActive: false }),
    });
    this.speak(message, retry);
  }
  startListening() {
    if (
      !this.isConnected() ||
      !this.getState().voiceActive ||
      this.getState().busy ||
      this.getState().speaking ||
      this.recognition ||
      !this.Recognition
    )
      return;
    const epoch = ++this.recognitionEpoch;
    const instance = new this.Recognition();
    this.recognition = instance;
    Object.assign(instance, {
      lang: "ru-RU",
      continuous: false,
      interimResults: false,
      maxAlternatives: 1,
    });
    instance.onstart = () => {
      if (epoch === this.recognitionEpoch) this.onChange({ voiceState: "Слушаю." });
    };
    instance.onresult = (event) => {
      if (epoch !== this.recognitionEpoch) return;
      const result = event.results[event.resultIndex ?? 0];
      const text = result?.[0]?.transcript?.trim();
      this.stopRecognition();
      if (!text) {
        this.recognitionFailure("no-speech");
        return;
      }
      this.noSpeechCount = 0;
      this.onText(text);
    };
    instance.onerror = (event) => {
      if (epoch === this.recognitionEpoch) this.recognitionFailure(event.error);
    };
    instance.onaudioend = () => {
      if (epoch === this.recognitionEpoch) this.onChange({ voiceState: "Распознаю запись…" });
    };
    instance.onend = () => {
      if (epoch !== this.recognitionEpoch) return;
      this.stopRecognition();
      if (this.getState().voiceActive && !this.getState().busy && !this.getState().speaking)
        this.recognitionFailure("no-speech");
    };
    try {
      instance.start();
    } catch {
      this.recognitionFailure("audio-capture");
    }
  }
}
