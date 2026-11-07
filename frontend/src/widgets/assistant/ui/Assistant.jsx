import { VoiceControls } from "../../../features/voice/index.js";
import {
  DialogueMessage,
  DialogueActions,
  TextEntry,
  DialogueDetails,
} from "../../../features/dialogue/index.js";
import { useAssistant } from "../model/useAssistant.js";

export function Assistant() {
  const { state: s, controller: c } = useAssistant();
  const ownSpeech = s.audioEnabled && c.canSpeak && !s.paused;
  const pending = s.current?.phase === "ready";
  return (
    <section className="dialogue" aria-label="Голосовой диалог">
      <VoiceControls
        voice={s}
        available={Boolean(c.Recognition)}
        canSpeak={c.canSpeak}
        blocked={(s.busy && !s.voiceActive) || (pending && !s.voiceActive)}
        onToggle={c.startVoice}
        onAudioEnabled={c.setAudioEnabled}
        onSpeechRate={c.setSpeechRate}
      />
      <DialogueMessage state={s} ownSpeech={ownSpeech} />
      <DialogueActions
        current={s.current}
        busy={s.busy}
        canSpeak={c.canSpeak}
        onRepeat={c.repeat}
        onCancel={c.cancel}
        onNew={c.startNewCommand}
      />
      <TextEntry state={s} onInput={c.setInput} onSubmit={c.send} onOpen={c.setTextEntryOpen} />
      <DialogueDetails state={s} />
    </section>
  );
}
