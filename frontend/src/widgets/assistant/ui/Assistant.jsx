import { ExecutionPanel } from "../../../features/browser-executor/index.js";
import { VoiceControls } from "../../../features/voice/index.js";
import {
  DialogueMessage,
  DialogueActions,
  TextEntry,
  DialogueDetails,
} from "../../../features/dialogue/index.js";

export function Assistant({ assistant }) {
  const { state, execution, controller: c } = assistant;
  const s = { ...state, busy: state.busy || state.executing };
  const ownSpeech = s.audioEnabled && c.canSpeak && !s.paused;
  const pending = s.current?.phase === "ready";
  return (
    <div className="assistant-workspace">
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
      <ExecutionPanel
        state={execution}
        busy={s.busy}
        onExample={c.runExample}
        onDismiss={c.executor.dismissAlarm}
        onEnableAudio={c.executor.enableAudio}
      />
    </div>
  );
}
