import {
  ActivityAnalytics,
  ActivityFilters,
  CommandHistory,
  useActivity,
} from "../../../features/activity/index.js";
import "./activity-dashboard.css";

export function ActivityDashboard() {
  const { filters, users, summary, history, update, refresh, paginate } = useActivity();
  return (
    <div className="history-dashboard">
      <ActivityFilters filters={filters} users={users} onChange={update} onRefresh={refresh} />
      <ActivityAnalytics resource={summary} onUser={(userId) => update({ userId })} />
      <CommandHistory resource={history} offset={filters.offset} onPage={paginate} />
    </div>
  );
}
