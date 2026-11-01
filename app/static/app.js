"use strict";
// Голосовой клиент микросервиса. Микрофон запускается только действием пользователя.
const $ = id => document.getElementById(id);
const NativeRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
const Recognition = NativeRecognition || (
  window.LocalSpeechRecognition?.supported() ? window.LocalSpeechRecognition : null
);
const canSpeak = typeof window.speechSynthesis?.speak === "function"
  && typeof window.SpeechSynthesisUtterance === "function";
const ACTIVE_PHASES = new Set(["clarifying","awaiting_confirmation"]);
const PHASES = {
  clarifying:"Нужны дополнительные сведения",
  awaiting_confirmation:"Проверьте команду на слух",
  ready:"Команда подготовлена. Исполнение не подтверждено",
  executed:"Получено подтверждение исполнителя",
  execution_failed:"Исполнитель сообщил об ошибке",
  cancelled:"Команда отменена",
  failed:"Диалог завершён без результата",
};
let current = null;
let busy = false;
let voiceActive = false;
let listening = false;
let speaking = false;
let paused = false;
let recognition = null;
let recognitionEpoch = 0;
let speechEpoch = 0;
let noSpeechCount = 0;
let lastMessage = $("assistant-text").textContent;
let pollTimer = null;
let pollCount = 0;
let pollErrors = 0;
let pollInFlight = false;
let speechRate = 1;

function setSpeechRate(value) {
  const rate = Number(value);
  speechRate = Number.isFinite(rate) && rate >= 0.5 && rate <= 2
    ? Math.round(rate * 10) / 10 : 1;
  const formatted = speechRate.toLocaleString("ru-RU",{maximumFractionDigits:1});
  $("speech-rate").value = String(speechRate);
  $("speech-rate").setAttribute("aria-valuetext",formatted + " от обычной скорости");
  $("speech-rate-value").textContent = formatted + "×";
}

function clean(text) {
  return text.toLowerCase().replace(/ё/g,"е").replace(/[.,!?]/g,"").replace(/\s+/g," ").trim();
}
function voiceState(text) { $("voice-state").textContent = text; }
function controls() {
  $("voice-button").setAttribute("aria-pressed",String(voiceActive));
  $("voice-button").querySelector("span").textContent = voiceActive ? "Пауза" : "Говорить";
  const pending = current?.phase === "ready";
  $("voice-button").disabled = !Recognition || (busy && !voiceActive) || (pending && !voiceActive);
  $("send-button").disabled = busy || pending;
  $("message").readOnly = busy || pending;
  $("cancel-button").disabled = busy || !current || !ACTIVE_PHASES.has(current.phase);
  $("new-button").hidden = !current || ACTIVE_PHASES.has(current.phase);
  $("new-button").disabled = busy;
  $("repeat-button").disabled = !canSpeak;
  const answering = current && ACTIVE_PHASES.has(current.phase);
  $("message-label").textContent = answering ? "Ваш ответ" : "Ваша команда";
  $("message").placeholder = answering
    ? current.phase === "awaiting_confirmation" ? "Да или нет" : "Ответ на вопрос помощника"
    : "Например: поставь будильник";
  $("message").maxLength = answering ? 200 : 300;
}
function log(who,text) {
  const li = document.createElement("li");
  const label = document.createElement("strong");
  label.textContent = who + ": ";
  li.append(label,document.createTextNode(text));
  $("transcript").appendChild(li);
  $("transcript-section").hidden = false;
}
function live(text) {
  $("screenreader-message").setAttribute("aria-live",$("audio-enabled").checked && canSpeak && !paused ? "off" : "polite");
  $("screenreader-message").textContent = text;
}
function showError(message) {
  $("error").textContent = message;
  $("error").hidden = false;
  $("error").setAttribute("aria-live",$("audio-enabled").checked && canSpeak && !paused ? "off" : "assertive");
}
async function api(path,options={}) {
  let response;
  try {
    response = await fetch("/api/dialogues"+path,{
      headers:{"Content-Type":"application/json"},...options,
    });
  } catch {
    throw new Error("Нет связи с микросервисом. Команда не подтверждена. Проверьте подключение.");
  }
  const data = await response.json().catch(()=>null);
  if(!response.ok) {
    const error = new Error(data?.error?.message || "Не удалось обработать запрос.");
    error.status = response.status;
    throw error;
  }
  return data;
}
function stopRecognition() {
  recognitionEpoch++;
  if(recognition) {
    const previous=recognition;
    recognition=null;
    previous.onstart=previous.onresult=previous.onerror=previous.onend=previous.onaudioend=null;
    try { previous.abort(); } catch {}
  }
  listening=false;
}
function stopSpeech() {
  speechEpoch++;
  speaking=false;
  if(canSpeak) window.speechSynthesis.cancel();
}
function pauseVoice() {
  voiceActive=false;
  paused=true;
  stopRecognition();
  stopSpeech();
  voiceState("Пауза. Микрофон выключен, команда сохранена.");
  $("voice-state").setAttribute("aria-live","polite");
  controls();
}
function speak(text,resume=false) {
  stopRecognition();
  stopSpeech();
  live(text);
  if(!$("audio-enabled").checked || !canSpeak || paused) {
    voiceActive=false;
    voiceState("Микрофон выключен. Ответ доступен на странице и экранному диктору.");
    controls();
    return;
  }
  const epoch=++speechEpoch;
  const utterance=new SpeechSynthesisUtterance(text);
  utterance.lang="ru-RU";
  utterance.rate=speechRate;
  const voices=window.speechSynthesis.getVoices().filter(v=>/^ru/i.test(v.lang));
  utterance.voice=voices.find(v=>v.localService) || voices[0] || null;
  speaking=true;
  voiceState("Помощник говорит");
  $("voice-state").setAttribute("aria-live","off");
  utterance.onend=()=>{
    if(epoch!==speechEpoch)return;
    speaking=false;
    if(resume && voiceActive && (!current || ACTIVE_PHASES.has(current.phase))) {
      voiceState("Приготовьтесь ответить");
      setTimeout(()=>{if(epoch===speechEpoch)startListening();},250);
    } else {
      voiceActive=false;
      voiceState("Микрофон выключен");
      controls();
    }
  };
  utterance.onerror=()=>{
    if(epoch!==speechEpoch)return;
    speaking=false;
    voiceActive=false;
    paused=true;
    $("screenreader-message").setAttribute("aria-live","polite");
    $("screenreader-message").textContent=text;
    voiceState("Озвучивание недоступно. Ответ передан экранному диктору.");
    controls();
  };
  window.speechSynthesis.speak(utterance);
  controls();
}
function recognitionFailure(code) {
  stopRecognition();
  if(code==="aborted")return;
  const errors={
    "not-allowed":"Браузер не разрешил доступ к микрофону. Разрешите его в настройках сайта или введите команду текстом.",
    "service-not-allowed":"Сервис распознавания речи пока недоступен. Попробуйте позже или введите команду текстом.",
    "audio-capture":"Микрофон не найден или занят другой программой. Проверьте его подключение.",
    "network":"Нет связи с сервисом распознавания речи. Можно ввести команду текстом.",
    "language-not-supported":"Распознавание русской речи недоступно в этом браузере.",
  };
  if(errors[code]) {
    voiceActive=false;
    $("text-entry").open=true;
    showError(errors[code]);
    lastMessage=errors[code];
    speak(lastMessage,false);
    controls();
    return;
  }
  noSpeechCount++;
  const retry=voiceActive && noSpeechCount<3;
  const message=retry
    ? "Я не расслышал. После окончания сообщения повторите фразу."
    : "Не удалось расслышать фразу. Микрофон выключен. Нажмите «Говорить» для новой попытки или введите текст.";
  if(!retry)voiceActive=false;
  lastMessage=message;
  showError(message);
  speak(message,retry);
}
function startListening() {
  if(!voiceActive || busy || speaking || recognition || !Recognition)return;
  const epoch=++recognitionEpoch;
  const instance=new Recognition();
  recognition=instance;
  instance.lang="ru-RU";
  instance.continuous=false;
  instance.interimResults=false;
  instance.maxAlternatives=1;
  instance.onstart=()=>{
    if(epoch!==recognitionEpoch)return;
    listening=true;
    voiceState("Слушаю. Скажите команду или ответ.");
    controls();
  };
  instance.onresult=event=>{
    if(epoch!==recognitionEpoch)return;
    const result=event.results[event.resultIndex ?? 0];
    const text=result?.[0]?.transcript?.trim();
    stopRecognition();
    if(!text) { recognitionFailure("no-speech"); return; }
    noSpeechCount=0;
    handleText(text);
  };
  instance.onerror=event=>{if(epoch===recognitionEpoch)recognitionFailure(event.error);};
  instance.onaudioend=()=>{
    if(epoch===recognitionEpoch)voiceState("Распознаю запись…");
  };
  instance.onend=()=>{
    if(epoch!==recognitionEpoch)return;
    stopRecognition();
    if(voiceActive && !busy && !speaking)recognitionFailure("no-speech");
  };
  try { instance.start(); }
  catch { recognitionFailure("audio-capture"); }
}
function startVoice() {
  if(!Recognition)return;
  if(voiceActive) { pauseVoice(); return; }
  if(busy || current?.phase === "ready")return;
  paused=false;
  voiceActive=true;
  noSpeechCount=0;
  if(canSpeak)$("audio-enabled").checked=true;
  $("error").hidden=true;
  const prompt=current && ACTIVE_PHASES.has(current.phase)
    ? current.spoken_text
    : "Это демонстрация микросервиса: реальные устройства не подключены. Скажите команду. Например: поставь будильник.";
  speak(prompt,true);
  if(!canSpeak) {
    voiceActive=true;
    startListening();
  }
  controls();
}
function stopPolling() {
  if(pollTimer)clearInterval(pollTimer);
  pollTimer=null;
}
function render(data,{prefix="",readAloud=true}={}) {
  current=data;
  try { localStorage.setItem("massive.dialogue",String(data.id)); } catch {}
  $("phase-label").hidden=false;
  $("phase-label").textContent=PHASES[data.phase];
  lastMessage=prefix ? prefix+" "+data.spoken_text : data.spoken_text;
  $("assistant-text").textContent=lastMessage;
  $("payload-section").hidden=false;
  $("payload").textContent=JSON.stringify({
    dialogue_id:data.id,phase:data.phase,intent:data.intent,
    slots:Object.fromEntries(data.slots.map(s=>[s.slot,s.value])),
    ready_for_execution:data.ready_for_execution,
    execution_confirmed:data.execution_confirmed,
    operation_id:data.operation_id,execution_message:data.execution_message,
  },null,2);
  if(readAloud) {
    log("Помощник",lastMessage);
    speak(lastMessage,voiceActive && ACTIVE_PHASES.has(data.phase));
  } else live(lastMessage);
  if(data.phase==="ready")startPolling();
  else stopPolling();
  controls();
}
function startPolling() {
  if(pollTimer)return;
  pollCount=0;
  pollErrors=0;
  pollTimer=setInterval(async()=>{
    if(pollInFlight || !current || current.phase!=="ready")return;
    pollInFlight=true;
    const id=current.id;
    try {
      const data=await api("/"+id);
      pollErrors=0;
      if(!current || current.id!==id)return;
      if(data.phase!=="ready") {
        stopPolling();
        render(data);
      } else if(++pollCount>=60) {
        stopPolling();
        const message="Подтверждение исполнения пока не получено. Действие нельзя считать выполненным. Кнопка «Повторить вслух» проверит состояние ещё раз.";
        lastMessage=message;
        $("assistant-text").textContent=message;
        log("Помощник",message);
        speak(message,false);
      }
    } catch(error) {
      if(++pollErrors>=3) {
        stopPolling();
        showError(error.message);
        speak(error.message,false);
      }
    } finally { pollInFlight=false; }
  },3000);
}
async function handleText(text) {
  if(busy)return;
  text=text.trim();
  if(!text)return;
  const control=clean(text);
  if(["повтори","повтори вопрос","повтори сообщение"].includes(control)) { await repeat(); return; }
  if(["стоп","пауза"].includes(control)) { pauseVoice(); return; }
  if(["отмена","отмени","отмени команду","отменить"].includes(control) && current) { await cancelCurrent(); return; }
  if(current?.phase === "ready")return;
  stopRecognition();
  paused=false;
  busy=true;
  $("error").hidden=true;
  voiceState("Обрабатываю запрос");
  controls();
  log("Вы",text);
  try {
    const answering=current && ACTIVE_PHASES.has(current.phase);
    const data=await api(answering ? "/"+current.id+"/answer" : "",{
      method:"POST",body:JSON.stringify(answering ? {answer:text} : {text}),
    });
    busy=false;
    $("message").value="";
    render(data);
  } catch(error) {
    busy=false;
    showError(error.message);
    if(current) {
      try { render(await api("/"+current.id),{prefix:error.message}); }
      catch { lastMessage=error.message; $("assistant-text").textContent=lastMessage; speak(lastMessage,false); }
    } else {
      lastMessage=error.message;
      $("assistant-text").textContent=lastMessage;
      speak(lastMessage,voiceActive);
    }
  } finally { busy=false; controls(); }
}
async function cancelCurrent() {
  if(busy || !current || !ACTIVE_PHASES.has(current.phase))return;
  stopRecognition();
  stopSpeech();
  busy=true;
  voiceActive=false;
  controls();
  try {
    const data=await api("/"+current.id+"/cancel",{method:"POST"});
    busy=false;
    render(data);
  } catch(error) { showError(error.message); speak(error.message,false); }
  finally { busy=false; controls(); }
}
async function repeat() {
  if(busy)return;
  paused=false;
  if(canSpeak)$("audio-enabled").checked=true;
  if(current) {
    try { render(await api("/"+current.id)); }
    catch(error) { showError(error.message); speak(lastMessage,false); }
  } else speak(lastMessage,voiceActive);
}
function reset() {
  if(busy)return;
  const previousPending=current?.phase === "ready";
  stopPolling();
  stopRecognition();
  stopSpeech();
  current=null;
  voiceActive=false;
  paused=false;
  try { localStorage.removeItem("massive.dialogue"); } catch {}
  $("transcript").replaceChildren();
  $("transcript-section").hidden=true;
  $("payload-section").hidden=true;
  $("phase-label").hidden=true;
  $("error").hidden=true;
  lastMessage=(previousPending ? "Выполнение предыдущей команды не подтверждено. " : "")
    + "Новый диалог. Нажмите «Говорить» и скажите команду.";
  $("assistant-text").textContent=lastMessage;
  voiceState("Микрофон выключен");
  speak(lastMessage,false);
  controls();
}
$("voice-button").onclick=startVoice;
$("repeat-button").onclick=repeat;
$("cancel-button").onclick=cancelCurrent;
$("new-button").onclick=reset;
$("audio-enabled").onchange=()=>{
  if(!$("audio-enabled").checked) {
    pauseVoice();
    live(lastMessage);
  } else paused=false;
};
$("speech-rate").oninput=event=>{
  setSpeechRate(event.target.value);
  try { localStorage.setItem("massive.speechRate",String(speechRate)); } catch {}
};
$("text-form").onsubmit=event=>{
  event.preventDefault();
  handleText($("message").value);
};
document.addEventListener("keydown",event=>{
  if(event.key==="Escape")pauseVoice();
  if(event.altKey && !event.ctrlKey && !event.metaKey) {
    if(event.code==="KeyM") { event.preventDefault(); startVoice(); }
    if(event.code==="KeyR") { event.preventDefault(); repeat(); }
  }
});
window.addEventListener("pagehide",()=>{stopPolling();stopRecognition();stopSpeech();});
async function restore() {
  if(Recognition && !NativeRecognition) {
    $("voice-support").classList.add("info");
    $("voice-support").hidden=false;
    $("voice-support").textContent="После фразы сделайте паузу — помощник распознает запись и ответит.";
  }
  if(!Recognition) {
    $("voice-support").hidden=false;
    $("voice-support").textContent="Голосовой ввод в этом браузере недоступен. Можно ввести команду текстом.";
    $("text-entry").open=true;
  }
  if(!canSpeak) {
    $("audio-enabled").disabled=true;
    $("speech-rate").disabled=true;
    $("voice-support").hidden=false;
    $("voice-support").textContent=($("voice-support").textContent+" Озвучивание браузером недоступно. Используйте экранный диктор.").trim();
  }
  controls();
  let id;
  try { id=localStorage.getItem("massive.dialogue"); } catch {}
  if(!id || !/^\d+$/.test(id))return;
  try {
    const data=await api("/"+id);
    log("Вы",data.text);
    render(data,{readAloud:false});
    voiceState("Диалог восстановлен. Микрофон выключен.");
  } catch {
    try { localStorage.removeItem("massive.dialogue"); } catch {}
  }
}
try { setSpeechRate(localStorage.getItem("massive.speechRate") ?? 1); }
catch { setSpeechRate(1); }
restore();
