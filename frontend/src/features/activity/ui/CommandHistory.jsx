import { OUTCOMES } from "../model/outcomes.js";

const timestamp = (value) =>
  new Intl.DateTimeFormat("ru-RU", { dateStyle: "short", timeStyle: "medium" }).format(
    new Date(value),
  );

export function CommandHistory({ resource, offset, onPage }) {
  const { data, error, loading } = resource;
  return (
    <section className="history-card" aria-labelledby="command-history-title" aria-busy={loading}>
      <h2 id="command-history-title">Журнал команд</h2>
      <p className="history-caption">
        Выполнено — получена успешная квитанция. Время показано в часовом поясе вашего устройства.
      </p>
      {loading && <p role="status">Загружаю команды…</p>}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {data && (
        <>
          <p className="history-result-count" role="status">
            Найдено команд: {data.total}
          </p>
          {data.items.length ? (
            <div
              className="history-table-scroll"
              tabIndex="0"
              role="region"
              aria-label="Таблица команд, можно прокручивать"
            >
              <table className="history-table">
                <thead>
                  <tr>
                    <th scope="col">Создана / пользователь</th>
                    <th scope="col">Команда</th>
                    <th scope="col">Результат</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((item) => (
                    <tr key={item.id} data-command-id={item.id}>
                      <td>
                        <time dateTime={item.created_at}>{timestamp(item.created_at)}</time>
                        <strong>{item.user.name}</strong>
                        <span className="history-caption">@{item.user.username}</span>
                      </td>
                      <td>
                        <strong>{item.text}</strong>
                        <span className="history-caption">{item.intent_name}</span>
                        {item.slots.length > 0 && (
                          <ul className="history-slots">
                            {item.slots.map((slot) => (
                              <li key={slot.slot}>
                                {slot.name}: {slot.value}
                              </li>
                            ))}
                          </ul>
                        )}
                        <details className="history-technical">
                          <summary>Подробности #{item.id}</summary>
                          <dl>
                            <dt>Намерение</dt>
                            <dd>{item.intent}</dd>
                            <dt>Уверенность модели</dt>
                            <dd>{Math.round(item.confidence * 100)}%</dd>
                            <dt>Уточнений</dt>
                            <dd>{item.clarifications}</dd>
                            <dt>Статус параметров</dt>
                            <dd>{item.command_status}</dd>
                            <dt>Квитанция</dt>
                            <dd>{item.operation_id || "Нет"}</dd>
                            {item.execution_recorded_at && (
                              <>
                                <dt>Результат записан</dt>
                                <dd>{timestamp(item.execution_recorded_at)}</dd>
                              </>
                            )}
                          </dl>
                        </details>
                      </td>
                      <td>
                        <span className={"outcome-badge outcome-" + item.phase}>
                          {OUTCOMES[item.phase]}
                        </span>
                        {item.execution_message && (
                          <p className="history-execution-message">{item.execution_message}</p>
                        )}
                        {item.phase === "legacy" && (
                          <p className="history-caption">
                            Статус completed означает собранные параметры, а не выполнение.
                          </p>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="history-empty">
              По этим фильтрам команд нет. Выберите другой результат, пользователя или период.
            </p>
          )}
          <div className="history-pagination">
            <button
              className="button"
              disabled={loading || offset === 0}
              onClick={() => onPage(Math.max(0, offset - data.limit))}
            >
              Назад
            </button>
            <span>
              {data.total ? Math.min(offset + 1, data.total) : 0}–
              {Math.min(offset + data.items.length, data.total)} из {data.total}
            </span>
            <button
              className="button"
              disabled={loading || offset + data.limit >= data.total}
              onClick={() => onPage(offset + data.limit)}
            >
              Далее
            </button>
          </div>
        </>
      )}
    </section>
  );
}
