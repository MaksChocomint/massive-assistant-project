import { Assistant, Help } from "../../../widgets/assistant/index.js";

export function AssistantPage({ assistant }) {
  return (
    <>
      <main id="main">
        <h1 tabIndex="-1">Уточнение голосовых команд</h1>
        <p className="instruction">Нажмите «Говорить» и скажите, что нужно сделать.</p>
        <p className="demo-note">
          Будильник, свет и дата работают прямо здесь. Скажите команду или выберите пример справа.
        </p>
        <Assistant assistant={assistant} />
        <Help />
      </main>
    </>
  );
}
