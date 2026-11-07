export class AlarmSound {
  constructor(browser = globalThis) {
    this.browser = browser;
    this.nodes = new Set();
    this.context = null;
    this.timer = null;
  }
  async unlock() {
    const Context = this.browser.AudioContext || this.browser.webkitAudioContext;
    if (!Context) return false;
    try {
      if (!this.context || this.context.state === "closed") this.context = new Context();
      if (this.context.state === "suspended") await this.context.resume();
      return this.context.state === "running";
    } catch {
      return false;
    }
  }
  pulse() {
    if (this.context?.state !== "running") return;
    for (const [offset, frequency] of [
      [0, 880],
      [0.3, 1100],
    ]) {
      const oscillator = this.context.createOscillator();
      const gain = this.context.createGain();
      const start = this.context.currentTime + offset;
      oscillator.type = "sine";
      oscillator.frequency.value = frequency;
      gain.gain.setValueAtTime(0, start);
      gain.gain.linearRampToValueAtTime(0.12, start + 0.015);
      gain.gain.setValueAtTime(0.12, start + 0.16);
      gain.gain.linearRampToValueAtTime(0, start + 0.22);
      oscillator.connect(gain);
      gain.connect(this.context.destination);
      const entry = { oscillator, gain };
      this.nodes.add(entry);
      oscillator.onended = () => {
        oscillator.disconnect();
        gain.disconnect();
        this.nodes.delete(entry);
      };
      oscillator.start(start);
      oscillator.stop(start + 0.23);
    }
  }
  ring() {
    if (this.context?.state !== "running") return false;
    if (!this.timer) {
      this.pulse();
      this.timer = setInterval(() => this.pulse(), 1200);
    }
    return true;
  }
  stop() {
    clearInterval(this.timer);
    this.timer = null;
    for (const { oscillator, gain } of this.nodes) {
      try {
        oscillator.stop();
      } catch {}
      oscillator.disconnect();
      gain.disconnect();
    }
    this.nodes.clear();
  }
}
