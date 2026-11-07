// Firefox fallback: microphone PCM -> bounded WAV -> local Russian ASR.
const Context = globalThis.AudioContext || globalThis.webkitAudioContext;
const MAX_SECONDS = 20;
const OUTPUT_RATE = 16000;

function wav(chunks, sampleRate) {
  const total = Math.min(
    chunks.reduce((n, c) => n + c.length, 0),
    sampleRate * MAX_SECONDS,
  );
  const input = new Float32Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    const size = Math.min(chunk.length, total - offset);
    if (size <= 0) break;
    input.set(chunk.subarray(0, size), offset);
    offset += size;
  }
  const ratio = sampleRate / OUTPUT_RATE;
  const samples = Math.floor(total / ratio);
  const data = new DataView(new ArrayBuffer(44 + samples * 2));
  const text = (at, value) => {
    for (let i = 0; i < value.length; i++) data.setUint8(at + i, value.charCodeAt(i));
  };
  text(0, "RIFF");
  data.setUint32(4, 36 + samples * 2, true);
  text(8, "WAVE");
  text(12, "fmt ");
  data.setUint32(16, 16, true);
  data.setUint16(20, 1, true);
  data.setUint16(22, 1, true);
  data.setUint32(24, OUTPUT_RATE, true);
  data.setUint32(28, OUTPUT_RATE * 2, true);
  data.setUint16(32, 2, true);
  data.setUint16(34, 16, true);
  text(36, "data");
  data.setUint32(40, samples * 2, true);
  for (let i = 0; i < samples; i++) {
    const first = Math.floor(i * ratio);
    const last = Math.min(total, Math.max(first + 1, Math.floor((i + 1) * ratio)));
    let value = 0;
    for (let j = first; j < last; j++) value += input[j];
    value = Math.max(-1, Math.min(1, value / (last - first)));
    data.setInt16(44 + i * 2, value * (value < 0 ? 32768 : 32767), true);
  }
  return new Blob([data], { type: "audio/wav" });
}

export class LocalSpeechRecognition {
  static supported() {
    return Boolean(
      globalThis.navigator?.mediaDevices?.getUserMedia &&
      Context &&
      globalThis.AudioWorkletNode &&
      globalThis.isSecureContext,
    );
  }
  start() {
    if (this.active) throw new Error("Recognition already started");
    this.active = true;
    this.finishing = false;
    this.chunks = [];
    this.controller = new AbortController();
    this._start().catch((error) => {
      if (this.active)
        this._fail(error.name === "NotAllowedError" ? "not-allowed" : "audio-capture");
    });
  }
  async _start() {
    const context = new Context();
    this.context = context;
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
      },
    });
    if (!this.active) {
      stream.getTracks().forEach((track) => track.stop());
      await context.close().catch(() => {});
      return;
    }
    this.stream = stream;
    this.sampleRate = context.sampleRate;
    await context.audioWorklet.addModule(new URL("./speech-capture-worklet.js", import.meta.url));
    if (!this.active) return;
    this.source = context.createMediaStreamSource(stream);
    this.node = new AudioWorkletNode(context, "speech-capture");
    this.sink = context.createGain();
    this.sink.gain.value = 0;
    this.node.port.onmessage = (event) => this._chunk(event.data);
    this.source.connect(this.node);
    this.node.connect(this.sink);
    this.sink.connect(context.destination);
    await context.resume();
    if (!this.active) return;
    this.startedAt = performance.now();
    this.lastVoiceAt = null;
    this.onstart?.();
    this.timer = setInterval(() => {
      if (!this.active || this.finishing) return;
      const now = performance.now();
      if (this.lastVoiceAt === null && now - this.startedAt >= 8000) this._fail("no-speech");
      else if (
        now - this.startedAt >= MAX_SECONDS * 1000 ||
        (this.lastVoiceAt !== null && now - this.lastVoiceAt >= 1100)
      )
        this._finish();
    }, 100);
  }
  _chunk(chunk) {
    if (!this.active || this.finishing) return;
    this.chunks.push(chunk);
    let energy = 0;
    for (const sample of chunk) energy += sample * sample;
    if (Math.sqrt(energy / chunk.length) >= 0.012) this.lastVoiceAt = performance.now();
  }
  _releaseMicrophone() {
    clearInterval(this.timer);
    if (this.node) this.node.port.onmessage = null;
    for (const node of [this.source, this.node, this.sink]) {
      try {
        node?.disconnect();
      } catch {}
    }
    this.stream?.getTracks().forEach((track) => track.stop());
    if (this.context && this.context.state !== "closed") this.context.close().catch(() => {});
    this.source = this.node = this.sink = this.stream = this.context = null;
  }
  async _finish() {
    if (!this.active || this.finishing) return;
    this.finishing = true;
    this._releaseMicrophone();
    this.onaudioend?.();
    const form = new FormData();
    form.append("audio", wav(this.chunks, this.sampleRate), "command.wav");
    this.chunks = [];
    const timeout = setTimeout(() => this.controller.abort(), 30000);
    try {
      const response = await fetch("/api/speech/transcribe", {
        method: "POST",
        body: form,
        signal: this.controller.signal,
      });
      if (!this.active) return;
      if (!response.ok) {
        this._fail(response.status === 400 ? "no-speech" : "service-not-allowed");
        return;
      }
      const result = await response.json();
      if (!this.active) return;
      if (!result.text?.trim()) {
        this._fail("no-speech");
        return;
      }
      this.onresult?.({ resultIndex: 0, results: [[{ transcript: result.text }]] });
      if (this.active) {
        this.active = false;
        this.onend?.();
      }
    } catch {
      if (this.active) this._fail("network");
    } finally {
      clearTimeout(timeout);
    }
  }
  _fail(error) {
    if (!this.active) return;
    this.active = false;
    this._releaseMicrophone();
    this.controller?.abort();
    this.chunks = [];
    this.onerror?.({ error });
  }
  abort() {
    this.active = false;
    this._releaseMicrophone();
    this.controller?.abort();
    this.chunks = [];
  }
}
