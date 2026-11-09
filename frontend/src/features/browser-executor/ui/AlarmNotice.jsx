export function AlarmNotice({ state, onDismiss, onEnableAudio }) {
  const ringing = state.alarms.filter((alarm) => alarm.status === "ringing");
  const needsAudio = state.alarms.length > 0 && !state.soundEnabled;
  if (!ringing.length && !needsAudio) return null;
  return (
    <div className="alarm-notice" role={ringing.length ? "alert" : "region"} aria-label="Будильник">
      <strong>
        {ringing.length
          ? "Будильник. Время вышло."
          : "Будильник сохранён. Включите звук после перезагрузки."}
      </strong>
      {needsAudio && (
        <button className="button" onClick={onEnableAudio}>
          Включить звук будильника
        </button>
      )}
      {ringing.map((alarm) => (
        <button className="button" key={alarm.id} onClick={() => onDismiss(alarm.id)}>
          Остановить сигнал
        </button>
      ))}
    </div>
  );
}
