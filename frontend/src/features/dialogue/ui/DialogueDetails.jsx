export function DialogueDetails({ state: s }) {
  const d = s.current;
  const payload = d
    ? {
        dialogue_id: d.id,
        user: d.user,
        phase: d.phase,
        intent: d.intent,
        slots: Object.fromEntries(d.slots.map((slot) => [slot.slot, slot.value])),
        ready_for_execution: d.ready_for_execution,
        execution_confirmed: d.execution_confirmed,
        operation_id: d.operation_id,
        execution_message: d.execution_message,
      }
    : null;
  return (
    <>
      <details id="transcript-section" hidden={!s.transcript.length}>
        <summary>Текст диалога</summary>
        <ol id="transcript" aria-label="Реплики диалога">
          {s.transcript.map((line, i) => (
            <li key={i}>
              <strong>{line.who}: </strong>
              {line.text}
            </li>
          ))}
        </ol>
      </details>
      <details id="payload-section" hidden={!d}>
        <summary>Результат для интеграции</summary>
        <pre id="payload">{payload ? JSON.stringify(payload, null, 2) : ""}</pre>
      </details>
    </>
  );
}
