import { ActivityDashboard } from "../../../widgets/activity/index.js";

export function HistoryPage() {
  return (
    <main id="main">
      <h1 tabIndex="-1">История и аналитика</h1>
      <p className="demo-note">
        Команды пользователей и фактические результаты из базы данных. По умолчанию журнал
        показывает выполненные действия за 30 дней.
      </p>
      <ActivityDashboard />
    </main>
  );
}
