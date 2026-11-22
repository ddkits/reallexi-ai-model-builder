// SPDX-FileCopyrightText: 2026 Reallexi LLC
// SPDX-License-Identifier: Apache-2.0
'use strict';
const $ = (id) => document.getElementById(id);
const state = { connected: false, jobs: [], plan: null, healPlan: null, busy: false, library: null, selectedModel: null, step: 'plan', website: null, websitePolling: false };
const pending = new Map();
const count = (n) => Number(n).toLocaleString('en-US');
const size = (n) => Number(n) >= 1e9 ? `${(Number(n) / 1e9).toFixed(3)}B` : Number(n) >= 1e6 ? `${(Number(n) / 1e6).toFixed(2)}M` : count(n);
const checkpointName = (job) => job.evidence?.model_name || `Lexi ${size(job.evidence?.expanded_parameters || 0)}`;
const isHealed = (job) => job.evidence?.status === 'trained_needs_quality_review' || job.operation === 'heal';
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
  const request = { operation: 'expand', source: $('source').value.trim(), revision: $('revision').value.trim() || 'main',
    first: $('first').value, count: $('count').value, copies: $('copies').value, initialization: $('initialization').value };
  if ($('heal-after-expand').checked) request.healing_recipe = healingRecipe();
  return request;
}
function healingRecipe() {
  return { train_file: $('train-file').value.trim(), eval_file: $('eval-file').value.trim(),
    train_scope: $('train-scope').value, device: $('device').value, steps: $('steps').value, sequence_length: $('sequence-length').value,
    learning_rate: $('learning-rate').value, accumulation: $('accumulation').value, eval_blocks: $('eval-blocks').value, optimizer: $('optimizer').value,
    data_rights_confirmed: $('rights').checked };
}
function healing() { return { operation: 'heal', parent_id: $('heal-parent').value, ...healingRecipe() }; }
function invalidateExpansion() { state.plan = null; $('plan-results').hidden = true; }
function healingRecipeChanged() {
  state.healPlan = null; $('heal-results').hidden = true;
  if ($('heal-after-expand').checked) invalidateExpansion();
}
function active() { return state.jobs.find((job) => ['queued', 'running'].includes(job.status)); }
function updateButtons() {
  const autoHeal = $('heal-after-expand').checked;
  $('expand').textContent = autoHeal ? 'Expand & train' : 'Start expansion';
  $('expansion-description').textContent = autoHeal
    ? 'Review both stages. Training starts automatically after the expanded checkpoint is verified.'
    : 'Expansion saves a new checkpoint. You can heal it from Run history.';
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
  $('website-build').disabled = state.busy || !state.connected || Boolean(state.website && ['queued','running'].includes(state.website.status));
  for (const id of ['website-download','website-use']) $(id).disabled = state.busy || !state.connected;
  $('full-gpu-pilot').disabled = state.busy || !state.connected;
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
        detail = plan.ready ? `${size(plan.original_parameters)} → ${size(plan.expanded_parameters)} parameters. ${$('expansion-description').textContent}` : plan.blockers.join(' ');
        label = $('expand').textContent; disabled ||= $('expand').disabled; run = () => $('expand').click();
      }
    } else if (state.step === 'heal' && checkpoint) {
      title = state.healPlan ? 'Next: start continual pre-training' : 'Next: prepare healing';
      detail = state.healPlan ? (state.healPlan.plan.ready ? 'Resources checked. Training creates another checkpoint.' : state.healPlan.plan.blockers.join(' ')) : 'Select a checkpoint, training text, separate evaluation text, and confirm data rights.';
      label = state.healPlan ? 'Start healing' : 'Check healing & continue';
      disabled ||= Boolean(state.healPlan && $('heal').disabled);
      run = () => state.healPlan ? $('heal').click() : $('heal-form').requestSubmit();
      if (!$('train-file').value.trim() || !$('eval-file').value.trim()) {
        const collecting = state.website && ['queued','running'].includes(state.website.status);
        title = collecting ? 'Preparing the Reallexi dataset' : 'Next: choose your training text';
        detail = collecting ? `${state.website.documents || 0} documents collected. Training and evaluation paths will fill when ready.` : 'Build the Reallexi website dataset, or provide your own training and separate evaluation files below.';
        label = collecting ? 'Collection in progress' : state.website?.status === 'completed' ? 'Use saved Reallexi dataset' : 'Build dataset & continue';
        disabled ||= Boolean(collecting);
        run = () => $(state.website?.status === 'completed' ? 'website-use' : 'website-build').click();
      }
    } else if (state.step === 'review' && checkpoint) {
      title = 'Next: test the checkpoint'; detail = 'Select a verified checkpoint and enter a representative prompt.'; label = 'Run prompt test'; run = () => $('probe-form').requestSubmit();
    } else if (state.step === 'history' && checkpoint) {
      const healed = isHealed(checkpoint);
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
  target.append(element('div', plan.ready ? `Resources fit the estimate. Approximately ${Number(plan.estimated_ram_gb).toFixed(2)} GiB RAM${plan.estimated_training_gb ? `; ${plan.estimated_training_gb.toFixed(2)} GiB training memory` : ''}${plan.estimated_disk_gb ? `; ${plan.estimated_disk_gb.toFixed(2)} GiB output disk` : ''}.${plan.ram_headroom_included ? ` The RAM estimate already includes headroom; ${Number(plan.resources.memory_available_gb).toFixed(2)} GiB is available now.` : ''} The worker checks again before loading.` : plan.blockers.join(' '), plan.ready ? 'ready' : 'blocked'));
  if (plan.smart_phases) {
    const memory = plan.resources;
    target.append(element('p', `Smart phases: ${plan.options.optimizer} on ${plan.options.device}. Requested training scope is preserved. Runtime RAM: ${Number(memory.memory_available_gb).toFixed(2)} GiB free / ${Number(memory.memory_total_gb || 0).toFixed(2)} GiB total. GPU VRAM: ${Number(plan.available_accelerator_gb).toFixed(2)} GiB free / ${Number(plan.total_accelerator_gb).toFixed(2)} GiB total. These are separate memory pools.`));
    if (plan.optimizer_disk_gb) target.append(element('p', `Gradient/optimizer disk workspace: approximately ${plan.optimizer_disk_gb.toFixed(2)} GiB; processed in ${plan.smart_phases.optimizer_buffer_mib} MiB buffers. Checkpoint shards target ${plan.smart_phases.checkpoint_shard_mib} MiB; a single larger tensor stays in one shard.`));
  }
}
async function inspect() {
  const input = expansion();
  if (input.healing_recipe && (!input.healing_recipe.train_file || !input.healing_recipe.eval_file || !input.healing_recipe.data_rights_confirmed)) {
    throw new Error('Set training text, separate evaluation text, and confirm data rights on the Heal tab.');
  }
  const reviewed = await request('preflight', 'POST', input);
  if (JSON.stringify(input) !== JSON.stringify(expansion())) throw new Error('The recipe changed while checking it. Check the current architecture again.');
  state.plan = {...reviewed, input};
  const plan = reviewed.plan; $('plan-results').hidden = false; $('middle').disabled = false;
  $('size-metrics').replaceChildren();
  for (const [value, label] of [[size(plan.original_parameters), 'Source parameters'], [size(plan.expanded_parameters), 'Expanded parameters'], [`${plan.source_layers} → ${plan.expanded_layers}`, 'Transformer layers']]) {
    const tile = element('div', undefined, 'metric'); tile.append(element('strong', value), element('span', label)); $('size-metrics').append(tile);
  }
  $('layer-description').textContent = `${plan.source_layers} source layers + (${plan.count} layer(s) per block × ${plan.copies} extra copies) = ${plan.expanded_layers} layers. Copy from position ${plan.first}–${plan.first + plan.count - 1}, after the original block. Add ${count(plan.added_parameters)} independent parameters. Exact total: ${count(plan.expanded_parameters)}.${state.selectedModel ? ' Using the selected local checkpoint.' : ` Resolved revision: ${plan.revision}.`}`;
  readiness($('plan-readiness'), plan.healing ? {...plan.healing, ready: plan.ready, blockers: plan.blockers} : plan);
  if (plan.healing) $('plan-readiness').append(element('p', `Automatic healing: ${plan.healing.options.steps} steps · ${plan.healing.options.train_scope === 'full' ? 'all parameters' : 'inserted layers'} · ${plan.healing.options.sequence_length} tokens per block.`));
  $('expansion-action').scrollIntoView({block:'center', behavior:'smooth'});
}
$('plan-form').addEventListener('submit', (event) => { event.preventDefault(); action(inspect); });
$('plan-form').addEventListener('input', (event) => {
  if (['model-search','scan-directory'].includes(event.target.id)) return;
  if (event.target.id === 'source') { state.selectedModel = null; $('source-model').value = ''; $('selected-model').hidden = true; }
  invalidateExpansion(); updateButtons();
});
$('configure-auto-heal').addEventListener('click', () => { view('heal'); $('train-file').focus(); });
$('heal-form').addEventListener('input', () => { healingRecipeChanged(); updateButtons(); });
$('heal-parent').addEventListener('change', () => { state.healPlan = null; $('heal-results').hidden = true; updateButtons(); });
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
  if (result.website_dataset) {
    state.website = result.website_dataset; renderWebsite();
    if (state.website.status === 'completed' && !$('train-file').value && !$('eval-file').value) useWebsiteFiles();
  }
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
    for (const job of checkpoints) $(id).add(new Option(`${checkpointName(job)} · ${isHealed(job) ? 'Healed' : 'Expanded'} · ${job.id.slice(0,8)}`, job.id));
    if (checkpoints.some((job) => job.id === selected)) $(id).value = selected;
  }
}
function renderJobs() {
  $('jobs').replaceChildren();
  if (!state.jobs.length) $('jobs').append(element('p', 'No runs yet. Start by checking your source architecture.'));
  for (const job of state.jobs) {
    const card = element('article', undefined, `run ${job.status}`);
    const heading = element('div', undefined, 'run-head'); heading.append(element('strong', `${job.plan?.healing ? 'Expansion & healing' : job.operation === 'expand' ? 'Architecture expansion' : job.operation === 'heal' ? 'Continual pre-training' : 'Prompt test'}${job.operation !== 'probe' && job.evidence ? ` · ${checkpointName(job)}` : ''} · ${job.id.slice(0,8)}`), element('span', job.stage?.startsWith('healing_') && job.status === 'completed' ? job.stage.replaceAll('_', ' ') : job.status, 'status'));
    card.append(heading, element('p', `${new Date(job.created_at * 1000).toLocaleString()} · ${job.message}`));
    const proof = job.evidence;
    if (job.status === 'completed' && proof) {
      if (job.operation === 'probe') card.append(element('p', `Prompt (${proof.prompt_format === 'chat' ? 'chat' : 'raw'}): ${proof.prompt}`), element('div', proof.completion || '(No visible completion tokens)', 'callout'));
      else {
        card.append(element('p', `${count(proof.expanded_parameters)} parameters · reload and finite-output check passed · ${proof.status.replaceAll('_',' ')}`), element('code', job.model_path));
        if (proof.before_evaluation) card.append(element('p', `Held-out loss: ${proof.before_evaluation.loss.toFixed(4)} → ${proof.after_evaluation.loss.toFixed(4)} (${proof.loss_improved ? 'lower' : 'did not improve'}). ${count(proof.training_tokens)} token exposures; ${proof.repeated_passes} repeated pass(es). Broad quality still needs review.`));
        if (proof.source_evaluation && proof.after_evaluation) {
          const sourceLoss = proof.source_evaluation.loss;
          const healedLoss = proof.after_evaluation.loss;
          card.append(element('p', `Starting checkpoint loss: ${sourceLoss.toFixed(4)}. The healed loss is ${healedLoss > sourceLoss ? 'higher' : healedLoss < sourceLoss ? 'lower' : 'the same'} on the same text.`));
        }
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
  if (JSON.stringify(state.plan.input) !== JSON.stringify(expansion())) throw new Error('The recipe changed. Check the current plan again.');
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
  healingRecipeChanged();
}));
$('probe-form').addEventListener('submit', (event) => { event.preventDefault(); action(async () => {
  await request('jobs','POST',{operation:'probe',parent_id:$('probe-parent').value,prompt:$('prompt').value,prompt_format:$('prompt-format').value,max_new_tokens:$('new-tokens').value});
  await refresh(); view('history');
}); });
setInterval(() => { if (state.connected && !state.busy && active()) action(refresh); }, 2500);
function renderWebsite() {
  const build = state.website;
  if (!build) return;
  const target = $('website-status'); target.hidden = false; target.replaceChildren();
  target.append(element('strong', build.message));
  const collecting = ['queued','running'].includes(build.status);
  $('website-cancel').hidden = !collecting;
  $('website-download').hidden = build.status !== 'completed';
  $('website-use').hidden = build.status !== 'completed';
  if (collecting) target.append(element('p', `${build.pages_checked || 0} URLs checked · ${build.documents || 0} documents saved · ${build.current_url || 'Starting…'}`));
  if (build.result) {
    const result = build.result, coverage = result.coverage;
    target.append(element('p', `${coverage.documents} documents · ${coverage.training_documents} training / ${coverage.evaluation_documents} evaluation · ${coverage.store_links} app-store links · ${coverage.domains.length} domains. ${coverage.failures.length} collection notes; ${coverage.pending_urls} discovered URLs remain.`));
    target.append(element('p', `Reusable archive: ${result.archive}`));
    if (coverage.budget_reached || coverage.failures.length) target.append(element('p', 'Review manifest.json in the ZIP for coverage, blocked pages, failed requests, and source terms. This snapshot does not claim every page was collected.'));
    if (result.training_blocker) target.append(element('p', `Dataset is ready; full training did not start: ${result.training_blocker}`, 'blocked'));
    if (result.healing_job) target.append(element('p', `Full-model healing run: ${result.healing_job.slice(0,8)}. Follow progress in Run history.`));
  }
}
$('website-build').addEventListener('click', () => action(async () => {
  const auto = $('website-auto').checked;
  const recipe = healing();
  if (auto && (!recipe.parent_id || !recipe.data_rights_confirmed)) throw new Error('For automatic training, select a verified parent and confirm data rights below before collecting.');
  state.website = await request('website-build','POST',{max_pages:$('website-pages').value,seeds:$('website-seeds').value.split(/\r?\n/).map((line) => line.trim()).filter(Boolean),auto_train:auto,healing_recipe:recipe});
  renderWebsite();
}));
$('website-cancel').addEventListener('click', () => action(async () => {
  await request('website-status','POST',{id:state.website.id,cancel:true});
  $('website-status').append(element('p', 'Cancellation requested. The current network request may take up to 20 seconds to finish.'));
}));
$('website-download').addEventListener('click', () => action(async () => {
  const result = await request('website-status','POST',{id:state.website.id,download:true});
  const bytes = Uint8Array.from(atob(result.base64), (character) => character.charCodeAt(0));
  const url = URL.createObjectURL(new Blob([bytes],{type:'application/zip'}));
  const link = element('a'); link.href = url; link.download = result.filename; document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url),30000);
}));
function useWebsiteFiles() {
  if (state.website?.status !== 'completed') return;
  $('train-file').value = state.website.result.train_file; $('eval-file').value = state.website.result.eval_file;
  healingRecipeChanged(); updateButtons();
}
$('website-use').addEventListener('click', () => { useWebsiteFiles(); view('heal'); $('heal-parent').scrollIntoView({block:'center'}); $('heal-parent').focus(); });
$('full-gpu-pilot').addEventListener('click', () => {
  const gpu = [...$('device').options].find((option) => option.value.startsWith('cuda:'));
  if (!gpu) { error('No CUDA GPU is available to this runtime. Choose CPU with standard AdamW or update GPU access first.'); updateButtons(); return; }
  $('device').value = gpu.value; $('train-scope').value = 'full'; $('optimizer').value = 'auto';
  for (const [id,value] of Object.entries({steps:100,'sequence-length':256,'learning-rate':.00001,accumulation:1,'eval-blocks':8})) $(id).value = value;
  healingRecipeChanged(); error(); updateButtons();
  $('heal-parent').scrollIntoView({block:'center'});
});
setInterval(async () => {
  if (!state.connected || state.websitePolling || !state.website || !['queued','running'].includes(state.website.status)) return;
  state.websitePolling = true;
  try {
    state.website = await request('website-status','POST',{id:state.website.id}); renderWebsite();
    if (state.website.status === 'completed') {
      useWebsiteFiles();
      if (state.website.result.healing_job || state.website.result.training_blocker) $('train-scope').value = 'full';
      await refresh();
    }
    updateButtons();
  } catch (e) { error(e.message); }
  finally { state.websitePolling = false; }
},2000);
updateButtons();
