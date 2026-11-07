import { PHASES } from "../model/constants.js";

export function DialogueMessage({ state: s, ownSpeech }) {
  return (
    <>
      <div className="assistant-message" role="region" aria-labelledby="assistant-heading">
        <h2 id="assistant-heading">Помощник</h2>
        <p id="phase-label" className="phase" hidden={!s.current}>
          {s.current ? PHASES[s.current.phase] : ""}
        </p>
        <p id="assistant-text">{s.lastMessage}</p>
      </div>
      <p
        id="screenreader-message"
        className="sr-only"
        role="status"
        aria-live={ownSpeech ? "off" : "polite"}
        aria-atomic="true"
      >
        {s.screenreaderMessage}
      </p>
      <p
        id="error"
        className="error"
        role="alert"
        hidden={!s.error}
        aria-live={ownSpeech ? "off" : "assertive"}
      >
        {s.error}
      </p>
    </>
  );
}
