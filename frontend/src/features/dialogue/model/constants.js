export const HELLO = "Скажите команду. Например: поставь будильник.";
export const ACTIVE_PHASES = new Set(["clarifying", "awaiting_confirmation"]);
export const PHASES = {
  clarifying: "Нужны дополнительные сведения",
  awaiting_confirmation: "Проверьте команду на слух",
  ready: "Команда согласована",
  executed: "Получено подтверждение исполнителя",
  execution_failed: "Исполнитель сообщил об ошибке",
  cancelled: "Команда отменена",
  failed: "Диалог завершён без результата",
};
