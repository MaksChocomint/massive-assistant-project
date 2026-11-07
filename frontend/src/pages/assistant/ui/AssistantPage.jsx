import { Assistant, Help } from "../../../widgets/assistant/index.js";

export function AssistantPage({ assistant }) {
  return (
    <>
      <main id="main">
        <h1 tabIndex="-1">Уточнение голосовых команд</h1>
        <Assistant assistant={assistant} />
        <Help />
      </main>
    </>
  );
}
