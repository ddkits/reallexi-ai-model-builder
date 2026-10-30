// SPDX-FileCopyrightText: 2026 Reallexi LLC
// SPDX-License-Identifier: Apache-2.0
'use strict';
const $ = (id) => document.getElementById(id);
const state = { connected: false, jobs: [], plan: null, healPlan: null, busy: false, library: null, selectedModel: null, step: 'plan' };
const pending = new Map();
const count = (n) => Number(n).toLocaleString('en-US');
const size = (n) => Number(n) >= 1e9 ? `${(Number(n) / 1e9).toFixed(3)}B` : Number(n) >= 1e6 ? `${(Number(n) / 1e6).toFixed(2)}M` : count(n);
function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}
function error(message = '') { $('error').textContent = message; $('error').hidden = !message; }
function request(path, method = 'GET', body = null) {
  if (!state.connected && path !== 'catalog') return Promise.reject(new Error('Connect the workspace first using Plugin Admin Unlock above.'));
  if (window.parent === window) return Promise.reject(new Error('Open Model Surgery inside the Extensions workspace to use the local Admin bridge.'));
  const requestId = crypto.randomUUID();
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => { pending.delete(requestId); reject(new Error('The request timed out. Reconnect and check history before starting another run.')); }, 120000);
    pending.set(requestId, { resolve, reject, timer });
    window.parent.postMessage({ type: 'reallexi:plugin-request', requestId, path: `/extensions/runtime/model-surgery/${path}`, method, body }, '*');
  });
}
window.addEventListener('message', (event) => {
  if (event.source !== window.parent || event.data?.type !== 'reallexi:plugin-response') return;
  const task = pending.get(event.data.requestId);
  if (!task) return;
  clearTimeout(task.timer); pending.delete(event.data.requestId);
  const result = event.data.result;
  if (!event.data.ok || result?.status === 'error') task.reject(new Error(event.data.error || result?.error || 'The operation failed.'));
  else task.resolve(result?.output ?? result);
});
async function action(work) {
  if (state.busy) return;
  state.busy = true; error(); updateButtons();
  try { await work(); } catch (e) { error(e.message); }
  finally { state.busy = false; updateButtons(); }
}
function view(step) {
  state.step = step;
  document.querySelectorAll('nav button').forEach((button) => {
    button.classList.toggle('selected', button.dataset.step === step);
    if (button.dataset.step === step) button.setAttribute('aria-current', 'step'); else button.removeAttribute('aria-current');
  });
  document.querySelectorAll('.panel').forEach((panel) => { panel.hidden = panel.id !== `panel-${step}`; });
  updateButtons();
}
document.querySelectorAll('[data-step]').forEach((button) => button.addEventListener('click', () => view(button.dataset.step)));
function expansion() {
  return { operation: 'expand', source: $('source').value.trim(), revision: $('revision').value.trim() || 'main',
    first: $('first').value, count: $('count').value, copies: $('copies').value, initialization: $('initialization').value };
}
function healing() {
  return { operation: 'heal', parent_id: $('heal-parent').value, train_file: $('train-file').value.trim(), eval_file: $('eval-file').value.trim(),
    train_scope: $('train-scope').value, device: $('device').value, steps: $('steps').value, sequence_length: $('sequence-length').value,
    learning_rate: $('learning-rate').value, accumulation: $('accumulation').value, eval_blocks: $('eval-blocks').value,
    data_rights_confirmed: $('rights').checked };
}
function active() { return state.jobs.find((job) => ['queued', 'running'].includes(job.status)); }
function updateButtons() {
  $('expand').disabled = state.busy || Boolean(active()) || !state.plan?.plan.ready;
  $('expand').disabled ||= Boolean(state.selectedModel && !state.selectedModel.eligible);
  $('heal').disabled = state.busy || Boolean(active()) || !state.healPlan?.plan.ready;
  $('connect').disabled = state.busy;
  for (const id of ['inspect','refresh']) $(id).disabled = state.busy || !state.connected;
  $('inspect').disabled ||= Boolean(state.selectedModel && !state.selectedModel.eligible);
  for (const id of ['refresh-models','scan-models','model-search','source-model']) $(id).disabled = state.busy || !state.connected;
  document.querySelector('#heal-form button[type=submit]').disabled = state.busy || !state.connected;
  document.querySelector('#probe-form button[type=submit]').disabled = state.busy || !state.connected || Boolean(active());
  for (const prefix of ['train','eval']) $(`${prefix}-upload`).disabled = state.busy || !state.connected;
  $('revision').disabled = state.busy || Boolean(state.selectedModel);
  document.querySelectorAll('[data-growth]').forEach((button) => { button.disabled = state.busy || !state.plan; });
  nextAction();
}
function nextAction() {
  $('next-action').hidden = Boolean(active());
  let title = 'Connect to begin', detail = 'Unlock Plugin Admin above, then connect to your local workspace.', label = 'Connect to start';
  let run = () => $('connect').click(), disabled = state.busy;
  const choose = () => { view('plan'); $('source-model').scrollIntoView({block:'center'}); ($('source-model').options.length > 1 ? $('source-model') : $('source')).focus(); };
  const checkpoint = state.jobs.find((job) => job.status === 'completed' && job.operation !== 'probe');
  if (state.connected) {
    if (state.step === 'plan') {
      if (state.selectedModel && !state.selectedModel.eligible) {
        title = 'This model needs preparation'; detail = state.selectedModel.reason; label = 'Choose another model'; run = choose;
      } else if (!$('source').value.trim()) {
        title = 'Choose the model to grow'; detail = 'Select your existing model or enter a backend folder / Hugging Face ID.'; label = 'Choose a model'; run = choose;
      } else if (!state.plan) {
        title = 'Next: preview the larger model'; detail = 'Inspect to calculate the exact new size and check available resources.'; label = 'Inspect & continue'; run = () => $('plan-form').requestSubmit();
      } else {
        const plan = state.plan.plan;
        title = plan.ready ? 'Ready to create the larger checkpoint' : 'Expansion is blocked';
        detail = plan.ready ? `${size(plan.original_parameters)} → ${size(plan.expanded_parameters)} parameters. Creates a separate checkpoint; healing comes next.` : plan.blockers.join(' ');
        label = 'Start expansion'; disabled ||= $('expand').disabled; run = () => $('expand').click();
      }
    } else if (state.step === 'heal' && checkpoint) {
      title = state.healPlan ? 'Next: start continual pre-training' : 'Next: prepare healing';
      detail = state.healPlan ? (state.healPlan.plan.ready ? 'Resources checked. Training creates another checkpoint.' : state.healPlan.plan.blockers.join(' ')) : 'Select a checkpoint, training text, separate evaluation text, and confirm data rights.';
      label = state.healPlan ? 'Start healing' : 'Check healing & continue';
      disabled ||= Boolean(state.healPlan && $('heal').disabled);
      run = () => state.healPlan ? $('heal').click() : $('heal-form').requestSubmit();
    } else if (state.step === 'review' && checkpoint) {
      title = 'Next: test the checkpoint'; detail = 'Select a verified checkpoint and enter a representative prompt.'; label = 'Run prompt test'; run = () => $('probe-form').requestSubmit();
    } else if (state.step === 'history' && checkpoint) {
      const healed = checkpoint.operation === 'heal';
      title = healed ? 'Next: evaluate the healed model' : 'Expansion complete. Next: healing';
      detail = 'Your verified checkpoint is saved. Continue with it in the next step.';
      label = healed ? 'Continue to prompt test' : 'Continue to healing';
      run = () => {
        $(healed ? 'probe-parent' : 'heal-parent').value = checkpoint.id;
        if (!healed) { state.healPlan = null; $('heal-results').hidden = true; }
        view(healed ? 'review' : 'heal');
      };
    } else {
      title = 'Create an expanded checkpoint first'; detail = 'Start with a supported model in Plan & expand.'; label = 'Go to model plan'; run = () => view('plan');
    }
  }
  if (state.busy) detail = 'Working… Please wait for the current check to finish.';
  else if (!$('error').hidden) detail = $('error').textContent;
  $('next-title').textContent = title; $('next-detail').textContent = detail;
  $('next-button').textContent = label; $('next-button').disabled = disabled; $('next-button').onclick = run;
}
function readiness(target, plan) {
  target.replaceChildren();
  target.append(element('div', plan.ready ? `Resources fit the estimate. Approximately ${Number(plan.estimated_ram_gb).toFixed(2)} GiB RAM${plan.estimated_training_gb ? `; ${plan.estimated_training_gb.toFixed(2)} GiB training memory` : ''}${plan.estimated_disk_gb ? `; ${plan.estimated_disk_gb.toFixed(2)} GiB output disk` : ''}. The worker checks again before loading.` : plan.blockers.join(' '), plan.ready ? 'ready' : 'blocked'));
}
async function inspect() {
  const input = expansion();
  const reviewed = await request('preflight', 'POST', input);
  if (JSON.stringify(input) !== JSON.stringify(expansion())) throw new Error('The recipe changed while checking it. Check the current architecture again.');
  state.plan = reviewed;
  const plan = reviewed.plan; $('plan-results').hidden = false; $('middle').disabled = false;
  $('size-metrics').replaceChildren();
  for (const [value, label] of [[size(plan.original_parameters), 'Source parameters'], [size(plan.expanded_parameters), 'Expanded parameters'], [`${plan.source_layers} → ${plan.expanded_layers}`, 'Transformer layers']]) {
    const tile = element('div', undefined, 'metric'); tile.append(element('strong', value), element('span', label)); $('size-metrics').append(tile);
  }
  $('layer-description').textContent = `${plan.source_layers} source layers + (${plan.count} layer(s) per block × ${plan.copies} extra copies) = ${plan.expanded_layers} layers. Copy from position ${plan.first}–${plan.first + plan.count - 1}, after the original block. Add ${count(plan.added_parameters)} independent parameters. Exact total: ${count(plan.expanded_parameters)}.${state.selectedModel ? ' Using the selected local checkpoint.' : ` Resolved revision: ${plan.revision}.`}`;
  readiness($('plan-readiness'), plan);
  $('expansion-action').scrollIntoView({block:'center', behavior:'smooth'});
}
$('plan-form').addEventListener('submit', (event) => { event.preventDefault(); action(inspect); });
$('plan-form').addEventListener('input', (event) => {
  if (['model-search','scan-directory'].includes(event.target.id)) return;
  if (event.target.id === 'source') { state.selectedModel = null; $('source-model').value = ''; $('selected-model').hidden = true; }
  state.plan = null; $('plan-results').hidden = true; updateButtons();
});
$('heal-form').addEventListener('input', () => { state.healPlan = null; $('heal-results').hidden = true; updateButtons(); });
$('plan-form').addEventListener('invalid', (event) => { const details = event.target.closest('details'); if (details) details.open = true; }, true);
$('initialization').addEventListener('change', () => {
  $('initialization-help').textContent = $('initialization').value === 'identity'
    ? 'Recommended: identity mode makes the added layers initially pass information through without changing the source probe output. The worker checks this. Train and evaluate afterward to make the added capacity useful.'
    : 'Copy mode applies the copied layers at their new positions with the original weights. This can change outputs immediately. Use it for depth-stacking experiments, followed by healing and evaluation.';
});
document.querySelectorAll('[data-growth]').forEach((button) => button.addEventListener('click', () => action(async () => {
  if (!state.plan) throw new Error('Inspect your model first.');
  const depth = state.plan.plan.source_layers;
  $('first').value = Math.floor(depth / 2); $('count').value = 1;
  $('copies').value = Math.max(1, Math.ceil(depth * Number(button.dataset.growth)));
  state.plan = null; await inspect();
})));
$('middle').addEventListener('click', () => action(async () => {
  if (!state.plan) throw new Error('Check the architecture first.');
  const depth = state.plan.plan.source_layers;
  $('first').value = Math.floor(depth / 3); $('count').value = Math.max(1, Math.floor(depth / 3)); $('copies').value = 1;
  state.plan = null; await inspect();
}));
$('target').addEventListener('click', () => action(async () => {
  const plan = state.plan?.plan, target = Number($('target-size').value) * 1e9;
  if (!plan || !Number.isFinite(target) || target <= plan.original_parameters) throw new Error('Enter a target larger than the source size.');
  const perLayer = plan.added_parameters / (plan.count * plan.copies);
  $('first').value = Math.floor(plan.source_layers / 2); $('count').value = 1;
  const copies = Math.ceil((target - plan.original_parameters) / perLayer);
  if (!Number.isSafeInteger(copies)) throw new Error('The layer count cannot be represented accurately by this browser.');
  $('copies').value = copies; state.plan = null; await inspect();
}));
async function refresh() {
  const result = await request('jobs'); state.jobs = result.jobs; renderJobs(); updateParents(); updateButtons();
}
async function connect() {
  const result = await request('catalog'); state.connected = true; state.jobs = result.jobs;
  state.library = result.model_library || { models: [], roots: [], warnings: [] }; renderModels();
  $('connection-state').textContent = `Connected locally · ${Number(result.resources.memory_available_gb).toFixed(1)} GiB RAM available · ${Number(result.resources.disk_free_gb).toFixed(1)} GiB disk free`;
  const selected = $('device').value; $('device').replaceChildren(new Option('CPU', 'cpu'));
  for (const accelerator of result.resources.accelerators || []) if (accelerator.usable && accelerator.torch_device?.startsWith('cuda:')) $('device').add(new Option(`${accelerator.name} (${accelerator.torch_device})`, accelerator.torch_device));
  if ([...$('device').options].some((option) => option.value === selected)) $('device').value = selected;
  renderJobs(); updateParents();
}
$('connect').addEventListener('click', () => action(connect));
$('refresh').addEventListener('click', () => action(refresh));
function renderModels() {
  const all = state.library?.models || [];
  const query = $('model-search').value.trim().toLocaleLowerCase();
  const filtered = all.filter((model) => `${model.label} ${model.path} ${model.architecture} ${model.reason}`.toLocaleLowerCase().includes(query));
  const selected = state.selectedModel?.id;
  $('source-model').replaceChildren(new Option(all.length ? 'Choose a model, or enter a path / Hub ID below' : 'No models found — scan a folder or enter a path below', ''));
  const groups = { trained: 'Your trained models', merged: 'Merged full SafeTensors exports', local: 'Local model folders', cached: 'Downloaded Hugging Face checkpoints', surgery: 'Earlier surgery checkpoints' };
  for (const [kind, label] of Object.entries(groups)) {
    const entries = filtered.filter((model) => model.kind === kind);
    if (!entries.length) continue;
    const group = document.createElement('optgroup'); group.label = label;
    for (const model of entries) group.append(new Option(`${model.label} · ${model.eligible ? model.architecture : 'needs preparation'}`, model.id));
    $('source-model').append(group);
  }
  if (selected && filtered.some((model) => model.id === selected)) $('source-model').value = selected;
  $('library-summary').textContent = `${all.length} model entries found · ${all.filter((model) => model.eligible).length} eligible for preflight${query ? ` · ${filtered.length} match your search` : ''}. Adapters and unsupported formats remain listed with preparation steps.`;
  const roots = $('model-roots-content'); roots.replaceChildren();
  for (const root of state.library?.roots || []) roots.append(element('p', `${root.label}: ${root.path}${root.available ? '' : ' (not present in this backend)'}`));
  for (const warning of state.library?.warnings || []) roots.append(element('p', warning, 'discovery-warning'));
  if (state.selectedModel) {
    const updated = all.find((model) => model.id === state.selectedModel.id);
    if (!updated) { state.selectedModel = null; state.plan = null; $('plan-results').hidden = true; $('selected-model').hidden = true; }
    else {
      if (updated.eligible !== state.selectedModel.eligible) { state.plan = null; $('plan-results').hidden = true; }
      showSelectedModel(updated);
    }
  }
}
function showSelectedModel(model) {
  state.selectedModel = model;
  const detail = $('selected-model'); detail.hidden = false; detail.replaceChildren(element('strong', model.label), element('code', model.path), element('p', model.reason));
  detail.className = `model-detail ${model.eligible ? 'model-eligible' : 'model-blocked'}`;
}
async function loadModels(scan = false) {
  const directory = $('scan-directory').value.trim();
  if (scan && !directory) throw new Error('Enter the backend model folder to scan.');
  state.library = await request('models', directory ? 'POST' : 'GET', directory ? {directory} : null);
  renderModels();
}
$('refresh-models').addEventListener('click', () => action(() => loadModels()));
$('scan-models').addEventListener('click', () => action(() => loadModels(true)));
$('model-search').addEventListener('input', renderModels);
$('source-model').addEventListener('change', () => {
  const model = state.library?.models.find((entry) => entry.id === $('source-model').value);
  state.plan = null; $('plan-results').hidden = true;
  if (model) { showSelectedModel(model); $('source').value = model.path; $('revision').value = 'main'; $('first').value = 0; $('count').value = 1; $('copies').value = 1; }
  else { state.selectedModel = null; $('selected-model').hidden = true; }
  updateButtons();
});
function updateParents() {
  const checkpoints = state.jobs.filter((job) => job.status === 'completed' && job.operation !== 'probe');
  for (const id of ['heal-parent','probe-parent']) {
    const selected = $(id).value; $(id).replaceChildren(new Option(checkpoints.length ? 'Select a checkpoint' : 'Create an expanded checkpoint first', ''));
    for (const job of checkpoints) $(id).add(new Option(`${job.operation === 'heal' ? 'Healed' : 'Expanded'} · ${size(job.evidence.expanded_parameters)} · ${job.id.slice(0,8)}`, job.id));
    if (checkpoints.some((job) => job.id === selected)) $(id).value = selected;
  }
}
function renderJobs() {
  $('jobs').replaceChildren();
  if (!state.jobs.length) $('jobs').append(element('p', 'No runs yet. Start by checking your source architecture.'));
  for (const job of state.jobs) {
    const card = element('article', undefined, `run ${job.status}`);
    const heading = element('div', undefined, 'run-head'); heading.append(element('strong', `${job.operation === 'expand' ? 'Architecture expansion' : job.operation === 'heal' ? 'Continual pre-training' : 'Prompt test'} · ${job.id.slice(0,8)}`), element('span', job.status, 'status'));
    card.append(heading, element('p', `${new Date(job.created_at * 1000).toLocaleString()} · ${job.message}`));
    const proof = job.evidence;
    if (job.status === 'completed' && proof) {
      if (job.operation === 'probe') card.append(element('p', `Prompt: ${proof.prompt}`), element('div', proof.completion || '(No visible completion tokens)', 'callout'));
      else {
        card.append(element('p', `${count(proof.expanded_parameters)} parameters · reload and finite-output check passed · ${proof.status.replaceAll('_',' ')}`), element('code', job.model_path));
        if (proof.before_evaluation) card.append(element('p', `Held-out loss: ${proof.before_evaluation.loss.toFixed(4)} → ${proof.after_evaluation.loss.toFixed(4)} (${proof.loss_improved ? 'lower' : 'did not improve'}). ${count(proof.training_tokens)} token exposures; ${proof.repeated_passes} repeated pass(es). Broad quality still needs review.`));
        const actions = element('div', undefined, 'actions');
        for (const [label, destination] of [['Heal this checkpoint','heal'], ['Test a prompt','review']]) {
          const button = element('button', label, 'secondary'); button.addEventListener('click', () => { $(destination === 'heal' ? 'heal-parent' : 'probe-parent').value = job.id; state.healPlan = null; $('heal-results').hidden = true; updateButtons(); view(destination); }); actions.append(button);
        }
        const more = element('button', 'Expand again', 'secondary'); more.addEventListener('click', () => { $('source').value = job.model_path; state.selectedModel = null; $('source-model').value = ''; $('selected-model').hidden = true; state.plan = null; $('plan-results').hidden = true; updateButtons(); view('plan'); }); actions.append(more); card.append(actions);
      }
    }
    $('jobs').append(card);
  }
  const running = active(); $('active-job').hidden = !running;
  if (running) {
    $('active-job').replaceChildren(element('strong', `${running.operation === 'heal' ? 'Healing' : running.operation === 'probe' ? 'Prompt test' : 'Expansion'} in progress`), element('p', running.message));
    if (running.steps) { const bar = element('progress'); bar.max = running.steps; bar.value = running.step || 0; $('active-job').append(bar); }
    const cancel = element('button', 'Request cancellation'); cancel.addEventListener('click', () => action(async () => { const response = await request('cancel','POST',{id:running.id}); $('active-job').append(element('p', response.message)); cancel.disabled = true; })); $('active-job').append(cancel);
  }
}
$('expand').addEventListener('click', () => action(async () => {
  if (!state.plan?.plan.ready) throw new Error('Check the plan first.');
  await request('jobs','POST', state.plan.request); await refresh(); view('history');
}));
$('heal-form').addEventListener('submit', (event) => { event.preventDefault(); action(async () => {
  const input = healing();
  const reviewed = await request('preflight','POST',input);
  if (JSON.stringify(input) !== JSON.stringify(healing())) throw new Error('The healing recipe changed. Check the current settings again.');
  state.healPlan = reviewed; $('heal-results').hidden = false;
  readiness($('heal-readiness'), state.healPlan.plan);
  $('heal-results').scrollIntoView({block:'center', behavior:'smooth'});
}); });
$('heal').addEventListener('click', () => action(async () => {
  if (!state.healPlan?.plan.ready) throw new Error('Check healing resources first.');
  await request('jobs','POST',state.healPlan.request); await refresh(); view('history');
}));
for (const prefix of ['train','eval']) $(`${prefix}-upload`).addEventListener('change', () => action(async () => {
  const file = $(`${prefix}-upload`).files[0]; if (!file) return;
  if (file.size > 16 * 1024 * 1024) throw new Error('For files over 16 MiB, use a mounted backend path.');
  const text = new TextDecoder('utf-8', {fatal:true}).decode(await file.arrayBuffer());
  const result = await request('dataset','POST',{text}); $(`${prefix}-file`).value = result.path;
  state.healPlan = null; $('heal-results').hidden = true;
}));
$('probe-form').addEventListener('submit', (event) => { event.preventDefault(); action(async () => {
  await request('jobs','POST',{operation:'probe',parent_id:$('probe-parent').value,prompt:$('prompt').value,max_new_tokens:$('new-tokens').value});
  await refresh(); view('history');
}); });
setInterval(() => { if (state.connected && !state.busy && active()) action(refresh); }, 2500);
updateButtons();
