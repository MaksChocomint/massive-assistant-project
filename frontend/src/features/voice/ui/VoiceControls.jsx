export function VoiceControls({
  voice: s,
  available,
  canSpeak,
  blocked,
  onToggle,
  onAudioEnabled,
  onSpeechRate,
}) {
  const rate = s.speechRate.toLocaleString("ru-RU", { maximumFractionDigits: 1 });
  return (
    <>
      <div className="voice-controls">
        <button
          id="voice-button"
          className="button voice-button"
          type="button"
          aria-pressed={s.voiceActive}
          aria-keyshortcuts="Alt+M"
          disabled={!available || blocked}
          onClick={onToggle}
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <rect x="9" y="2" width="6" height="13" rx="3" />
            <path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3M8 22h8" />
          </svg>
          <span>{s.voiceActive ? "Пауза" : "Говорить"}</span>
        </button>
        <p
          id="voice-state"
          role="status"
          aria-live={s.speaking ? "off" : "polite"}
          aria-atomic="true"
        >
          {s.voiceState}
        </p>
      </div>
      <p
        id="voice-support"
        className={"support-note" + (s.localRecognition ? " info" : "")}
        hidden={!s.voiceSupport}
      >
        {s.voiceSupport}
      </p>
      <label className="audio-option">
        <input
          type="checkbox"
          id="audio-enabled"
          checked={s.audioEnabled}
          disabled={!canSpeak}
          onChange={(e) => onAudioEnabled(e.target.checked)}
        />
        Озвучивать ответы помощника
      </label>
      <div className="speech-rate">
        <div className="speech-rate-title">
          <label htmlFor="speech-rate">Скорость озвучивания</label>
          <output id="speech-rate-value" htmlFor="speech-rate" aria-live="off">
            {rate}×
          </output>
        </div>
        <input
          id="speech-rate"
          type="range"
          min="0.5"
          max="2"
          step="0.1"
          value={s.speechRate}
          aria-valuetext={rate + " от обычной скорости"}
          aria-describedby="speech-rate-help"
          disabled={!canSpeak}
          onChange={(e) => onSpeechRate(e.target.value)}
        />
        <p id="speech-rate-help">От 0,5× до 2×. Для следующего прочтения.</p>
      </div>
    </>
  );
}
