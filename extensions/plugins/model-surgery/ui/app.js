// SPDX-FileCopyrightText: 2026 Reallexi LLC
// SPDX-License-Identifier: Apache-2.0
'use strict';
const $ = (id) => document.getElementById(id);
const state = { connected: false, jobs: [], plan: null, healPlan: null, busy: false };
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
  document.querySelectorAll('nav button').forEach((button) => {
    button.classList.toggle('selected', button.dataset.step === step);
    if (button.dataset.step === step) button.setAttribute('aria-current', 'step'); else button.removeAttribute('aria-current');
  });
  document.querySelectorAll('.panel').forEach((panel) => { panel.hidden = panel.id !== `panel-${step}`; });
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
  $('heal').disabled = state.busy || Boolean(active()) || !state.healPlan?.plan.ready;
  $('connect').disabled = state.busy;
  for (const id of ['inspect','refresh']) $(id).disabled = state.busy || !state.connected;
  document.querySelector('#heal-form button[type=submit]').disabled = state.busy || !state.connected;
  document.querySelector('#probe-form button[type=submit]').disabled = state.busy || !state.connected || Boolean(active());
  for (const prefix of ['train','eval']) $(`${prefix}-upload`).disabled = state.busy || !state.connected;
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
  $('layer-description').textContent = `Copy layers ${plan.first}–${plan.first + plan.count - 1} ${plan.copies} additional time(s), after the original block. Add ${count(plan.added_parameters)} independent parameters. Exact total: ${count(plan.expanded_parameters)}. Resolved revision: ${plan.revision}.`;
  readiness($('plan-readiness'), plan);
}
$('plan-form').addEventListener('submit', (event) => { event.preventDefault(); action(inspect); });
$('plan-form').addEventListener('input', () => { state.plan = null; $('plan-results').hidden = true; updateButtons(); });
$('heal-form').addEventListener('input', () => { state.healPlan = null; $('heal-results').hidden = true; updateButtons(); });
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
  $('connection-state').textContent = `Connected locally · ${Number(result.resources.memory_available_gb).toFixed(1)} GiB RAM available · ${Number(result.resources.disk_free_gb).toFixed(1)} GiB disk free`;
  const selected = $('device').value; $('device').replaceChildren(new Option('CPU', 'cpu'));
  for (const accelerator of result.resources.accelerators || []) if (accelerator.usable && accelerator.torch_device?.startsWith('cuda:')) $('device').add(new Option(`${accelerator.name} (${accelerator.torch_device})`, accelerator.torch_device));
  if ([...$('device').options].some((option) => option.value === selected)) $('device').value = selected;
  renderJobs(); updateParents();
}
$('connect').addEventListener('click', () => action(connect));
$('refresh').addEventListener('click', () => action(refresh));
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
        const more = element('button', 'Expand again', 'secondary'); more.addEventListener('click', () => { $('source').value = job.model_path; state.plan = null; $('plan-results').hidden = true; updateButtons(); view('plan'); }); actions.append(more); card.append(actions);
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
