export async function fetchJson(url, options = {}) {
  let response;
  try {
    response = await fetch(url, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch {
    throw new Error("Не удалось получить ответ сервиса. Проверьте подключение.");
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const error = new Error(data?.error?.message || "Не удалось обработать запрос.");
    error.status = response.status;
    throw error;
  }
  return data;
}
