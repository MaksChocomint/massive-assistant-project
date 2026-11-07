export const HELLO = "Слушаю.";
export const ACTIVE_PHASES = new Set(["clarifying", "awaiting_confirmation"]);
export const PHASES = {
  clarifying: "Уточнение",
  awaiting_confirmation: "Подтверждение",
  ready: "Ожидание выполнения",
  executed: "Выполнено",
  execution_failed: "Ошибка исполнения",
  cancelled: "Отменено",
  failed: "Не завершено",
};
