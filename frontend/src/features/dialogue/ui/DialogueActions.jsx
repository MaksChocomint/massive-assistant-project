import { ACTIVE_PHASES } from "../model/constants.js";

export function DialogueActions({ current, busy, canSpeak, onRepeat, onCancel, onNew }) {
  const active = current && ACTIVE_PHASES.has(current.phase);
  return (
    <div className="dialogue-actions">
      <button
        id="repeat-button"
        className="button"
        type="button"
        aria-keyshortcuts="Alt+R"
        disabled={!canSpeak}
        onClick={onRepeat}
      >
        Повторить вслух
      </button>
      <button
        id="cancel-button"
        className="button"
        type="button"
        disabled={busy || !active}
        onClick={onCancel}
      >
        Отменить команду
      </button>
      <button
        id="new-button"
        className="button"
        type="button"
        hidden={!current || active}
        disabled={busy}
        onClick={onNew}
      >
        Новая команда
      </button>
    </div>
  );
}
