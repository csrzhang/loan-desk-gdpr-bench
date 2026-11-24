import {escapeText as esc, inlineText, articleLinks, gdprIndex, evaluateVerdicts} from './presentation.mjs';
const main = document.querySelector('#main');
const stages = { policy_scan: 'Interpret obligation', locus_finder: 'Locate source', control_verifier: 'Verify controls', counterexample_review: 'Challenge finding', regulatory_arbiter: 'Issue verdict', anchor_repair: 'Validate citations' };
const walkthrough = { scope: 'Read scoped obligation', observation: 'Inspect test receipt', decision: 'Open reference finding' };
const models = { 'deepseek-flash': 'DeepSeek Flash', 'deepseek-v4-pro': 'DeepSeek Pro' };
const titles = ['Data minimization', 'Purpose limitation', 'Consent to processing', 'Consent withdrawal', 'Collection notices', 'Right of access', 'Right to rectification', 'Right to erasure', 'Restriction of processing', 'Data portability', 'Marketing objection', 'Case confidentiality', 'Human intervention'];
const sourceNames = { replay: 'Recorded replay', reference: 'Reference walkthrough', live: 'Live inference' };
const laws = {
  GDPR: ['European Union', 'General Data Protection Regulation', gdprIndex],
  CCPA: ['California', 'California Consumer Privacy Act, as amended by the CPRA', 'https://cppa.ca.gov/pdf/20260101_ccpa_statute.pdf'],
  PDPO: ['Hong Kong', 'Personal Data (Privacy) Ordinance', 'https://www.elegislation.gov.hk/hk/cap486'],
  PIPL: ['China', 'Personal Information Protection Law', 'https://www.cac.gov.cn/2021-08/20/c_1631050028355286.htm'],
  EUAI: ['European Union', 'EU Artificial Intelligence Act', 'https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng']
};
const apps = ['Loan Desk', 'Clinic Portal', 'Retail Rewards'];
const baseline = 'PriAgent regulatory-v2';
const choices = { app: apps[0], law: 'GDPR', snapshot: 'base', ids: new Set(['GDPR01']), model: 'deepseek-flash', mode: 'replay', archive: 'flash-01' };
const filters = { snapshot: 'all', type: 'models', oid: 'all' };
const dateFormat = new Intl.DateTimeFormat('en-GB', {day:'2-digit', month:'short', year:'numeric', hour:'2-digit', minute:'2-digit', second:'2-digit', timeZoneName:'short'});
const runDate = run => run.created ? dateFormat.format(run.created * 1000) : 'Imported archive';
const runById = id => catalog.runs.find(entry => entry.id === id);
const modelName = id => models[id] || id;
const runHref = id => '#run/' + encodeURIComponent(id);
const statusName = {complete:'Complete', partial:'Partial', failed:'Interrupted', running:'In progress'};
let catalog, active = null, pageRevision = 0, working = false;
const sourceCache = new Map();
document.querySelector('.skip').addEventListener('click', event => {
  event.preventDefault();
  main.focus();
});
const byId = id => document.getElementById(id);
const rule = id => catalog.rules.find(r => r.obligation_id === id);
const title = id => titles[Number(id.slice(-2)) - 1];
const name = s => s === 'base' ? 'Base' : s;
const opts = (items, value) => items.map(([k, label, disabled]) => '<option value="' + esc(k) + '" ' + (k === value ? 'selected' : '') + (disabled ? ' disabled' : '') + '>' + esc(label) + '</option>').join('');
const reportLink = (a, s, o) => '#report/' + [a, s, o].map(encodeURIComponent).join('/');
const link = (s, text, cls = '') => '<a class="' + cls + '" href="' + esc(s) + '">' + esc(text) + '</a>';
const field = (label, id, options, value, disabled = false) => '<div class="field"><label class="formlabel" for="' + id + '">' + label + '</label><select class="select" id="' + id + '" ' + (disabled ? 'disabled' : '') + '>' + opts(options, value) + '</select></div>';
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
async function api(path, params = {}, options = {}) {
  const query = new URLSearchParams(params).toString();
  const response = await fetch(query ? path + '?' + query : path, options);
  const data = await response.json();
  if (!response.ok) throw Error(data.error || 'Request failed.');
  return data;
}
function go(hash) { if (location.hash === hash) render(); else location.hash = hash; }
function hero(crumb, heading, sub, aside = '') {
  return '<div class="hero"><div><div class="crumb">App Zoo <span>/</span> ' + esc(crumb) + '</div><h1>' + esc(heading) + '</h1><p class="sub">' + esc(sub) + '</p></div>' + aside + '</div>';
}
function badge(verdict) {
  const labels = { SUPPORTED: ['good', '✓', 'Supported'], CONTRADICTED: ['bad', '×', 'Contradicted'], INSUFFICIENT: ['unknown', '?', 'Insufficient'], NOT_APPLICABLE: ['', '–', 'Not applicable'] };
  const [cls, symbol, word] = labels[verdict] || ['', '', 'Pending'];
  return '<span class="pill ' + cls + '">' + symbol + ' ' + word + '</span>';
}
function workspace() {
  const c = choices;
  const supported = c.app === 'Loan Desk' && c.law === 'GDPR';
  const recordedRuns = catalog.runs.filter(run => run.model === c.model && run.findings.some(f => f.snapshot === c.snapshot));
  const recording = recordedRuns.find(run => run.id === c.archive) || recordedRuns[0];
  c.archive = recording?.id || '';
  const available = recording?.findings.filter(f => f.snapshot === c.snapshot && c.ids.has(f.oid)).length || 0;
  const canRun = supported && c.ids.size > 0 && (c.mode !== 'replay' || available === c.ids.size);
  const busy = active?.status === 'running';
  const [, lawTitle, url] = laws[c.law];
  const appField = field('Application', 'app', apps.map(a => [a, a === apps[0] ? a : a + ' · preview']), c.app);
  const lawField = field('Regulation', 'law', Object.entries(laws).map(([id, info]) =>
    [id, id + ' · ' + info[0] + (id === 'GDPR' ? '' : ' · preview')]), c.law);
  const item = r => `<div class="choice obligation">
    <input type="checkbox" id="pick-${r.obligation_id}" value="${r.obligation_id}" ${c.ids.has(r.obligation_id) ? 'checked' : ''}>
    <div><label for="pick-${r.obligation_id}"><span class="oid">${r.obligation_id}</span><strong>${esc(title(r.obligation_id))}</strong></label>
    <div class="articles">${articleLinks(r.article)}</div></div></div>`;
  const scope = supported ? `<div class="section-head"><h3>Obligations</h3><div class="actions">
    <button id="all" class="textbtn">Select all</button><button id="clear" class="textbtn">Clear</button></div></div>
    <div class="choices">${catalog.rules.map(item).join('')}</div>` :
    `<div class="preview-note"><h3>Catalogue preview</h3><p>${esc(c.app)} × ${esc(c.law)} has no runnable cases yet.</p>
      <button class="secondary" id="demo-scope">Use Loan Desk with GDPR</button></div>`;
  let help = c.mode === 'live' ? 'Uses the selected model provider. Live requests may incur usage charges.' :
    c.mode === 'reference' ? 'Explore reviewed findings and recorded test observations offline.' :
    `This recording covers ${available} of ${c.ids.size} selected obligation${c.ids.size === 1 ? '' : 's'}.`;
  if (!supported) help = 'Live and offline audits are available for Loan Desk with GDPR.';
  const backend = c.mode === 'reference' ? [['none','Offline · no model']] :
    [...Object.entries(models), ['openai','OpenAI · GPT (planned)',true], ['anthropic','Anthropic · Claude (planned)',true]];
  main.innerHTML = hero('Research workspace', 'Configure an audit', 'Choose an application, legal scope and evaluation method.',
    '<div class="app-picker">' + appField + '</div>') +
    `<div class="workspace"><section class="panel"><div class="panelhead"><h2>Audit scope</h2>${supported ? '<span class="count">'+c.ids.size+' of 13 selected</span>' : ''}</div>
    <div class="scopeinner"><div class="law-picker">${lawField}<a target="_blank" rel="noopener noreferrer" href="${url}">${esc(lawTitle)}</a></div>${scope}</div></section>
    <aside class="setup"><div class="panelhead"><h2>Run setup</h2></div><div class="ins">` +
    field('Source snapshot','snapshot', c.app === apps[0] ? catalog.snapshots.map(s => [s, s === 'base' ? 'Base · original' : 'Mutation · '+s]) : [['none','No snapshots available']], c.app === apps[0] ? c.snapshot : 'none',!supported) +
    field('Run mode','mode',Object.entries(sourceNames),c.mode,!supported) +
    field('Baseline','baseline',c.mode === 'reference' ? [['ref','Reviewed reference']] : [['pri',baseline]],c.mode === 'reference' ? 'ref' : 'pri',!supported || c.mode === 'reference') +
    field('Backend model','model',backend,c.mode === 'reference' ? 'none' : c.model,!supported || c.mode === 'reference') +
    (c.mode === 'replay' && supported ? field('Recording','archive',recordedRuns.length ? recordedRuns.map(r => [r.id,runDate(r)+' · '+r.id]) : [['','No recording available']], c.archive,!recordedRuns.length) : '') +
    `<div class="rundiv"></div><p class="help">${esc(help)}</p><button class="primary" id="start" ${!canRun || working || busy ? 'disabled' : ''}>${{replay:'Play recorded run', live:'Start live audit', reference:'Start walkthrough'}[c.mode]}</button>` +
    (busy ? '<p class="help"><a class="light" href="#activity">View active run</a></p>' : '') +
    (supported && c.mode === 'replay' && available<c.ids.size ? '<p class="help">Choose another recording, Live inference or Reference walkthrough for this selection.</p>' : '') +
    '<div id="setup-error" role="alert"></div></div></aside></div>';
  const repaint = id => { workspace(); byId(id)?.focus({preventScroll:true}); };
  if (supported) {
    byId('all').onclick = () => { c.ids=new Set(catalog.rules.map(r=>r.obligation_id)); repaint('all'); };
    byId('clear').onclick = () => { c.ids.clear(); repaint('clear'); };
    main.querySelectorAll('.choice input').forEach(box => box.onchange = () => {
      if (box.checked) c.ids.add(box.value); else c.ids.delete(box.value);
      repaint(box.id);
    });
  } else byId('demo-scope').onclick = () => { c.law='GDPR'; c.app=apps[0]; repaint('law'); };
  for (const key of ['app','law','snapshot','mode','model','archive']) {
    const select = byId(key);
    if (select) select.onchange = e => { c[key]=e.target.value; repaint(key); };
  }
  byId('start').onclick=start;
}
async function start() {
  if (working || active?.status === 'running') return;
  working = true; byId('start').disabled = true;
  const run = { app: choices.app, law: choices.law, archive: choices.archive, snapshot: choices.snapshot, model: choices.model, mode: choices.mode, ids: [...choices.ids].sort(), done: [], events: [], status: 'running', started: Date.now() };
  try {
    if (run.mode === 'live') {
      const res = await api('/api/live', {}, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ app: run.app, law: run.law, baseline, snapshot: run.snapshot, model: run.model, obligations: run.ids }) });
      run.archive = res.id;
    }
    active = run; sessionStorage.setItem('studio-live', run.mode === 'live' ? JSON.stringify(run) : '');
    go('#activity');
    if (run.mode === 'live') await poll(run); else await playback(run);
  } catch (e) {
    if (active === run) { run.status = 'failed'; run.finished = Date.now(); run.error = e.message; refreshActivity(); }
    else if (byId('setup-error')) byId('setup-error').textContent = e.message;
  } finally { working = false; if (!location.hash || location.hash === '#workspace') workspace(); }
}
function refreshActivity() {
  if (location.hash === '#activity') activity();
  else if (active?.mode === 'live' && location.hash === runHref(active.archive) && runById(active.archive)) {
    runDetail(active.archive, byId('mismatch-only')?.checked);
  }
}
async function playback(run) {
  for (const id of run.ids) {
    run.current = id;
    const archive = run.mode === 'reference' ? 'reference' : run.archive;
    const rep = await api('/api/report', { snapshot: run.snapshot, oid: id, archive });
    const steps = run.mode === 'replay' ? rep.stages : Object.keys(walkthrough).map((stage, i) => ({ stage, note: [rep.rule.title, 'Validated business observations available', rep.verdict][i] }));
    for (const s of steps) {
      const event = { oid: id, stage: s.stage, status: 'running', note: '', seconds: s.seconds };
      run.events.push(event); refreshActivity();
      await wait(run.mode === 'replay' ? Math.max(400, Math.min(s.seconds * 250, 1400)) : 450);
      Object.assign(event, { status: 'done', note: s.note }); refreshActivity();
    }
    run.done.push({ id, archive, verdict:rep.verdict, reference:catalog.references[run.snapshot][id] }); refreshActivity();
  }
  run.status = 'complete'; run.finished = Date.now(); refreshActivity();
}
async function poll(run) {
  let lost = 0;
  while (run.status === 'running') {
    let data;
    try { data = await api('/api/status', { id: run.archive }); lost = 0; }
    catch (e) { if (++lost >= 5) throw e; await wait(1000); continue; }
    run.current = data.current; run.events = data.events; run.status = data.status; run.error = data.error;
    if (run.status !== 'running') run.finished = Date.now();
    if (data.completed.length !== run.done.length || run.status !== 'running') catalog = await api('/api/catalog');
    const saved = runById(run.archive)?.findings || [];
    run.done = data.completed.map(id => ({ id, archive: run.archive, ...saved.find(f => f.oid===id && f.snapshot===run.snapshot) })); refreshActivity();
    if (run.status === 'running') await wait(850);
  }
  sessionStorage.removeItem('studio-live'); refreshActivity();
}
function activity() {
  const r = active; if (!r) { main.innerHTML = hero('Run activity', 'No active run', 'Configure a selection or open a saved report.') + link('#workspace', 'Configure audit', 'secondary'); return; }
  const done = r.done.length, total = r.ids.length, id = r.current || r.ids[0];
  const steps = r.mode === 'reference' ? walkthrough : stages;
  const phase = r.status === 'complete' ? 'Run complete' : r.status === 'failed' ? 'Run interrupted' : 'Run in progress';
  const mode = r.mode === 'reference' ? 'Verified reference · offline' : r.mode === 'replay' ? 'Recorded model activity · accelerated playback' : 'Live model activity';
  const entries = Object.entries(steps).filter(([k]) => k !== 'anchor_repair' || r.events.some(e => e.stage === k));
  const timeline = entries.map(([key, label]) => {
    const ev = r.events.filter(e => e.oid === id && e.stage === key).at(-1);
    const state = r.status === 'failed' && ev?.status === 'running' ? 'interrupted' : ev?.status || 'pending';
    return '<li class="' + state + '"><i class="state"></i><div>' + esc(label) + (ev?.note ? '<small class="note">' + esc(ev.note) + '</small>' : '') + '</div><b>' + esc(ev?.seconds && state === 'done' ? ev.seconds.toFixed(1) + 's' : state) + '</b></li>';
  }).join('');
  main.innerHTML = hero(sourceNames[r.mode], phase, mode + ' · ' + name(r.snapshot) + (r.mode === 'reference' ? '' : ' · ' + models[r.model])) +
    '<div class="summary"><div><span class="sourceflag">' + done + ' / ' + total + '</span> obligations complete</div><span class="mono mini">' + Math.floor(((r.finished || Date.now()) - r.started) / 1000) + 's elapsed</span><progress class="progress" aria-label="Completed obligations" max="' + total + '" value="' + done + '"></progress></div>' +
    (r.mode !== 'reference' && r.done.length ? evaluationPanel(r.done,total) : '') +
    (r.mode !== 'reference' && r.archive && runById(r.archive) ? '<div class="activity-run">'+link(runHref(r.archive),'Open saved run results')+' · <code>'+esc(r.archive)+'</code></div>' : '') +
    (r.error ? '<div class="callout alert" role="alert">' + esc(r.error) + (done ? ' Open the completed reports below.' : ' This run produced no report.') + '</div>' : '') +
    '<div class="layout2"><section class="reportbody"><h2>Audit queue</h2><div class="queue">' + r.ids.map(k => {
      const found = r.done.find(o => o.id === k);
      return '<div class="qitem"><div><small>' + k + '</small>' + esc(title(k)) + '</div>' + (found ? '<div class="actions">'+(r.mode==='reference'?'':comparisonTag(found.verdict,found.reference))+link(reportLink(found.archive, r.snapshot, k), 'View report')+'</div>' : esc(r.status === 'failed' ? 'Incomplete' : k === id ? 'Running' : 'Queued')) + '</div>';
    }).join('') + '</div></section><section class="reportbody"><div class="eyeline">' + id + '</div><h2>' + esc(title(id)) + '</h2><ol class="timeline">' + timeline + '</ol></section></div><div class="reportnav">' + link('#workspace', 'Configure another audit', 'secondary') + link('#library', 'Report library', 'secondary') + '</div>';
}
function comparisonTag(verdict, reference) {
  if (!verdict || !reference) return '';
  const match = verdict === reference;
  return '<span class="agreement '+(match?'match':'different')+'">'+(match?'Match':'Mismatch')+'</span>';
}
function evaluationPanel(findings, planned) {
  const m = evaluateVerdicts(findings);
  const percent = value => value === null ? 'N/A' : (value*100).toLocaleString('en-US',{maximumFractionDigits:1})+'%';
  const stats = [
    ['Coverage',m.count+' / '+planned,'Completed / scheduled'],
    ['Verdict agreement',m.matches+' / '+m.count,'Exact verdict matches'],
    ['Precision',percent(m.precision),m.tp+' correct / '+(m.tp+m.fp)+' flagged'],
    ['Recall',percent(m.recall),m.tp+' found / '+(m.tp+m.fn)+' reference violations'],
    ['F1',percent(m.f1),'Violation detection']
  ];
  return `<section class="evaluation"><div class="section-head"><h2>Run evaluation</h2><span class="mini">Against verified references</span></div>
    <div class="metric-grid">${stats.map(([label,value,note])=>`<div><span>${label}</span><strong>${value}</strong><small>${note}</small></div>`).join('')}</div>
    <details class="metric-details"><summary>How these scores are calculated</summary><p>
    Each completed obligation contributes once. A <code>CONTRADICTED</code> verdict flags a violation.
    Precision measures how many flags were correct. Recall measures how many reference violations were found.
    F1 is 2TP / (2TP + FP + FN). N/A indicates a zero denominator.
    An unresolved prediction counts as an unflagged case and a missed violation when the reference is contradicted.
    Missing predictions affect coverage only. These scores evaluate verdicts; evidence and explanations require separate review.</p>
    <div class="tally">${m.tp} true positives · ${m.fp} false positives · ${m.fn} false negatives · ${m.tn} true negatives · ${m.unresolved} unresolved predictions</div>
    </details></section>`;
}
function comparisonTable(rows,archive) {
  if (!rows.length) return '<p class="empty">No findings match this view.</p>';
  return `<div class="table-scroll"><table class="findings"><thead><tr><th>Obligation</th><th>Snapshot</th><th>Model verdict</th><th>Reference</th><th>Comparison</th></tr></thead><tbody>${rows.map(f=>
    `<tr><td>${link(reportLink(archive,f.snapshot,f.oid),title(f.oid))}<small>${f.oid}</small></td><td>${esc(name(f.snapshot))}</td>
    <td>${badge(f.verdict)}</td><td>${badge(f.reference)}</td><td>${comparisonTag(f.verdict,f.reference)}</td></tr>`).join('')}</tbody></table></div>`;
}
function library() {
  const f=filters, isModel=f.type==='models';
  const matches=entry=>(f.snapshot==='all'||entry.snapshot===f.snapshot)&&(f.oid==='all'||entry.oid===f.oid);
  const runCards=catalog.runs.filter(r=>r.plan.some(matches)).map(r=>{
    const snapshots=[...new Set(r.plan.map(p=>name(p.snapshot)))];
    const m=evaluateVerdicts(r.findings);
    return `<a class="run-card" href="${runHref(r.id)}"><div class="run-main"><strong>${esc(modelName(r.model))}</strong>
    <span>${esc(r.baseline)} · ${esc(r.app)} · ${esc(snapshots.length===1?snapshots[0]:snapshots.length+' snapshots')}</span>
    <small>${esc(runDate(r))} · <code>${esc(r.id)}</code></small></div><div class="run-result"><b>${esc(statusName[r.status]||r.status)}</b>
    <span>${r.findings.length} / ${r.plan.length} completed</span>${m.count?'<small>'+m.matches+' / '+m.count+' verdicts match</small>':''}</div></a>`;
  });
  const refs=catalog.snapshots.flatMap(snapshot=>catalog.rules.map(r=>({snapshot,oid:r.obligation_id}))).filter(matches);
  const refCards=()=>refs.map(r=>`<a class="reference-row" href="${reportLink('reference',r.snapshot,r.oid)}"><span class="oid">${r.oid}</span>
    <strong>${esc(title(r.oid))}</strong><span>${esc(name(r.snapshot))}</span>${badge(catalog.references[r.snapshot][r.oid])}</a>`).join('');
  main.innerHTML=hero('Library','Report library','Browse model runs or inspect the reviewed reference for a single case.')+
    `<div class="source-tabs" role="group" aria-label="Report source"><button id="tab-models" aria-pressed="${isModel}">Model runs <span>${catalog.runs.length}</span></button>
    <button id="tab-references" aria-pressed="${!isModel}">Verified references <span>${catalog.snapshots.length*catalog.rules.length}</span></button></div>
    <section class="summary filters">`+field('Snapshot','filter-snapshot',[['all','All snapshots'],...catalog.snapshots.map(s=>[s,name(s)])],f.snapshot)+
    field('Obligation','filter-oid',[['all','All obligations'],...catalog.rules.map(r=>[r.obligation_id,r.obligation_id+' · '+title(r.obligation_id)])],f.oid)+
    '<span class="count">'+(isModel?runCards.length+' runs':refs.length+' references')+'</span></section>'+
    '<div class="rowlist">'+(isModel?runCards.join(''):refCards()||'')+'</div>';
  if (!(isModel?runCards:refs).length) main.querySelector('.rowlist').innerHTML='<p class="empty">No results match these filters.</p>';
  for (const id of ['models','references']) byId('tab-'+id).onclick=()=>{f.type=id;history.replaceState(null,'','#library/'+id);library();byId('tab-'+id).focus();};
  for (const key of ['snapshot','oid']) byId('filter-'+key).onchange=e=>{f[key]=e.target.value;library();byId('filter-'+key).focus();};
}
function runDetail(id, mismatches=false) {
  const r=runById(id);
  if(!r) throw Error('This run is unavailable.');
  const diffs=r.findings.filter(f=>f.verdict!==f.reference);
  const snaps=[...new Set(r.plan.map(f=>name(f.snapshot)))].join(', ');
  main.innerHTML=hero('Report library','Run results',r.app+' · '+snaps+' · '+r.law)+
    `<div class="summary run-meta"><div><span class="mini">Baseline</span><strong>${esc(r.baseline)}</strong></div>
    <div><span class="mini">Backend model</span><strong>${esc(modelName(r.model))}</strong></div>
    <div><span class="mini">Run ID</span><code>${esc(r.id)}</code></div><div><span class="mini">${esc(statusName[r.status]||r.status)}</span>${esc(runDate(r))}</div></div>`+
    evaluationPanel(r.findings,r.plan.length)+
    `<section class="panel"><div class="panelhead"><h2>Obligation results</h2><label class="toggle"><input id="mismatch-only" type="checkbox" ${mismatches?'checked':''}> Mismatches only (${diffs.length})</label></div>
    ${comparisonTable(mismatches?diffs:r.findings,id)}</section><div class="reportnav">${link('#library','Report library','secondary')}</div>`;
  byId('mismatch-only').onchange=e=>{runDetail(id,e.target.checked);byId('mismatch-only').focus();};
}
function observedFields(obj, prefix = '') {
  return Object.entries(obj).flatMap(([k, v]) => {
    const key = (prefix ? prefix + ' / ' : '') + k.replaceAll('_', ' ');
    if (v && typeof v === 'object' && !Array.isArray(v)) return observedFields(v, key);
    const value = Array.isArray(v) ? v.join(' · ') || 'None' : v === null ? 'None' : v === true ? 'Yes' : v === false ? 'No' : String(v);
    return [[key, value]];
  });
}
function observation(obj) {
  return observedFields(obj).map(([key, value]) => '<div class="observation"><span>' + esc(key) + '</span><b>' + esc(value) + '</b></div>').join('');
}
function compareCases(original, current) {
  const before = new Map(observedFields(original.observed));
  const after = new Map(observedFields(current.observed));
  const keys = [...new Set([...before.keys(), ...after.keys()])].filter(k => before.get(k) !== after.get(k));
  const rows = keys.map(k => '<tr><th scope="row">' + esc(k) + '</th><td>' + esc(before.get(k) ?? 'Absent') + '</td><td>' + esc(after.get(k) ?? 'Absent') + '</td></tr>').join('');
  return '<div class="callout"><strong>Base reference</strong> ' + badge(original.verdict) + '</div>' +
    (keys.length ? '<table class="compare"><caption>Changed test observations</caption><thead><tr><th>Observation</th><th>Base</th><th>' + esc(current.snapshot) + '</th></tr></thead><tbody>' + rows + '</tbody></table>' : '<p class="reason">The recorded test observations match Base.</p>') +
    link(reportLink('reference', 'base', current.rule.obligation_id), 'Inspect Base evidence');
}
async function sourceLines(snapshot, path) {
  const key = snapshot + '/' + path;
  if (!sourceCache.has(key)) sourceCache.set(key, (await api('/api/source', { snapshot, path })).lines);
  return sourceCache.get(key);
}
async function showCode(host, e, snap, expanded = false) {
  try {
    const lines = await sourceLines(snap, e.path), a = e.start_line, b = e.end_line;
    const start = expanded ? 1 : Math.max(1, a - 2), end = expanded ? lines.length : Math.min(lines.length, b + 2);
    host.innerHTML = '<pre class="code" tabindex="0" aria-label="Source excerpt">' + lines.slice(start - 1, end).map((v, i) => {
      const n = start + i;
      return '<span class="cline ' + (n >= a && n <= b ? 'hit' : '') + '"><em>' + n + '</em>' + esc(v || ' ') + '</span>';
    }).join('') + '</pre><button class="textbtn expand-file">' + (expanded ? 'Show excerpt' : 'Show full file') + '</button>';
    if (expanded) {
      const pane = host.querySelector('pre');
      pane.scrollTop = Math.max(0, (a - 3) * parseFloat(getComputedStyle(pane).lineHeight));
    }
    host.querySelector('button').onclick = () => showCode(host, e, snap, !expanded);
  } catch (err) { host.textContent = err.message; }
}
function explanation(text) {
  const parts=text.split(/(?:^|\s+)(Code facts|Requirement|Justification):\s*/i);
  if(parts.length<3) return '<p class="reason">'+inlineText(text)+'</p>';
  const sections=[];
  if(parts[0].trim()) sections.push('<p class="reason">'+inlineText(parts[0])+'</p>');
  const headings={'justification':'Why this verdict','requirement':'Requirement','code facts':'Behavior in code'};
  const entries=[];
  for(let i=1;i<parts.length;i+=2) entries.push([parts[i].toLowerCase(),parts[i+1]]);
  for(const [key,label] of Object.entries(headings)) {
    for(const [,body] of entries.filter(([name])=>name===key)) {
      sections.push('<div class="block"><h3>'+label+'</h3><p>'+inlineText(body)+'</p></div>');
    }
  }
  return sections.join('');
}
async function detail(archive,snap,id,rev) {
  const r=await api('/api/report',{snapshot:snap,oid:id,archive});
  if(rev!==pageRevision) return;
  const ref=archive==='reference';
  const comparison=ref ? `<div class="summary report-summary"><div><span class="mini">Verified reference verdict</span> ${badge(r.verdict)}</div><span class="mini">Reviewed source and recorded test observations</span></div>` :
    `<section class="verdict-strip" aria-label="Verdict comparison"><div><span>Model verdict</span>${badge(r.verdict)}</div>
    <div><span>Verified reference</span>${badge(r.reference_verdict)}</div><div><span>Verdict agreement</span>${comparisonTag(r.verdict,r.reference_verdict)}</div>
    <div>${link(reportLink('reference',snap,id),'Inspect reference report')}</div></section>
    <div class="report-meta"><span>Baseline <b>${esc(r.baseline)}</b></span><span>Model <b>${esc(modelName(r.model))}</b></span>
    <span>Run ${link(runHref(archive),archive)} · ${esc(runDate(r))}</span></div>`;
  const checks=r.evidence_check;
  const screen=checks ? `<details class="screen"><summary>Evidence checks · ${checks.covered?'Reviewed route covered':'Review coverage'}</summary>
    <p>${checks.errors} citation issues. ${checks.covered} of ${checks.routes} reviewed evidence routes have all required source lines.
    Alternative evidence and the meaning of each citation require review.</p></details>` : '';
  main.innerHTML=`<div class="crumb">${link(ref?'#library/references':'#library/models','Report library')}<span>/</span>${esc(name(snap))}<span>/</span>${esc(id)}</div>
    <h1 class="titlelong">${esc(title(id))}</h1><div class="report-law">Loan Desk · ${esc(name(snap))} · <a href="${gdprIndex}" target="_blank" rel="noopener noreferrer">GDPR</a> <span class="articles">${articleLinks(r.rule.article)}</span></div>
    ${comparison}<div class="layout2"><section class="reportbody"><h2>Explanation</h2>
    ${explanation(r.explanation)}<details class="scope-detail"><summary>Scenario and scoped requirement</summary>
    <div class="block"><h3>Scenario</h3><p>${inlineText(r.rule.scenario)}</p></div><div class="block"><h3>Scoped requirement</h3><p>${inlineText(r.requirement)}</p></div></details>
    ${ref ? '<div class="block"><h3>Observed in test</h3>'+observation(r.observed)+'</div>'+(snap==='base'?'':'<button class="secondary" id="reveal">Compare with Base</button><div id="comparison"></div>') : ''}
    </section><section class="reportbody"><div class="evidence-head"><h2>Source evidence</h2><span class="count">${r.evidence.length} citations</span></div>
    ${screen}${r.evidence.map((e,i)=>`<details class="ev" ${i?'':'open'}><summary><code>${esc(e.path)}</code> · L${e.start_line}–${e.end_line}</summary>
    <p class="reason">${inlineText(e.supports)}</p><div class="excerpt"></div></details>`).join('')}</section></div>
    <div class="reportnav">${!ref?link(runHref(archive),'Run results','secondary'):''}${link(ref?'#library/references':'#library/models','Report library','secondary')}${active?link('#activity','Run activity','secondary'):''}</div>`;
  main.querySelectorAll('.ev').forEach((node,i)=>{
    const fill=()=>{const host=node.querySelector('.excerpt');if(node.open&&!host.hasChildNodes())showCode(host,r.evidence[i],snap);};
    node.ontoggle=fill;fill();
  });
  if(byId('reveal')) byId('reveal').onclick=async e=>{
    e.target.disabled=true;
    try{const base=await api('/api/report',{snapshot:'base',oid:id,archive:'reference'});
      if(rev===pageRevision) byId('comparison').innerHTML=compareCases(base,r);
    }catch(err){if(rev===pageRevision) byId('comparison').textContent=err.message;}
  };
}
async function render() {
  if (!catalog) return;
  const rev = ++pageRevision;
  const [view = 'workspace', a, s, o] = (location.hash.slice(1) || 'workspace').split('/');
  byId('nav-workspace').classList.toggle('on', view === 'workspace' || view === 'activity');
  byId('nav-library').classList.toggle('on', view === 'library' || view === 'report' || view === 'run');
  try {
    if (view === 'library') { if (['models','references'].includes(a)) filters.type=a; catalog = await api('/api/catalog'); if (rev === pageRevision) library(); }
    else if (view === 'run') { catalog = await api('/api/catalog'); if(rev===pageRevision) runDetail(a); }
    else if (view === 'report') { main.innerHTML = '<p>Opening report…</p>'; await detail(a, s, o, rev); }
    else if (view === 'activity') activity();
    else workspace();
  } catch (err) { if (rev === pageRevision) main.innerHTML = '<div class="callout alert">' + esc(err.message) + '</div>' + link('#workspace', 'Return to workspace'); }
}
window.addEventListener('hashchange', () => { window.scrollTo(0, 0); render(); });
setInterval(() => {
  if (active?.status === 'running' && location.hash === '#activity') {
    const clock = main.querySelector('.summary .mono'); if (clock) clock.textContent = Math.floor((Date.now() - active.started) / 1000) + 's elapsed';
  }
}, 1000);
(async () => {
  try { catalog = await api('/api/catalog'); const stored = sessionStorage.getItem('studio-live'); if (stored) { active = JSON.parse(stored); poll(active).catch(e => { active.status = 'failed'; active.error = e.message; refreshActivity(); }); } await render(); }
  catch (err) { main.textContent = err.message; }
})();
