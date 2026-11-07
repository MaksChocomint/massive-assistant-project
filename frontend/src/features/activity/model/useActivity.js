import { useEffect, useState } from "react";
import { fetchJson } from "../../../shared/api/http.js";
import { activityUrls } from "../api/activity-api.js";

function useResource(url, revision) {
  const [state, setState] = useState({ data: null, loading: true, error: null });
  useEffect(() => {
    let ignore = false;
    const abort = new AbortController();
    setState({ data: null, loading: true, error: null });
    fetchJson(url, { signal: abort.signal }).then(
      (data) => {
        if (!ignore) setState({ data, loading: false, error: null });
      },
      (error) => {
        if (!ignore) setState({ data: null, loading: false, error: error.message });
      },
    );
    return () => {
      ignore = true;
      abort.abort();
    };
  }, [url, revision]);
  return state;
}

export function useActivity() {
  const [filters, setFilters] = useState({
    userId: "",
    days: "30",
    phase: "executed",
    search: "",
    offset: 0,
  });
  const [revision, setRevision] = useState(0);
  const urls = activityUrls(filters);
  const users = useResource("/api/users", revision);
  const summary = useResource(urls.summary, revision);
  const history = useResource(urls.history, revision);
  const update = (values) => setFilters((current) => ({ ...current, ...values, offset: 0 }));
  const refresh = () => {
    update({});
    setRevision((value) => value + 1);
  };
  const paginate = (offset) => setFilters((current) => ({ ...current, offset }));
  return { filters, users, summary, history, update, refresh, paginate };
}
