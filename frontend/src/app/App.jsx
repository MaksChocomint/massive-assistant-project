import { useEffect } from "react";
import { AssistantPage } from "../pages/assistant/index.js";
import { HistoryPage } from "../pages/history/index.js";
import { useAssistant } from "../widgets/assistant/index.js";
import { AlarmNotice } from "../features/browser-executor/index.js";
import { useNavigation } from "./model/useNavigation.js";

export default function App() {
  const { page, navigate } = useNavigation();
  const assistant = useAssistant({ voiceShortcuts: page === "assistant" });
  useEffect(() => {
    document.title =
      page === "history" ? "История и аналитика — MASSIVE" : "MASSIVE — уточнение голосовых команд";
    if (page === "history") assistant.controller.pauseVoice();
    document.querySelector("main h1")?.focus({ preventScroll: true });
  }, [page, assistant.controller]);
  return (
    <>
      <a className="skip-link" href="#main">
        К содержимому
      </a>
      <header className="app-header">
        <a href="/" onClick={(event) => navigate(event, "/")} className="wordmark">
          MASSIVE<span>.</span> Диалог
        </a>
        <nav className="app-navigation" aria-label="Основное меню">
          <a
            href="/"
            onClick={(event) => navigate(event, "/")}
            aria-current={page === "assistant" ? "page" : undefined}
          >
            Помощник
          </a>
          <a
            href="/history"
            onClick={(event) => navigate(event, "/history")}
            aria-current={page === "history" ? "page" : undefined}
          >
            История и аналитика
          </a>
        </nav>
      </header>
      {page === "history" ? (
        <>
          <AlarmNotice
            state={assistant.execution}
            onDismiss={assistant.controller.executor.dismissAlarm}
            onEnableAudio={assistant.controller.executor.enableAudio}
          />
          <HistoryPage />
        </>
      ) : (
        <AssistantPage assistant={assistant} />
      )}
      <footer>
        <span>Сервис уточнения для голосовых помощников и умного дома</span>
        <a href="/docs">API</a>
      </footer>
    </>
  );
}
