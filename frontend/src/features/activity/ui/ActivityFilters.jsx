import { useState } from "react";
import { OUTCOMES } from "../model/outcomes.js";

export function ActivityFilters({ filters, users, onChange, onRefresh }) {
  const [search, setSearch] = useState(filters.search);
  return (
    <section className="history-filters" aria-label="Фильтры журнала и аналитики">
      <div className="history-scope">
        <label>
          Пользователь
          <select
            id="history-user"
            value={filters.userId}
            onChange={(e) => onChange({ userId: e.target.value })}
            disabled={users.loading}
          >
            <option value="">Все пользователи</option>
            {(users.data ?? []).map((user) => (
              <option key={user.id} value={user.id}>
                {user.name} · {user.username}
              </option>
            ))}
          </select>
        </label>
        <label>
          Период
          <select
            id="history-period"
            value={filters.days}
            onChange={(e) => onChange({ days: e.target.value })}
          >
            <option value="7">7 дней</option>
            <option value="30">30 дней</option>
            <option value="90">90 дней</option>
            <option value="">Всё время</option>
          </select>
        </label>
        <button className="button" onClick={onRefresh}>
          Обновить данные
        </button>
      </div>
      {users.error && (
        <p className="error" role="alert">
          Не удалось загрузить пользователей: {users.error}
        </p>
      )}
      <form
        className="history-search"
        onSubmit={(e) => {
          e.preventDefault();
          onChange({ search: search.trim() });
        }}
      >
        <label>
          Результат в журнале
          <select
            id="history-outcome"
            value={filters.phase}
            onChange={(e) => onChange({ phase: e.target.value })}
          >
            <option value="">Все результаты</option>
            {Object.entries(OUTCOMES).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="history-search-input">
          Текст команды
          <input
            id="history-search"
            type="search"
            maxLength={300}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Например: будильник"
          />
        </label>
        <button className="button" type="submit">
          Найти
        </button>
      </form>
      <p className="history-caption">
        Пользователь и период применяются ко всей странице. Результат и поиск — только к журналу.
      </p>
    </section>
  );
}
