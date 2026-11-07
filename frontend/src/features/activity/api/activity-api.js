export function queryString(values) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(values))
    if (value !== "" && value !== null && value !== undefined) params.set(key, value);
  return params.toString();
}

export function activityUrls(filters) {
  const scope = { user_id: filters.userId, days: filters.days };
  return {
    summary: "/api/analytics/activity?" + queryString(scope),
    history:
      "/api/activity?" +
      queryString({
        ...scope,
        phase: filters.phase,
        search: filters.search,
        limit: 20,
        offset: filters.offset,
      }),
  };
}
