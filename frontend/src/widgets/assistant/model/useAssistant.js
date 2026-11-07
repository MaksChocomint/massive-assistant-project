import { useEffect, useState, useSyncExternalStore } from "react";
import { AssistantController } from "./assistant-controller.js";

export function useAssistant() {
  const [controller] = useState(() => new AssistantController());
  const state = useSyncExternalStore(controller.subscribe, controller.getSnapshot);
  const execution = useSyncExternalStore(
    controller.executor.subscribe,
    controller.executor.getSnapshot,
  );
  useEffect(() => {
    const disconnect = controller.connect();
    const keydown = (event) => {
      if (event.key === "Escape") controller.pauseVoice();
      if (event.altKey && !event.ctrlKey && !event.metaKey) {
        if (event.code === "KeyM") {
          event.preventDefault();
          controller.startVoice();
        }
        if (event.code === "KeyR") {
          event.preventDefault();
          controller.repeat();
        }
      }
    };
    const pagehide = () => {
      controller.stopPolling();
      controller.pauseVoice();
      controller.executor.disconnect();
    };
    window.addEventListener("keydown", keydown);
    window.addEventListener("pagehide", pagehide);
    return () => {
      window.removeEventListener("keydown", keydown);
      window.removeEventListener("pagehide", pagehide);
      disconnect();
    };
  }, [controller]);
  return { state, execution, controller };
}
