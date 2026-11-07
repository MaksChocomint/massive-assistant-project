import { useEffect, useState } from "react";

const currentPage = () => (window.location.pathname === "/history" ? "history" : "assistant");

export function useNavigation() {
  const [page, setPage] = useState(currentPage);
  useEffect(() => {
    const onPop = () => setPage(currentPage());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);
  const navigate = (event, path) => {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey)
      return;
    event.preventDefault();
    if (window.location.pathname === path) return;
    window.history.pushState(null, "", path);
    setPage(currentPage());
  };
  return { page, navigate };
}
