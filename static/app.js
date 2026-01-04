let currentSession = null;

const queryInput = document.getElementById('query-input');
const startBtn = document.getElementById('start-btn');
const quickQueryBtns = document.querySelectorAll('.quick-query');
const navLinks = document.querySelectorAll('.nav-link');
const tabChat = document.getElementById('tab-chat');
const tabForm = document.getElementById('tab-form');
const candidateList = document.getElementById('candidate-list');
const confidenceEl = document.getElementById('confidence');
const questionsEl = document.getElementById('questions');
const clarifyBtn = document.getElementById('clarify-btn');
const sqlBtn = document.getElementById('sql-btn');
const sqlPreview = document.getElementById('sql-preview');
const timeline = document.getElementById('timeline');
const conflictCard = document.getElementById('conflict-card');
const conflictBody = document.getElementById('conflict-body');
const slotFormEl = document.getElementById('slot-form');
const slotFormBtn = document.getElementById('slot-form-btn');
const confirmationEl = document.getElementById('confirmation');
const confirmExecBtn = document.getElementById('confirm-exec');
const confirmModifyBtn = document.getElementById('confirm-modify');
const expertCard = document.getElementById('expert-card');
const expertTitle = document.getElementById('expert-title');
const expertContext = document.getElementById('expert-context');
const expertReason = document.getElementById('expert-reason');
const expertOptions = document.getElementById('expert-options');
const expertRevise = document.getElementById('expert-revise');
const expertReviseBtn = document.getElementById('expert-revise-btn');
const expertForward = document.getElementById('expert-forward');
const expertForwardBtn = document.getElementById('expert-forward-btn');
const designBtn = document.getElementById('design-btn');
const newAnalysisBtn = document.getElementById('new-analysis-btn');
const expertRouteToggle = document.getElementById('expert-route');

function appendMessage(role, text) {
  const wrapper = document.createElement('div');
  wrapper.className = `message ${role}`;
  const avatar = document.createElement('div');
  avatar.className = 'avatar';
  avatar.textContent = role === 'agent' ? 'A' : 'U';
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.innerText = text;
  wrapper.appendChild(avatar);
  wrapper.appendChild(bubble);
  timeline.appendChild(wrapper);
  timeline.scrollTop = timeline.scrollHeight;
}

function renderCandidates(candidates, selectedSpec) {
  candidateList.innerHTML = '';
  candidates.forEach((c) => {
    const div = document.createElement('div');
    div.className = 'candidate';
    if (selectedSpec && selectedSpec.spec_id === c.spec.spec_id) {
      div.classList.add('selected');
    }
    const title = document.createElement('div');
    title.className = 'title';
    title.innerHTML = `${c.spec.name}<span class="badge">${c.spec.version}</span>`;

    const meta = document.createElement('div');
    meta.className = 'meta';
    meta.innerText = `${c.spec.domain} · ${c.spec.data_source}`;

    const summary = document.createElement('div');
    summary.className = 'muted';
    summary.innerText = c.spec.summary;

    const row = document.createElement('div');
    row.className = 'row';
    row.innerHTML = `<span>口径：${c.spec.metric_caliber || '未声明'}</span><span>${c.spec.time_granularity} · ${c.spec.time_semantics}</span>`;

    const filter = document.createElement('div');
    filter.className = 'muted';
    filter.innerHTML = `<strong>过滤:</strong> ${c.spec.filters.join('，') || '无'} | 映射: ${
      c.spec.industry_mapping || '未指定'
    } | owner: ${c.spec.owner}`;

    const snippet = document.createElement('pre');
    snippet.className = 'sql-snippet mono';
    snippet.innerText = c.spec.sql_snippet;

    div.appendChild(title);
    div.appendChild(meta);
    div.appendChild(summary);
    div.appendChild(row);
    div.appendChild(filter);
    div.appendChild(snippet);

    div.addEventListener('click', async () => {
      await selectSpec(c.spec.spec_id);
    });

    candidateList.appendChild(div);
  });
}

function renderQuestions(questions, clarifications) {
  questionsEl.innerHTML = '';
  if (!questions || questions.length === 0) {
    questionsEl.innerHTML = '<div class="muted">暂无澄清问题</div>';
    clarifyBtn.disabled = true;
    return;
  }
  questions.forEach((q) => {
    const wrapper = document.createElement('div');
    wrapper.className = 'question';
    const label = document.createElement('label');
    label.textContent = `${q.question} ${q.recommended ? '（推荐：' + q.recommended + '）' : ''}`;
    const select = document.createElement('select');
    select.className = 'select';
    select.dataset.slot = q.slot;
    q.options.forEach((opt) => {
      const option = document.createElement('option');
      option.value = opt;
      option.text = opt;
      if (clarifications[q.slot]?.value === opt || (!clarifications[q.slot] && q.recommended === opt)) {
        option.selected = true;
      }
      select.appendChild(option);
    });
    wrapper.appendChild(label);
    wrapper.appendChild(select);
    questionsEl.appendChild(wrapper);
  });
  clarifyBtn.disabled = false;
}

function renderConflict(conflict) {
  if (!conflict) {
    conflictCard.style.display = 'none';
    return;
  }
  conflictCard.style.display = 'block';
  conflictBody.innerHTML = '';
  const msg = document.createElement('div');
  msg.textContent = conflict.message;
  conflictBody.appendChild(msg);
  const opts = document.createElement('div');
  opts.className = 'conflict-options';
  conflict.options.forEach((opt) => {
    const btn = document.createElement('button');
    btn.className = 'btn secondary';
    btn.textContent = `${opt.label}（${opt.consequence}）`;
    btn.addEventListener('click', () => resolveConflict(opt.option_id));
    opts.appendChild(btn);
  });
  conflictBody.appendChild(opts);
}

function renderSlotForm(fields) {
  slotFormEl.innerHTML = '';
  if (!fields || fields.length === 0) {
    slotFormBtn.disabled = true;
    return;
  }
  fields.forEach((field) => {
    const wrapper = document.createElement('div');
    wrapper.className = 'field';
    const label = document.createElement('label');
    label.textContent = field.label;
    const select = document.createElement('select');
    select.className = 'select';
    select.dataset.slot = field.slot;
    field.options.forEach((opt) => {
      const option = document.createElement('option');
      option.value = opt;
      option.text = opt;
      if (field.value === opt) {
        option.selected = true;
      }
      select.appendChild(option);
    });
    wrapper.appendChild(label);
    wrapper.appendChild(select);
    slotFormEl.appendChild(wrapper);
  });
  slotFormBtn.disabled = false;
}

function renderExpertCard(card, slotFormFields) {
  if (!card) {
    expertCard.style.display = 'none';
    return;
  }
  expertCard.style.display = 'block';
  expertTitle.textContent = card.title;
  expertContext.textContent = `来源：用户 @${card.source_user}`;
  expertReason.textContent = `求助理由：${card.reason}`;
  expertOptions.innerHTML = '';
  card.options.forEach((opt) => {
    const div = document.createElement('div');
    div.className = 'expert-option';
    div.innerHTML = `
      <div class="line">
        <strong>${opt.label}</strong>
        <span class="badge">置信 ${opt.confidence}</span>
      </div>
      <div class="muted">业务定义：${opt.definition}</div>
      <div class="muted">口径/过滤：${opt.business_hint || '未声明'} ｜ ${opt.filters.join('；') || '无'}</div>
      <div class="muted">来源：${opt.source}</div>
    `;
    const pre = document.createElement('pre');
    pre.textContent = opt.snippet.join('\n');
    div.appendChild(pre);
    const btn = document.createElement('button');
    btn.className = 'btn full primary';
    btn.textContent = `确认${opt.label}`;
    btn.addEventListener('click', () => expertConfirm(opt.spec_id));
    div.appendChild(btn);
    expertOptions.appendChild(div);
  });

  expertRevise.innerHTML = '';
  slotFormFields.forEach((field) => {
    const wrapper = document.createElement('div');
    wrapper.className = 'field';
    const label = document.createElement('label');
    label.textContent = field.label;
    const select = document.createElement('select');
    select.className = 'select';
    select.dataset.slot = field.slot;
    field.options.forEach((opt) => {
      const option = document.createElement('option');
      option.value = opt;
      option.text = opt;
      if (field.value === opt) option.selected = true;
      select.appendChild(option);
    });
    wrapper.appendChild(label);
    wrapper.appendChild(select);
    expertRevise.appendChild(wrapper);
  });
}

function renderConfirmation(confirmation) {
  confirmationEl.innerHTML = '';
  if (!confirmation) {
    confirmExecBtn.disabled = true;
    return;
  }
  const lines = [
    `指标：${confirmation.metric} (${confirmation.version})`,
    `粒度：${confirmation.grain}`,
    `时间：${confirmation.time_range}`,
    `时间口径：${confirmation.time_semantics}`,
    `行业映射：${confirmation.industry_mapping}`,
    `过滤：${confirmation.filters.join('，') || '无'}`,
    `口径：${confirmation.caliber || '未声明'}`,
    `数据源：${confirmation.source} | Owner ${confirmation.owner}`,
    `澄清：${Object.keys(confirmation.clarifications || {}).length > 0 ? JSON.stringify(confirmation.clarifications) : '未补充'}`,
  ];
  lines.forEach((line) => {
    const div = document.createElement('div');
    div.innerHTML = `<span class="label">●</span> ${line}`;
    confirmationEl.appendChild(div);
  });
  confirmExecBtn.disabled = false;
}

function updateSql(sql) {
  sqlPreview.textContent = sql || '';
}

function resetUI() {
  currentSession = null;
  candidateList.innerHTML = '';
  questionsEl.innerHTML = '';
  slotFormEl.innerHTML = '';
  confirmationEl.innerHTML = '';
  conflictCard.style.display = 'none';
  expertCard.style.display = 'none';
  updateSql('');
  clarifyBtn.disabled = true;
  sqlBtn.disabled = true;
  confirmExecBtn.disabled = true;
  slotFormBtn.disabled = true;
  confidenceEl.textContent = '置信度 --';
}

function refreshUI(data) {
  currentSession = data;
  confidenceEl.textContent = `置信度 ${data.confidence?.toFixed ? data.confidence.toFixed(2) : '--'}`;
  renderCandidates(data.candidates || [], data.selected_spec);
  renderConflict(data.conflict);
  renderExpertCard(data.expert_card, data.slot_form || []);
  renderQuestions(data.questions || [], data.clarifications || {});
  renderSlotForm(data.slot_form || []);
  renderConfirmation(data.confirmation);
  sqlBtn.disabled = !data.selected_spec;
  confirmExecBtn.disabled = !data.selected_spec;
  slotFormBtn.disabled = !data.slot_form || data.slot_form.length === 0;
  updateSql(data.sql);
}

function setActiveNav(target) {
  navLinks.forEach((el) => {
    el.classList.toggle('active', el === target);
  });
}

function setActiveTab(tab) {
  if (!tabChat || !tabForm) return;
  if (tab === 'chat') {
    tabChat.classList.add('active');
    tabForm.classList.remove('active');
    timeline.scrollIntoView({ behavior: 'smooth' });
  } else {
    tabForm.classList.add('active');
    tabChat.classList.remove('active');
    slotFormEl.scrollIntoView({ behavior: 'smooth' });
  }
}

async function startSession(presetQuery = null, silent = false) {
  const query = (presetQuery || queryInput.value || '').trim();
  if (!query) {
    alert('请输入需求描述');
    return;
  }
  const res = await fetch('/api/session/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, user: 'demo_user', route_expert: expertRouteToggle?.checked }),
  });
  const data = await res.json();
  if (!silent) {
    timeline.innerHTML = '';
    appendMessage('user', query);
    appendMessage('agent', '已检索到候选口径，选择或补充澄清后生成 SQL。');
  }
  refreshUI(data);
}

async function selectSpec(specId) {
  if (!currentSession) return;
  const res = await fetch('/api/session/select_spec', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: currentSession.session_id, spec_id: specId }),
  });
  const data = await res.json();
  refreshUI(data);
  appendMessage('agent', `已选择口径：${data.selected_spec.name}`);
}

async function submitClarifications() {
  if (!currentSession) return;
  const selections = Array.from(questionsEl.querySelectorAll('select')).map((sel) => ({
    slot: sel.dataset.slot,
    value: sel.value,
  }));
  const res = await fetch('/api/session/clarify', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: currentSession.session_id, answers: selections }),
  });
  const data = await res.json();
  refreshUI(data);
  appendMessage('agent', `澄清完成：${JSON.stringify(selections.map((s) => s.value)).replace(/"/g, '')}`);
}

async function generateSql() {
  if (!currentSession || !currentSession.selected_spec) return;
  const res = await fetch('/api/session/generate_sql', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: currentSession.session_id }),
  });
  const data = await res.json();
  refreshUI(data);
  appendMessage('agent', 'SQL 已生成，见右侧。');
}

async function resolveConflict(optionId) {
  if (!currentSession) return;
  const res = await fetch('/api/session/resolve_conflict', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: currentSession.session_id, option_id: optionId }),
  });
  const data = await res.json();
  refreshUI(data);
  appendMessage('agent', '已根据你的选择调整口径，请确认澄清。');
}

async function expertConfirm(specId) {
  if (!currentSession) return;
  const res = await fetch('/api/expert/decision', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: currentSession.session_id, action: 'confirm', spec_id: specId }),
  });
  const data = await res.json();
  refreshUI(data);
  appendMessage('agent', '专家已确认推测，已更新口径。');
}

async function expertReviseAction() {
  if (!currentSession) return;
  const selections = Array.from(expertRevise.querySelectorAll('select')).map((sel) => ({
    slot: sel.dataset.slot,
    value: sel.value,
  }));
  const res = await fetch('/api/expert/decision', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: currentSession.session_id, action: 'revise', answers: selections }),
  });
  const data = await res.json();
  refreshUI(data);
  appendMessage('agent', '专家修正完毕，已更新槽位。');
}

async function expertForwardAction() {
  if (!currentSession) return;
  const forward_to = expertForward.value.trim();
  if (!forward_to) {
    alert('请输入转发对象');
    return;
  }
  const res = await fetch('/api/expert/decision', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: currentSession.session_id, action: 'forward', forward_to }),
  });
  const data = await res.json();
  refreshUI(data);
  appendMessage('agent', `已转发给 ${forward_to} 等待确认。`);
}

async function applySlotForm() {
  if (!currentSession) return;
  const selections = Array.from(slotFormEl.querySelectorAll('select')).map((sel) => ({
    slot: sel.dataset.slot,
    value: sel.value,
  }));
  const res = await fetch('/api/session/clarify', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: currentSession.session_id, answers: selections }),
  });
  const data = await res.json();
  refreshUI(data);
  appendMessage('agent', '已应用表单口径设置。');
}

startBtn.addEventListener('click', startSession);
clarifyBtn.addEventListener('click', submitClarifications);
sqlBtn.addEventListener('click', generateSql);
slotFormBtn.addEventListener('click', applySlotForm);
confirmExecBtn.addEventListener('click', generateSql);
confirmModifyBtn.addEventListener('click', () => {
  questionsEl.scrollIntoView({ behavior: 'smooth' });
});
expertReviseBtn.addEventListener('click', expertReviseAction);
expertForwardBtn.addEventListener('click', expertForwardAction);

quickQueryBtns.forEach((btn) => {
  btn.addEventListener('click', () => {
    const q = btn.dataset.query || '';
    queryInput.value = q;
    setActiveNav(document.getElementById('nav-chat'));
    startSession(q);
  });
});

navLinks.forEach((link) => {
  link.addEventListener('click', () => {
    setActiveNav(link);
    const q = link.dataset.query;
    if (q) {
      queryInput.value = q;
      startSession(q);
    }
  });
});

tabChat?.addEventListener('click', () => setActiveTab('chat'));
tabForm?.addEventListener('click', () => setActiveTab('form'));

designBtn?.addEventListener('click', () => {
  appendMessage('agent', '设计规范参考 docs/PRD.md，已根据 PRD 打通低摩擦澄清、冲突处理与专家协同。');
});

newAnalysisBtn?.addEventListener('click', () => {
  queryInput.value = '';
  timeline.innerHTML = '';
  resetUI();
  appendMessage('agent', '已重置上下文，可直接输入新需求或选择页面快捷入口。');
});

// preload sample query
queryInput.value = '电商直播用户 7 日 GMV 趋势及口径澄清';
startSession(queryInput.value, true);
