import { Assistant, Help } from "../../../widgets/assistant/index.js";

export function AssistantPage() {
  return (
    <>
      <a className="skip-link" href="#main">
        К диалогу
      </a>
      <header className="app-header">
        <a href="/" className="wordmark">
          MASSIVE<span>.</span> Диалог
        </a>
        <a href="/presentation">О проекте</a>
      </header>
      <main id="main">
        <h1>Уточнение голосовых команд</h1>
        <p className="instruction">Нажмите «Говорить» и скажите, что нужно сделать.</p>
        <p className="demo-note">
          Будильник, свет и дата работают прямо здесь. Скажите команду или выберите пример справа.
        </p>
        <Assistant />
        <Help />
      </main>
      <footer>
        <span>Сервис уточнения для голосовых помощников и умного дома</span>
        <a href="/docs">API</a>
      </footer>
    </>
  );
}
