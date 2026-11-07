import { OUTCOMES } from "../model/outcomes.js";

export function ActivityAnalytics({ resource, onUser }) {
  const { data, error, loading } = resource;
  if (loading) return <p role="status">Загружаю сводку…</p>;
  if (error)
    return (
      <p className="error" role="alert">
        {error}
      </p>
    );
  if (!data) return null;
  const phases = data.by_phase;
  const waiting =
    (phases.ready || 0) + (phases.clarifying || 0) + (phases.awaiting_confirmation || 0);
  return (
    <section aria-labelledby="activity-summary-title">
      <h2 id="activity-summary-title">Сводка выбранного периода</h2>
      <div className="history-statistics">
        <Stat label="Всего команд" value={data.total} />
        <Stat label="Выполнено" value={phases.executed || 0} />
        <Stat label="В процессе" value={waiting} />
        <Stat
          label="Успех исполнения"
          value={
            data.execution_success_rate === null
              ? "—"
              : Math.round(data.execution_success_rate * 100) + "%"
          }
          hint="Среди полученных квитанций"
        />
      </div>
      <p className="history-caption">
        Среднее число уточнений: {data.avg_clarifications}. Нет квитанций — доля успеха не
        вычисляется.
      </p>
      <ul className="history-phase-counts">
        {Object.entries(phases).map(([phase, n]) => (
          <li key={phase}>
            {OUTCOMES[phase]}: <strong>{n}</strong>
          </li>
        ))}
      </ul>
      <div className="history-analytics-grid">
        <section className="history-card" aria-labelledby="popular-title">
          <h3 id="popular-title">Самые частые команды</h3>
          <p className="history-caption">
            По намерению, включая незавершённые команды. Рядом — число выполненных.
          </p>
          {!data.top_intents.length && <p className="history-empty">Пока нет команд.</p>}
          <ol className="history-ranking">
            {data.top_intents.map((item) => (
              <li key={item.intent}>
                <div>
                  <span>{item.name}</span>
                  <strong>{item.commands}</strong>
                </div>
                <div className="history-rank-track" aria-hidden="true">
                  <span
                    style={{ width: (100 * item.commands) / data.top_intents[0].commands + "%" }}
                  />
                </div>
                <small>Выполнено: {item.executed}</small>
              </li>
            ))}
          </ol>
        </section>
        <section className="history-card" aria-labelledby="users-title">
          <h3 id="users-title">Активность пользователей</h3>
          <p className="history-caption">Нажмите на имя, чтобы отфильтровать страницу.</p>
          {!data.by_user.length ? (
            <p className="history-empty">Пока нет команд.</p>
          ) : (
            <div className="history-table-scroll">
              <table className="history-table history-users">
                <thead>
                  <tr>
                    <th scope="col">Пользователь</th>
                    <th scope="col">Всего</th>
                    <th scope="col">Выполнено</th>
                  </tr>
                </thead>
                <tbody>
                  {data.by_user.map((user) => (
                    <tr key={user.user_id}>
                      <td>
                        <button
                          className="history-user-link"
                          onClick={() => onUser(String(user.user_id))}
                        >
                          {user.name}
                        </button>
                        <small>@{user.username}</small>
                      </td>
                      <td>{user.commands}</td>
                      <td>{user.executed}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
      <details className="history-daily">
        <summary>Команды по дням (UTC)</summary>
        {!data.by_day.length ? (
          <p>Пока нет команд.</p>
        ) : (
          <table className="history-table">
            <thead>
              <tr>
                <th scope="col">День</th>
                <th scope="col">Команд</th>
                <th scope="col">Выполнено</th>
              </tr>
            </thead>
            <tbody>
              {data.by_day.map((day) => (
                <tr key={day.day}>
                  <td>{day.day}</td>
                  <td>{day.commands}</td>
                  <td>{day.executed}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </details>
    </section>
  );
}

function Stat({ label, value, hint }) {
  return (
    <div className="history-stat">
      <span>{label}</span>
      <strong>{value}</strong>
      {hint && <small>{hint}</small>}
    </div>
  );
}
