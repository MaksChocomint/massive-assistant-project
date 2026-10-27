// Простой клиент: обычный fetch к нашему API, без фреймворков.

const STATUS = {
  needs_clarification: "Ждёт уточнения",
  completed: "Выполнена",
  cancelled: "Отменена",
  failed: "Не удалась",
};
const PAGE = 10;
const $ = (id) => document.getElementById(id);

// --- запросы и ошибки --------------------------------------------------------

async function api(path, options = {}) {
  const response = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (response.status === 204) return null;
  const body = await response.json();
  if (!response.ok) {
    const error = body.error || {};
    const details = (error.details || []).map((d) => `${d.field}: ${d.message}`).join("; ");
    throw new Error(details ? `${error.message} (${details})` : error.message || "Ошибка");
  }
  return body;
}

function showError(error) {
  $("error").textContent = error.message;
  $("error").hidden = false;
}

function clearError() {
  $("error").hidden = true;
}

function escape(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function pager(element, page, total, onPage) {
  const pages = Math.max(1, Math.ceil(total / PAGE));
  element.innerHTML = `
    <button class="button" ${page === 0 ? "disabled" : ""}>←</button>
    <span>Страница ${page + 1} из ${pages} · всего ${total}</span>
    <button class="button" ${page + 1 >= pages ? "disabled" : ""}>→</button>`;
  const [prev, next] = element.querySelectorAll("button");
  prev.onclick = () => onPage(page - 1);
  next.onclick = () => onPage(page + 1);
}

// --- вкладки ------------------------------------------------------------------

document.querySelectorAll(".tab").forEach((tab) => {
  tab.onclick = () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t === tab));
    document.querySelectorAll(".page").forEach((p) => (p.hidden = p.id !== tab.dataset.tab));
    clearError();
    if (tab.dataset.tab === "commands") loadCommands();
    if (tab.dataset.tab === "intents") loadIntents();
    if (tab.dataset.tab === "analytics") loadAnalytics();
  };
});

// --- команды ------------------------------------------------------------------

let commandPage = 0;

async function loadUsers() {
  const users = await api("/users");
  $("command-user").innerHTML = users
    .map((u) => `<option value="${u.id}">${escape(u.name)} (${escape(u.username)})</option>`)
    .join("");
}

function slotsText(command) {
  return command.slots.map((s) => `${s.name}: ${s.value}`).join(", ") || "—";
}

function renderResult(command) {
  const box = $("command-result");
  let actions = "";
  if (command.status === "needs_clarification") {
    actions = `
      <p class="question">${escape(command.question)}</p>
      <div class="row">
        <input id="answer" placeholder="Ваш ответ" />
        <button type="button" class="button primary" id="answer-send">Ответить</button>
        <button type="button" class="button" id="command-cancel">Отменить</button>
      </div>`;
  }
  box.innerHTML = `
    <div class="result status-${command.status}">
      <div class="row between">
        <strong>${escape(command.intent_name)}</strong>
        <span class="badge">${STATUS[command.status]}</span>
      </div>
      <div class="muted">уверенность ${Math.round(command.confidence * 100)}% ·
        уточнений ${command.clarifications}</div>
      <div>Параметры: ${escape(slotsText(command))}</div>
      ${actions}
    </div>`;
  if (command.status === "needs_clarification") {
    $("answer").focus();
    $("answer-send").onclick = () => clarify(command.id);
    $("answer").onkeydown = (e) => e.key === "Enter" && (e.preventDefault(), clarify(command.id));
    $("command-cancel").onclick = () => cancel(command.id);
  }
}

async function clarify(id) {
  clearError();
  try {
    const answer = $("answer").value;
    renderResult(await api(`/commands/${id}/clarify`, { method: "POST", body: JSON.stringify({ answer }) }));
  } catch (error) {
    showError(error);
    renderResult(await api(`/commands/${id}`)); // число попыток могло измениться
  }
  loadCommands();
}

async function cancel(id) {
  clearError();
  try {
    renderResult(await api(`/commands/${id}/cancel`, { method: "POST" }));
  } catch (error) {
    showError(error);
  }
  loadCommands();
}

$("command-form").onsubmit = async (event) => {
  event.preventDefault();
  clearError();
  try {
    const body = { user_id: Number($("command-user").value), text: $("command-text").value };
    renderResult(await api("/commands", { method: "POST", body: JSON.stringify(body) }));
    $("command-text").value = "";
    commandPage = 0;
    loadCommands();
  } catch (error) {
    showError(error);
  }
};

$("user-form").onsubmit = async (event) => {
  event.preventDefault();
  clearError();
  try {
    const body = { username: $("user-username").value, name: $("user-name").value };
    await api("/users", { method: "POST", body: JSON.stringify(body) });
    $("user-form").reset();
    await loadUsers();
  } catch (error) {
    showError(error);
  }
};

async function loadCommands() {
  try {
    const status = $("command-status").value;
    const query = new URLSearchParams({ limit: PAGE, offset: commandPage * PAGE });
    if (status) query.set("status", status);
    const page = await api(`/commands?${query}`);
    $("command-rows").innerHTML =
      page.items
        .map(
          (c) => `<tr>
            <td>${c.id}</td><td>${escape(c.text)}</td><td>${escape(c.intent_name)}</td>
            <td>${escape(slotsText(c))}</td>
            <td><span class="badge status-${c.status}">${STATUS[c.status]}</span></td></tr>`,
        )
        .join("") || `<tr><td colspan="5" class="muted">Команд пока нет</td></tr>`;
    pager($("command-pager"), commandPage, page.total, (p) => ((commandPage = p), loadCommands()));
  } catch (error) {
    showError(error);
  }
}

$("command-status").onchange = () => ((commandPage = 0), loadCommands());

// --- намерения ----------------------------------------------------------------

let intentPage = 0;

async function loadScenarios() {
  const scenarios = await api("/scenarios");
  const options = scenarios.map((s) => `<option value="${s.id}">${escape(s.name)}</option>`).join("");
  $("intent-scenario").innerHTML = `<option value="">Все сценарии</option>${options}`;
  $("intent-scenario-id").innerHTML = options;
}

async function loadIntents() {
  try {
    const query = new URLSearchParams({
      limit: PAGE,
      offset: intentPage * PAGE,
      sort: $("intent-sort").value,
    });
    if ($("intent-search").value) query.set("search", $("intent-search").value);
    if ($("intent-scenario").value) query.set("scenario_id", $("intent-scenario").value);
    const page = await api(`/intents?${query}`);
    $("intent-rows").innerHTML = page.items
      .map(
        (i) => `<tr>
          <td><code>${escape(i.code)}</code></td><td>${escape(i.name)}</td><td>${i.utterances}</td>
          <td>${i.is_active ? "да" : "нет"}</td>
          <td class="row">
            <button class="button small" data-edit="${i.id}">Изменить</button>
            <button class="button small danger" data-delete="${i.id}">Удалить</button>
          </td></tr>`,
      )
      .join("");
    $("intent-rows").querySelectorAll("[data-edit]").forEach((b) => (b.onclick = () => editIntent(b.dataset.edit)));
    $("intent-rows").querySelectorAll("[data-delete]").forEach((b) => (b.onclick = () => deleteIntent(b.dataset.delete)));
    pager($("intent-pager"), intentPage, page.total, (p) => ((intentPage = p), loadIntents()));
  } catch (error) {
    showError(error);
  }
}

async function editIntent(id) {
  const intent = await api(`/intents/${id}`);
  $("intent-id").value = intent.id;
  $("intent-code").value = intent.code;
  $("intent-code").disabled = true; // код не меняется
  $("intent-name").value = intent.name;
  $("intent-scenario-id").value = intent.scenario_id;
  $("intent-active").checked = intent.is_active;
  $("intent-form-title").textContent = `Изменить «${intent.name}»`;
}

async function deleteIntent(id) {
  clearError();
  if (!confirm("Удалить намерение?")) return;
  try {
    await api(`/intents/${id}`, { method: "DELETE" });
    loadIntents();
  } catch (error) {
    showError(error);
  }
}

function resetIntentForm() {
  $("intent-form").reset();
  $("intent-id").value = "";
  $("intent-code").disabled = false;
  $("intent-form-title").textContent = "Новое намерение";
}

$("intent-reset").onclick = resetIntentForm;

$("intent-form").onsubmit = async (event) => {
  event.preventDefault();
  clearError();
  const id = $("intent-id").value;
  const body = {
    name: $("intent-name").value,
    scenario_id: Number($("intent-scenario-id").value),
    is_active: $("intent-active").checked,
  };
  try {
    if (id) await api(`/intents/${id}`, { method: "PATCH", body: JSON.stringify(body) });
    else await api("/intents", { method: "POST", body: JSON.stringify({ ...body, code: $("intent-code").value }) });
    resetIntentForm();
    loadIntents();
  } catch (error) {
    showError(error);
  }
};

let searchTimer;
$("intent-search").oninput = () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => ((intentPage = 0), loadIntents()), 300);
};
$("intent-scenario").onchange = () => ((intentPage = 0), loadIntents());
$("intent-sort").onchange = () => loadIntents();

// --- аналитика ----------------------------------------------------------------

function bars(element, items, label, value) {
  const max = Math.max(1, ...items.map(value));
  element.innerHTML =
    items
      .map(
        (item) => `<div class="bar">
          <span>${escape(label(item))}</span>
          <div class="track"><div style="width:${(value(item) / max) * 100}%"></div></div>
          <b>${value(item)}</b></div>`,
      )
      .join("") || `<p class="muted">Нет данных</p>`;
}

async function loadAnalytics() {
  try {
    const [summary, top, days, dataset] = await Promise.all([
      api("/analytics/status-summary"),
      api("/analytics/top-intents?limit=5"),
      api("/analytics/commands-by-day?days=7"),
      api("/analytics/dataset"),
    ]);
    const tile = (title, value) => `<div class="tile"><span>${title}</span><b>${value}</b></div>`;
    $("summary").innerHTML =
      tile("Всего команд", summary.total) +
      tile("Выполнено", `${Math.round(summary.success_rate * 100)}%`) +
      tile("Ждут уточнения", summary.by_status.needs_clarification || 0) +
      tile("Уточнений в среднем", summary.avg_clarifications);
    $("top-rows").innerHTML = top
      .map((t) => `<tr><td>${escape(t.name)}</td><td>${t.commands}</td><td>${Math.round(t.success_rate * 100)}%</td></tr>`)
      .join("");
    bars($("days"), days, (d) => d.day, (d) => d.commands);
    bars($("dataset"), dataset, (s) => s.name, (s) => s.utterances);
  } catch (error) {
    showError(error);
  }
}

// --- старт --------------------------------------------------------------------

Promise.all([loadUsers(), loadScenarios()]).then(loadCommands).catch(showError);
