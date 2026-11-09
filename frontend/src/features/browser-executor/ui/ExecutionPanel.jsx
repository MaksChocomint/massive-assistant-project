import { clockTime, dateAndTime, remainingTime } from "../lib/time.js";
import "./execution-panel.css";

export function ExecutionPanel({ state, busy, onExample, onDismiss, onEnableAudio }) {
  const ringing = state.alarms.some((a) => a.status === "ringing");
  return (
    <aside className="execution-panel" aria-label="Будильник, свет, дата и время">
      <h2>Попробуйте команды</h2>
      <p className="execution-caption">Действия выполняются в этой вкладке после вашего «да».</p>
      <section aria-labelledby="alarm-title">
        <h3 id="alarm-title">Будильник</h3>
        <button
          id="example-alarm"
          className="button"
          disabled={busy}
          onClick={() => onExample("Поставь будильник через минуту")}
        >
          Поставь будильник через минуту
        </button>
        {!state.alarms.length && <p className="execution-muted">Активных будильников нет</p>}
        <ul className="alarm-list">
          {state.alarms.map((alarm) => (
            <li key={alarm.id} data-alarm-state={alarm.status} data-alarm-id={alarm.id}>
              <p>На {clockTime(alarm.dueAt)}</p>
              <output
                className="alarm-countdown"
                role="timer"
                aria-live="off"
                aria-label={"До будильника на " + clockTime(alarm.dueAt)}
              >
                {alarm.status === "ringing" ? "Время вышло" : remainingTime(alarm.dueAt, state.now)}
              </output>
              <button className="button" onClick={() => onDismiss(alarm.id)}>
                {alarm.status === "ringing" ? "Остановить сигнал" : "Отменить будильник"}
              </button>
            </li>
          ))}
        </ul>
        <p className="alarm-alert" role="alert" aria-live="assertive">
          {ringing ? "Будильник: время вышло." : ""}
        </p>
        {!state.soundEnabled && (
          <button id="enable-alarm-sound" className="sound-button" onClick={onEnableAudio}>
            Включить звук будильника
          </button>
        )}
      </section>
      <section aria-labelledby="light-title">
        <h3 id="light-title">Свет</h3>
        <p id="light-status">{state.light === "on" ? "Свет включён" : "Свет выключен"}</p>
        <button
          id="example-light"
          className="button"
          disabled={busy}
          onClick={() => onExample(state.light === "on" ? "Выключи свет" : "Включи свет")}
        >
          {state.light === "on" ? "Выключи свет" : "Включи свет"}
        </button>
      </section>
      <section aria-labelledby="datetime-title">
        <h3 id="datetime-title">Дата и время</h3>
        <time id="device-datetime" dateTime={new Date(state.now).toISOString()} aria-live="off">
          {dateAndTime(state.now)}
        </time>
        <button
          id="example-datetime"
          className="button"
          disabled={busy}
          onClick={() => onExample("Какой сегодня день и сколько времени")}
        >
          Какой сегодня день и время?
        </button>
        {state.lastDateTime && <p className="execution-muted">{state.lastDateTime}</p>}
      </section>
      <p className="execution-caption">Для сигнала будильника оставьте страницу открытой.</p>
    </aside>
  );
}
