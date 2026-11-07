import { ACTIVE_PHASES } from "../model/constants.js";

export function TextEntry({ state: s, onInput, onSubmit, onOpen }) {
  const answering = s.current && ACTIVE_PHASES.has(s.current.phase);
  const pending = s.current?.phase === "ready";
  const placeholder = answering
    ? s.current.phase === "awaiting_confirmation"
      ? "Подтверждение"
      : "Ответ"
    : "Команда";
  return (
    <details
      id="text-entry"
      open={s.textEntryOpen}
      onToggle={(event) => onOpen(event.currentTarget.open)}
    >
      <summary>Ввести текстом</summary>
      <form
        id="text-form"
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit(s.input);
        }}
      >
        <label htmlFor="message" id="message-label">
          {answering ? "Ваш ответ" : "Ваша команда"}
        </label>
        <div className="text-row">
          <input
            id="message"
            type="text"
            maxLength={answering ? 200 : 300}
            autoComplete="off"
            placeholder={placeholder}
            required
            value={s.input}
            readOnly={s.busy || pending}
            onChange={(e) => onInput(e.target.value)}
          />
          <button
            id="send-button"
            className="button primary"
            type="submit"
            disabled={s.busy || pending}
          >
            Отправить
          </button>
        </div>
      </form>
    </details>
  );
}
