'use strict';
/* OpenTwin OS additive UI. Governance prepares context only; exact-preview approval remains mandatory. */

const OS_FIXED_TABS = [
  ['command', '🏠 My Command'], ['news', '📰 Open News'], ['ai-code', '🧠 My AI & Code'],
  ['markets', '📈 My Markets & Odds'], ['zoo-studio', '🔭 My Zoo & Studio'],
];
const OS_TITLES = {
  my_models_hub:'🧠 My Models, Version Router & Benchmark', openskills_library:'🧩 OpenSkills v2 Optimizer',
  morning_postcard:'While You Were Out', project_decisions:'Pinned Decisions', task_center_live_feed:'⏱️ Task Center Live Feed',
  airlock_privacy_diff:'Airlock Privacy Diff', open_news_engine:'📰 Open News', multimodal_model_tracker:'Multimodal Model Tracker',
  personal_blind_scorecard:'Personal Blind Scorecard', builder_signal_radar:'Builder Signal Radar', pro_sports_odds_board:'Pro Sports Odds Board',
  macro_alpha_delta:'Macro Alpha Delta', zoo_arena_pulse_cta:'OpenZoo Arena Pulse', room_zero_lockbox:'Room Zero Lockbox',
  imageboard_media_remix:'Imageboard Media Remix', custom_task_widget:'Task Results', model_market_tracker:'Frontier Model Intelligence',
  global_agent_telemetry:'The Live Zoo Pulse', model_scorecard:'Blind Scrimmage Scorecard', airlock_diff:'Outbound Sanitizer Diff',
  zoo_odds_watch:'Arena Odds Watch', fork_crew_spotlight:'Fork Crew Spotlight', story_spectrum_mapper:'News Spectrum & Spin Mapper',
  model_tracker_hub:'Model Tracker Hub',
};
const OS_LENS = ['open-source-ai','vibe-coding','macro-markets','geopolitics','pro-sports','crypto','bio-health','media-music'];
const OS_LENS_WIDGETS = {
  'open-source-ai':['my_models_hub','openskills_library','builder_signal_radar'], 'vibe-coding':['my_models_hub','openskills_library','multimodal_model_tracker'],
  'macro-markets':['macro_alpha_delta','open_news_engine'], geopolitics:['open_news_engine','morning_postcard'], 'pro-sports':['pro_sports_odds_board','zoo_odds_watch'],
  crypto:['macro_alpha_delta','zoo_odds_watch'], 'bio-health':['open_news_engine','project_decisions'], 'media-music':['imageboard_media_remix','open_news_engine'],
};
const OS_SPANS = {'1x1':'2x1','2x1':'2x2','2x2':'1x1'};
const OS_NEWS_MODES = ['scan','split','audio'];

function osClone(value){ return JSON.parse(JSON.stringify(value)); }
function osEscape(value){ return String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch])); }
function osActiveTab(layout){ return layout.tabs.find(tab => tab.id === layout.active_tab) || layout.tabs[0]; }
function osSelectTab(layout, tabId){
  if (!layout.tabs.some(tab => tab.id === tabId)) throw new Error('Unknown tab');
  const next = osClone(layout); next.active_tab = tabId; return next;
}
function osAddCustomTab(layout, title, id){
  const name = String(title || '').trim(); if (!name || name.length > 40) throw new Error('Custom tab title must be 1–40 characters');
  if (layout.tabs.filter(tab => tab.kind === 'custom').length >= 8) throw new Error('Eight custom tabs maximum');
  if (!/^custom-[A-Za-z0-9-]{1,60}$/.test(id) || layout.tabs.some(tab => tab.id === id)) throw new Error('Custom tab ID is invalid or already used');
  const next = osClone(layout); next.tabs.push({id,title:name,kind:'custom',widgets:[]}); next.active_tab = id; return next;
}
function osRenameCustomTab(layout, tabId, title){
  const name = String(title || '').trim(); if (!name || name.length > 40) throw new Error('Custom tab title must be 1–40 characters');
  const next = osClone(layout), tab = next.tabs.find(item => item.id === tabId); if (!tab || tab.kind !== 'custom') throw new Error('Only custom tabs can be renamed');
  tab.title = name; return next;
}
function osDeleteCustomTab(layout, tabId){
  const next = osClone(layout), index = next.tabs.findIndex(tab => tab.id === tabId);
  if (index < 0 || next.tabs[index].kind !== 'custom') throw new Error('System tabs cannot be deleted');
  const removed = {tab:next.tabs[index],index}; next.tabs.splice(index,1); if (next.active_tab === tabId) next.active_tab = 'command';
  return {layout:next,removed};
}
function osMutateWidget(layout, tabId, widgetId, mutation){
  const next = osClone(layout), tab = next.tabs.find(item => item.id === tabId); if (!tab) throw new Error('Unknown tab');
  const index = tab.widgets.findIndex(widget => widget.id === widgetId); if (index < 0) throw new Error('Unknown widget');
  mutation(tab.widgets,index,tab); tab.widgets.forEach((widget,order) => { widget.order = order; }); return next;
}
function osResizeWidget(layout, tabId, widgetId){ return osMutateWidget(layout,tabId,widgetId,widgets => { const widget = widgets.find(item => item.id === widgetId); widget.span = OS_SPANS[widget.span] || '1x1'; }); }
function osMoveWidget(layout, tabId, widgetId, direction){
  return osMutateWidget(layout,tabId,widgetId,(widgets,index) => { const target = index + Math.sign(direction); if (target < 0 || target >= widgets.length) return; const [widget] = widgets.splice(index,1); widgets.splice(target,0,widget); });
}
function osDeleteWidget(layout, tabId, widgetId){
  let removed = null; const next = osMutateWidget(layout,tabId,widgetId,(widgets,index) => { removed = {widget:widgets[index],index}; widgets.splice(index,1); }); return {layout:next,removed};
}
function osUndoDelete(layout, tabId, removed){
  if (!removed || !removed.widget) throw new Error('Nothing to undo');
  const next = osClone(layout), tab = next.tabs.find(item => item.id === tabId); if (!tab) throw new Error('Unknown tab');
  if (tab.widgets.some(widget => widget.id === removed.widget.id)) return next;
  if (tab.widgets.length >= 12) throw new Error('This tab is full'); tab.widgets.splice(Math.min(removed.index,tab.widgets.length),0,removed.widget);
  tab.widgets.forEach((widget,order) => { widget.order = order; }); return next;
}
function osToggleSkill(selected, skillId, checked){ const next = new Set(selected); if (checked) next.add(skillId); else next.delete(skillId); return next; }
function osRouterLabel(result){ return result && result.available ? result.selected_model + ' · ' + result.tier : 'No connected model for this tier'; }
function osSwarmAcceptance(result, accepted, externalWriteApproved){
  const external = result && result.external_write_requires_approval === true;
  return {activated:Boolean(accepted && result && (result.requires_acceptance || result.auto_activate) && (!external || externalWriteApproved === true)), external_write_requires_approval:external, execution_started:false};
}
function osNewsMode(mode){
  if (!OS_NEWS_MODES.includes(mode)) throw new Error('Unknown news reading mode'); return {mode,available:mode !== 'audio' ? true : false};
}
function osModelMetrics(record){
  const value = key => record && record[key] !== undefined && record[key] !== null && record[key] !== '' ? String(record[key]) : '—';
  return {ttft:value('ttft'),tokensPerSecond:value('tokens_per_second'),winRate:value('win_rate'),savings:value('savings')};
}
function osApplyLens(layout){
  const next = osClone(layout), lens = next.lens || [];
  if (!lens.length) return next;
  const rank = widget => Math.min(...lens.map(id => (OS_LENS_WIDGETS[id] || []).indexOf(widget.type)).filter(index => index >= 0),999);
  for (const tab of next.tabs){ tab.widgets = tab.widgets.map((widget,index) => ({widget,index})).sort((a,b) => rank(a.widget)-rank(b.widget) || a.index-b.index).map(entry => entry.widget); tab.widgets.forEach((widget,order) => { widget.order = order; }); }
  return next;
}

let osLayout = null, osTasks = null, osView = 'dashboard', osLensOpen = false, osCustomizing = false, osSkillResults = [], osSkillBundle = null;
let osSelectedSkills = new Set(), osRouterMode = 'auto_optimize', osSwarmPolicy = 'notify_accept', osSwarmResult = null, osSwarmAccepted = false;
let osNewsResult = null, osNewsReadingMode = 'scan', osNewsDraft = {url_or_headline:'',source_text:'',source_kind:'unverified'}, osNewsIndex = 0;
let osOdds = null, osTracker = null, osMarket = null, osDragId = null, osLoadPromise = null, osStoryEpoch = 0;

function osNotify(message, options){
  if (typeof sdToast === 'function') { sdToast(message,options || {}); return; }
  if (typeof note === 'function') { note(message); return; }
  if (typeof document === 'undefined') return;
  const node = document.createElement('div'); node.className = 'os-toast-note'; node.setAttribute('role','status');
  if (options && options.undo){ const button = document.createElement('button'); button.textContent = 'Undo'; button.onclick = () => { options.undo(); node.remove(); }; node.append(document.createTextNode(message+' '),button); } else node.textContent = message;
  document.body.appendChild(node); setTimeout(() => node.remove(),options && options.undo ? 6500 : 3500);
}
async function osApi(path,data){ if (typeof api !== 'function') throw new Error('The local API is unavailable'); return api(path,data); }
function osProjects(){ return typeof state !== 'undefined' && state && Array.isArray(state.projects) ? state.projects : []; }
function osProviders(){ return typeof state !== 'undefined' && state && Array.isArray(state.providers) ? state.providers : []; }
function osZoo(){ return typeof zooState !== 'undefined' && zooState ? zooState : {}; }
function osInvalidate(){ if (typeof invalidate === 'function') invalidate(); }
function osSyncSkills(){
  if (typeof selectedSkills !== 'undefined' && selectedSkills instanceof Set){ selectedSkills.clear(); for (const id of osSelectedSkills) selectedSkills.add(id); }
  osInvalidate();
}
function osCleanLayout(result){
  if (!result || result.schema_version !== 2 || !Array.isArray(result.tabs)) throw new Error('The local dashboard did not return schema v2');
  const clean = osClone(result); delete clean.widgets; return clean;
}
async function osLoad(){
  const result = await osApi('/api/dashboard/layout'); osLayout = osApplyLens(osCleanLayout(result));
  try { osTasks = (await osApi('/api/tasks')).tasks || []; } catch { osTasks = []; }
}
function osTabById(tabId){ return osLayout && osLayout.tabs.find(tab => tab.id === tabId); }
async function osPersist(message){
  try { const saved = await osApi('/api/dashboard/layout',osLayout); osLayout = osApplyLens(osCleanLayout(saved)); if (message) osNotify(message,{teal:true}); }
  catch (error) { osNotify('Layout was not saved: '+error.message); }
  osRenderDashboard();
}
function osProvenance(type){
  if (['morning_postcard','global_agent_telemetry','zoo_odds_watch','fork_crew_spotlight','zoo_arena_pulse_cta','pro_sports_odds_board'].includes(type)) return '<span class="os-badge">ZOO / FIXTURE</span>';
  if (['airlock_privacy_diff','airlock_diff'].includes(type)) return '<span class="os-badge os-local">AIRLOCK</span>';
  return '<span class="os-badge os-local">LOCAL</span>';
}
function osMetricsHtml(){
  const metrics = osModelMetrics({}); return `<div class="os-stat-row"><div class="os-stat"><strong>${metrics.ttft}</strong><span>TTFT · no local sample</span></div><div class="os-stat"><strong>${metrics.tokensPerSecond}</strong><span>Tokens/sec · no local sample</span></div><div class="os-stat"><strong>${metrics.winRate}</strong><span>Win rate · no blind sample</span></div><div class="os-stat"><strong>${metrics.savings}</strong><span>Measured savings</span></div></div>`;
}
function osModelsBody(){
  const providers = osProviders(); return `<p class="os-muted">Choose by need, then review an available model. Connection state is session-local; routing never dispatches a request.</p>
    <div class="os-actions">${['Deep reasoning','Vibe coding','Multimodal','Local & private'].map(label => `<button class="os-pill" data-os-need="${osEscape(label)}">${osEscape(label)}</button>`).join('')}</div>
    ${osMetricsHtml()}<div class="os-list">${providers.length ? providers.slice(0,6).map(provider => `<div class="os-model-row"><div><strong>${osEscape(provider.name || provider.id)}</strong><p class="os-muted">${provider.configured ? 'Configured this session · access unverified until a request succeeds' : 'Not connected'}</p></div><button class="os-btn" data-os-connect="${osEscape(provider.id)}">${provider.configured ? 'Manage' : 'Connect'}</button></div>`).join('') : '<div class="os-empty">Provider state is not loaded. Open My Models to inspect local connection options.</div>'}</div>
    <div class="os-actions"><button class="os-btn os-teal" data-os-models-drawer>Open model-picker drawer</button><span class="os-badge">No live benchmark or price claims</span></div>`;
}
function osSkillsBody(){
  return `<form class="os-form" id="os-skills-form"><label>Discover across 1,462 active local manifests<input id="os-skill-query" maxlength="5000" placeholder="Security architecture, research, design…" value="${osEscape(osNewsDraft.skill_query || '')}"></label><div class="os-actions"><button class="os-btn os-teal" type="submit">Search local FTS5</button><button class="os-btn" type="button" data-os-optimize-selected ${osSelectedSkills.size ? '' : 'disabled'}>Inspect selected playbook</button></div></form>
    <div id="os-skills-results" class="os-results">${osSkillResultsHtml()}</div><div id="os-skill-inspector">${osSkillBundle ? osBundleHtml(osSkillBundle) : ''}</div>
    <form class="os-form" id="os-learn-form" style="margin-top:12px"><label>Learned preference · private to projects.sqlite3<input id="os-learn-rule" maxlength="500" placeholder="Always separate observed facts from inference"></label><button class="os-btn" type="submit">Save bounded local rule</button></form>
    <p class="os-small os-muted" style="margin-top:10px">Discovery returns headers only. Only selected playbooks enter the inspector. 1,201 records are metadata-only and say so; no source procedure is invented.</p>`;
}
function osSkillResultsHtml(){
  if (!osSkillResults.length) return '<div class="os-empty">Search the offline catalog. No private learned rules appear in discovery results.</div>';
  return osSkillResults.map(skill => `<article class="os-skill"><label><input type="checkbox" data-os-skill="${osEscape(skill.id)}" ${osSelectedSkills.has(skill.id) ? 'checked' : ''}><span><strong>${osEscape(skill.name)}</strong><span class="os-badge">${osEscape(skill.guild || 'Legacy starter')}</span></span></label><p>${osEscape(skill.description)}</p><p>${osEscape(skill.reason || '')}</p></article>`).join('');
}
function osBundleHtml(bundle){
  return `<div class="os-results">${(bundle.selected || []).map(manifest => `<article class="os-story-card"><span class="os-badge">${osEscape(manifest.content_basis)}</span><h4>${osEscape(manifest.header.branded_title)}</h4><pre class="os-verdict">${osEscape(manifest.builder_instructions)}</pre><details><summary>Challenger &amp; verification contract</summary><pre class="os-verdict">${osEscape(JSON.stringify({challenger:manifest.challenger_rubric,verification:manifest.verification_contract},null,2))}</pre></details></article>`).join('')}</div>`;
}
function osMorningBody(){
  const zoo = osZoo(), rooms = Array.isArray(zoo.rooms) ? zoo.rooms.length : 0;
  return `<p>No private project text is mixed into this OpenZoo widget.</p><div class="os-stat-row"><div class="os-stat"><strong>${rooms}</strong><span>Locally loaded room records</span></div><div class="os-stat"><strong>—</strong><span>Unreviewed remote events</span></div></div><p class="os-small os-muted">Settled activity appears only when supplied by the existing Zoo feed. No background scheduler was added.</p>`;
}
function osDecisionsBody(widget){
  const projects = osProjects(), configured = widget.config && widget.config.project_id;
  const rows = projects.filter(project => !configured || project.id === configured).flatMap(project => (project.decisions || []).map(decision => ({...decision,project:project.name}))).slice(0,5);
  return rows.length ? `<div class="os-list">${rows.map(row => `<div class="os-list-row"><strong>${osEscape(row.text)}</strong><p>${osEscape(row.project)} · local project decision</p></div>`).join('')}</div>` : '<div class="os-empty">No pinned project decisions. Add one in My Projects; nothing is inferred.</div>';
}
function osTasksBody(){
  const tasks = osTasks || []; return tasks.length ? `<div class="os-list">${tasks.map(task => `<div class="os-list-row"><strong>${osEscape(task.name)}</strong><p>${task.is_enabled ? 'Enabled' : 'Paused'} · ${osEscape(task.status)} · ${osEscape(task.swarm_policy)} · cap $${Number(task.budget_cap_usd).toFixed(2)}</p></div>`).join('')}</div><button class="os-btn" data-os-view="tasks">Open Task Center</button>` : '<div class="os-empty">No task configuration is loaded. No task has run.</div>';
}
function osAirlockBody(){ return '<p>Project and Zoo stores remain separate. External writes require their own explicit approval.</p><div class="os-empty">No outbound sanitized diff is loaded. Analysis does not grant send or publish approval.</div>'; }
function osNewsBody(){
  return `<form class="os-form" id="os-news-form"><label>Link or headline · URLs are never fetched<input id="os-news-input" maxlength="500" required placeholder="Paste a link or write a headline" value="${osEscape(osNewsDraft.url_or_headline)}"></label><label>Optional supplied source text<textarea id="os-news-source" maxlength="100000" placeholder="Paste article or primary-source text for extractive analysis">${osEscape(osNewsDraft.source_text)}</textarea></label><div class="os-form-row"><label>Source provenance<select id="os-news-kind"><option value="unverified" ${osNewsDraft.source_kind === 'unverified' ? 'selected' : ''}>Unverified / secondary text</option><option value="primary" ${osNewsDraft.source_kind === 'primary' ? 'selected' : ''}>I supplied primary-source text</option></select></label><button class="os-btn os-teal" type="submit">Analyze locally</button></div></form>
    <div class="os-news-modes" role="group" aria-label="News reading modes">${[['scan','60s Scan'],['split','Split Reader'],['audio','3-Min Audio Brief']].map(([id,label]) => `<button class="os-btn os-news-mode os-${id}" data-os-news-mode="${id}" aria-pressed="${osNewsReadingMode === id}">${label}</button>`).join('')}</div><div id="os-news-result">${osNewsResultHtml()}</div>`;
}
function osNewsResultHtml(){
  const result = osNewsResult; if (!result) return '<div class="os-empty">No story analyzed. Submitted links remain unfetched and unverified.</div>';
  const mode = osNewsReadingMode, coverage = result.coverage_split || {};
  const header = `<article class="os-story-card" tabindex="0" data-os-story="0"><span class="os-badge">${osEscape(result.submitted_source)}</span><h3>${osEscape(result.headline)}</h3><p class="os-small os-muted">${osEscape(result.method)}</p></article>`;
  if (mode === 'scan') return `${header}<div class="os-scan-grid">${['left','center','right'].map(key => `<div class="os-scan-card"><strong>${Number(coverage[key] || 0)}%</strong><span>${key} keyword bucket</span></div>`).join('')}</div><p><strong>Divergence heuristic: ${Number(result.divergence_score || 0)}/100</strong></p><p class="${result.verified_core && result.verified_core.verified ? '' : 'os-muted'}">${osEscape(result.verified_core && result.verified_core.text)}</p>${osNewsActions()}`;
  if (mode === 'split') return `${header}<div class="os-split-grid">${(result.frames || []).map(frame => `<section class="os-frame"><h4>${osEscape(frame.label)}</h4><p>${osEscape(frame.headline)}</p><span class="os-badge os-warning">Hypothesis · not a live outlet</span></section>`).join('')}</div><div class="os-split-grid" style="margin-top:10px"><section class="os-frame"><h4>FACT · supplied extracts</h4><p>${osEscape((result.facts || []).join('\n') || 'No source-text facts supplied.')}</p></section><section class="os-frame"><h4>INFERENCE</h4><p>${osEscape((result.inferences || []).join('\n'))}</p></section><section class="os-frame"><h4>COULDNT_VERIFY</h4><p>${osEscape((result.unverified || []).join('\n'))}</p></section></div><pre class="os-verdict">${osEscape(result.verdict_card)}</pre>${osNewsActions()}`;
  const script = result.audio_brief && result.audio_brief.script || {anchor:[],skeptic:[]};
  return `${header}<div class="os-empty">Audio unavailable · ${osEscape(result.audio_brief && result.audio_brief.reason || 'No speech engine connected')}. The script below is text only.</div><div class="os-audio-script"><section><h4>Anchor</h4><ul>${script.anchor.map(line => `<li>${osEscape(line)}</li>`).join('')}</ul></section><section><h4>Skeptic</h4><ul>${script.skeptic.map(line => `<li>${osEscape(line)}</li>`).join('')}</ul></section></div>${osNewsActions()}`;
}
function osNewsActions(){ return '<div class="os-actions"><button class="os-btn" data-os-copy-verdict>Copy Verdict Card</button><button class="os-btn" data-os-stress-test>Prepare project stress-test draft</button><span class="os-small os-muted">J/K focuses story cards · no publication or audio action</span></div>'; }
function osTrackerBody(){
  const categories = osTracker || []; return categories.length ? `<div class="os-list">${categories.map(category => `<div class="os-list-row"><strong>${osEscape(category.name)}</strong><p>${(category.models || []).map(model => osEscape(model.name)).join(' · ')}</p></div>`).join('')}</div><p class="os-small os-muted">Existing catalog/reference metadata, not a live provider benchmark.</p>${osMetricsHtml()}` : '<div class="os-empty">Model catalog not loaded. No multimodal measurements are available.</div>';
}
function osScorecardBody(){ return `<div class="os-empty">No locally measured blind-scrimmage sample is available.</div>${osMetricsHtml()}<p class="os-small os-muted">Win rates stay blank until real local paired outcomes exist.</p>`; }
function osBuilderBody(){ return '<div class="os-empty">No repository or build signals collected.</div><p class="os-small os-muted">Connect a local project workflow before interpreting builder activity. No swarm execution is started here.</p>'; }
function osOddsBody(){
  if (!osOdds) return '<div class="os-empty">Sports fixture board not loaded.</div>';
  return '<span class="os-badge os-warning">FIXTURE / REFERENCE DATA · NOT LIVE ODDS</span><div class="os-list">'+(osOdds.length ? osOdds.map(row => `<div class="os-list-row"><strong>${osEscape(row.league)} · ${osEscape(row.event)}</strong><p>${osEscape(row.syndicate_blind_prob)} vs. ${osEscape(row.sealed_market_prob)} · ${Number(row.disagreement_pts)} pt fixture delta</p></div>`).join('') : '<div class="os-empty">No fixture rows returned.</div>')+'</div>';
}
function osMacroBody(){ return '<div class="os-empty">No consented macro market feed is connected.</div><p class="os-small os-muted">Macro deltas and crypto prices remain unavailable rather than fixture-generated. Open News can analyze text you supply.</p>'; }
function osArenaBody(){
  const zoo = osZoo(), agents = Array.isArray(zoo.agents) ? zoo.agents.length : 0, rooms = Array.isArray(zoo.rooms) ? zoo.rooms.length : 0;
  return `<div class="os-stat-row"><div class="os-stat"><strong>${agents}</strong><span>Loaded local/feed agents</span></div><div class="os-stat"><strong>${rooms}</strong><span>Loaded rooms</span></div></div><p class="os-small os-muted">No live telemetry is inferred when the Zoo feed is absent. Arena actions remain in the existing Zoo UI.</p>`;
}
function osRoomZeroBody(){ return '<p>Room Zero uses the existing local Zoo thread controls.</p><div class="os-empty">Lockbox is a product label, not a cryptographic enclave. No new external write or room engine is introduced.</div>'; }
function osRemixBody(){ return '<div class="os-empty">No media generation or remix has been requested.</div><p class="os-small os-muted">Open My Projects for the existing exact-preview image workflow. This widget never creates or publishes media itself.</p>'; }
function osTaskResultBody(widget){
  const task = (osTasks || []).find(item => item.id === (widget.config && widget.config.task_id));
  return task ? `<strong>${osEscape(task.name)}</strong><p class="os-muted">${osEscape(task.status)} · ${task.is_enabled ? 'Enabled' : 'Paused'}</p><pre class="os-verdict">${osEscape(task.last_result == null ? 'No result recorded. This configuration has not been executed by the new UI.' : JSON.stringify(task.last_result,null,2))}</pre>` : '<div class="os-empty">The pinned task no longer exists.</div>';
}
function osBody(widget){
  const aliases = {model_market_tracker:'my_models_hub',model_tracker_hub:'multimodal_model_tracker',model_scorecard:'personal_blind_scorecard',airlock_diff:'airlock_privacy_diff',story_spectrum_mapper:'open_news_engine',global_agent_telemetry:'zoo_arena_pulse_cta',zoo_odds_watch:'pro_sports_odds_board',fork_crew_spotlight:'zoo_arena_pulse_cta'};
  const type = aliases[widget.type] || widget.type;
  const bodies = {my_models_hub:osModelsBody,openskills_library:osSkillsBody,morning_postcard:osMorningBody,project_decisions:() => osDecisionsBody(widget),task_center_live_feed:osTasksBody,airlock_privacy_diff:osAirlockBody,open_news_engine:osNewsBody,multimodal_model_tracker:osTrackerBody,personal_blind_scorecard:osScorecardBody,builder_signal_radar:osBuilderBody,pro_sports_odds_board:osOddsBody,macro_alpha_delta:osMacroBody,zoo_arena_pulse_cta:osArenaBody,room_zero_lockbox:osRoomZeroBody,imageboard_media_remix:osRemixBody,custom_task_widget:() => osTaskResultBody(widget)};
  return (bodies[type] || (() => '<div class="os-empty">This migrated widget has no additional renderer.</div>'))();
}
function osWidgetHtml(widget,index,total,tab){
  const span = OS_SPANS[widget.span] ? widget.span : '1x1';
  return `<article class="os-card ${span === '2x1' ? 'os-wide' : span === '2x2' ? 'os-large' : ''}" data-os-card="${osEscape(widget.id)}" data-os-tab-id="${osEscape(tab.id)}"><div class="os-card-head"><button class="os-drag" draggable="true" data-os-drag="${osEscape(widget.id)}" aria-label="Drag ${osEscape(widget.title)}">⋮⋮</button><div class="os-card-title">${osCustomizing ? `<input data-os-widget-title="${osEscape(widget.id)}" maxlength="120" value="${osEscape(widget.title)}" aria-label="Widget title">` : `<h3>${osEscape(widget.title)}</h3>`}<small>${osEscape(span)} · order ${index+1}</small></div>${osProvenance(widget.type)}<button class="os-icon-btn" data-os-move="-1" data-os-id="${osEscape(widget.id)}" ${index === 0 ? 'disabled' : ''} aria-label="Move widget earlier">←</button><button class="os-icon-btn" data-os-move="1" data-os-id="${osEscape(widget.id)}" ${index === total-1 ? 'disabled' : ''} aria-label="Move widget later">→</button><button class="os-icon-btn" data-os-resize="${osEscape(widget.id)}" aria-label="Resize widget">${osEscape(span)}</button><button class="os-icon-btn" data-os-delete-widget="${osEscape(widget.id)}" aria-label="Delete widget">×</button></div><div class="os-card-body">${osBody(widget)}</div></article>`;
}
function osTaskCenterHtml(){
  const tasks = osTasks || []; return `<section><div class="os-topbar"><div><span class="os-eyebrow">Configuration, not autonomous execution</span><h2>Task Center</h2><p>Enable state stays separate from triggers. New controls persist policy only; they do not start schedules, provider calls, or external writes.</p></div><button class="os-btn" data-os-view="dashboard">← Back to OS tabs</button></div>${tasks.length ? tasks.map(task => `<article class="os-task" data-os-task="${osEscape(task.id)}"><div class="os-task-head"><div><h3>${osEscape(task.name)}</h3><p class="os-muted">${osEscape(task.note || '')}</p></div><label class="os-check"><input type="checkbox" data-os-task-enabled ${task.is_enabled ? 'checked' : ''}> Enabled</label></div><div class="os-task-controls"><label>Swarm policy<select data-os-task-policy><option value="notify_accept" ${task.swarm_policy === 'notify_accept' ? 'selected' : ''}>Notify &amp; Accept</option><option value="auto_optimize" ${task.swarm_policy === 'auto_optimize' ? 'selected' : ''}>Auto-Optimize eligible work</option></select></label><label>Budget cap USD<input type="number" min="0" max="10000" step="0.01" data-os-task-budget value="${Number(task.budget_cap_usd)}"></label><button class="os-btn" data-os-save-task="${osEscape(task.id)}">Save policy</button></div><div class="os-trigger-row">${['1h','6h','daily','on_app_open'].map(trigger => `<label class="os-check"><input type="checkbox" data-os-task-trigger="${trigger}" ${(task.triggers || []).includes(trigger) ? 'checked' : ''}> ${trigger}</label>`).join('')}</div><div class="os-actions"><span class="os-badge">${osEscape(task.status)}</span><button class="os-btn" data-os-pin-task="${osEscape(task.id)}">Pin one result widget to active tab</button></div></article>`).join('') : '<div class="os-empty">No task configuration loaded.</div>'}</section>`;
}
function osRenderDashboard(){
  if (typeof document === 'undefined' || !osLayout) return;
  const section = document.getElementById('studio-dashboard'); if (!section) return; section.className = 'os-shell';
  if (osView === 'tasks'){ section.innerHTML = osTaskCenterHtml(); return; }
  const tab = osActiveTab(osLayout); if (!tab) return;
  const tabs = osLayout.tabs.map(item => `<button class="os-tab" role="tab" data-os-tab="${osEscape(item.id)}" aria-selected="${item.id === tab.id}">${osEscape(item.title)}</button>`).join('');
  const types = Object.keys(OS_TITLES).sort((a,b) => OS_TITLES[a].localeCompare(OS_TITLES[b]));
  section.innerHTML = `<div class="os-topbar"><div><span class="os-eyebrow">Porcelain &amp; Ink · local personal intelligence OS</span><h2>OpenTwin</h2><p>Five tuned workspaces, local skills and model governance. Private vault, OpenZoo, fixtures, and unavailable live data remain explicitly distinct.</p></div><div class="os-actions"><button class="os-btn ${osView === 'tasks' ? 'os-primary' : ''}" data-os-view="tasks">⏱️ Task Center</button><button class="os-btn" data-os-lens>✦ Tune My OS Lens</button></div></div>
    <div class="os-tabs" role="tablist" aria-label="OpenTwin workspaces">${tabs}<button class="os-tab os-custom-add" data-os-add-tab>＋ My Custom Tab</button></div>
    <div class="os-lens-panel ${osLensOpen ? 'os-open' : ''}"><strong>Interest lens</strong>${OS_LENS.map(id => `<button class="os-pill" data-os-lens-id="${id}" aria-pressed="${(osLayout.lens || []).includes(id)}">${osEscape(id)}</button>`).join('')}<span class="os-small os-muted">Only selected IDs are stored; no sensitive-interest inference.</span></div>
    <div class="os-toolbar">${tab.kind === 'custom' ? `<button class="os-btn" data-os-rename-tab="${osEscape(tab.id)}">Rename tab</button><button class="os-btn os-danger" data-os-delete-tab="${osEscape(tab.id)}">Delete tab</button>` : ''}<select class="os-inline-input" id="os-add-type" aria-label="Widget type" style="max-width:280px">${types.map(type => `<option value="${type}">${osEscape(OS_TITLES[type])}</option>`).join('')}</select><button class="os-btn" data-os-add-widget>＋ Add Widget</button><span class="os-spacer"></span><button class="os-btn ${osCustomizing ? 'os-primary' : ''}" data-os-customize>${osCustomizing ? 'Done customizing' : 'Customize Grid'}</button><button class="os-btn" data-os-save-layout>Save Layout</button></div>
    <div class="os-grid" data-os-grid>${tab.widgets.length ? tab.widgets.map((widget,index) => osWidgetHtml(widget,index,tab.widgets.length,tab)).join('') : '<div class="os-empty">This tab is empty. Add a widget to begin.</div>'}</div>`;
  osLoadWidgetData(tab);
}
async function osLoadWidgetData(tab){
  const types = tab.widgets.map(widget => widget.type);
  if (types.includes('pro_sports_odds_board') && osOdds === null){ try { osOdds = (await osApi('/api/dashboard/sports-odds')).matchups || []; } catch { osOdds = []; } if (osLayout && osLayout.active_tab === tab.id) osRenderDashboard(); }
  if (types.some(type => ['multimodal_model_tracker','model_tracker_hub'].includes(type)) && osTracker === null){ try { osTracker = (await osApi('/api/dashboard/model-tracker')).categories || []; } catch { osTracker = []; } if (osLayout && osLayout.active_tab === tab.id) osRenderDashboard(); }
}
async function enhanceOpenTwinOS(){
  if (typeof document === 'undefined') return;
  enhanceOpenTwinComposer();
  let section = document.getElementById('studio-dashboard');
  if (!section) {
    const pageEl = document.getElementById('page');
    if (!pageEl || typeof page === 'undefined' || page !== 'home') return;
    section = document.createElement('section');
    section.id = 'studio-dashboard';
    pageEl.appendChild(section);
  }
  if (!osLayout){ if (!osLoadPromise) osLoadPromise = osLoad().catch(error => { osNotify(error.message); throw error; }).finally(() => { osLoadPromise = null; }); try { await osLoadPromise; } catch { return; } }
  osRenderDashboard();
}

function osDashboardClick(event){
  const target = event.target.closest('button'); if (!target) return;
  const current = osLayout && osActiveTab(osLayout); if (!current) return;
  if (target.dataset.osTab){ osLayout = osSelectTab(osLayout,target.dataset.osTab); osPersist(); return; }
  if (target.hasAttribute('data-os-add-tab')){ const title = window.prompt('Custom tab name','Research'); if (!title) return; try { osLayout = osAddCustomTab(osLayout,title,'custom-'+Date.now().toString(36)); osPersist('Custom tab added.'); } catch (error) { osNotify(error.message); } return; }
  if (target.dataset.osRenameTab){ const title = window.prompt('Rename custom tab',current.title); if (!title) return; try { osLayout = osRenameCustomTab(osLayout,current.id,title); osPersist('Custom tab renamed.'); } catch (error) { osNotify(error.message); } return; }
  if (target.dataset.osDeleteTab){ if (!window.confirm('Delete this custom tab and its local widget layout? Undo is available in this session.')) return; const deletion = osDeleteCustomTab(osLayout,current.id); osLayout = deletion.layout; osPersist(); osNotify('Custom tab deleted.',{undo(){ const next = osClone(osLayout); next.tabs.splice(Math.min(deletion.removed.index,next.tabs.length),0,deletion.removed.tab); osLayout = next; osPersist('Custom tab restored.'); }}); return; }
  if (target.hasAttribute('data-os-lens')){ osLensOpen = !osLensOpen; osRenderDashboard(); return; }
  if (target.dataset.osLensId){ const id = target.dataset.osLensId, lens = new Set(osLayout.lens || []); if (lens.has(id)) lens.delete(id); else lens.add(id); osLayout.lens = [...lens]; osLayout = osApplyLens(osLayout); osPersist('Lens saved; widget order updated deterministically.'); return; }
  if (target.dataset.osView){ osView = target.dataset.osView; osRenderDashboard(); return; }
  if (target.hasAttribute('data-os-customize')){ osCustomizing = !osCustomizing; osRenderDashboard(); return; }
  if (target.hasAttribute('data-os-save-layout')){ osPersist('Layout saved locally.'); return; }
  if (target.hasAttribute('data-os-add-widget')){ if (current.widgets.length >= 12) return osNotify('This tab already has 12 widgets.'); const select = document.getElementById('os-add-type'), type = select && select.value; if (!OS_TITLES[type]) return; const widget = {id:'dash-'+current.id+'-'+type+'-'+Date.now().toString(36),type,title:OS_TITLES[type],span:'1x1',config:{},order:current.widgets.length}; current.widgets.push(widget); osPersist('Widget added.'); return; }
  if (target.dataset.osMove){ osLayout = osMoveWidget(osLayout,current.id,target.dataset.osId,Number(target.dataset.osMove)); osPersist(); return; }
  if (target.dataset.osResize){ osLayout = osResizeWidget(osLayout,current.id,target.dataset.osResize); osPersist('Widget resized.'); return; }
  if (target.dataset.osDeleteWidget){ const deletion = osDeleteWidget(osLayout,current.id,target.dataset.osDeleteWidget); osLayout = deletion.layout; osPersist(); osNotify('Widget removed.',{undo(){ try { osLayout = osUndoDelete(osLayout,current.id,deletion.removed); osPersist('Widget restored.'); } catch (error) { osNotify(error.message); } }}); return; }
  if (target.hasAttribute('data-os-models-drawer')){ osOpenModelsDrawer(); return; }
  if (target.dataset.osConnect){ if (typeof showConnect === 'function') showConnect(target.dataset.osConnect); else osNotify('Open My Models to manage this provider.'); return; }
  if (target.dataset.osNeed){ osOpenModelsDrawer(target.dataset.osNeed); return; }
  if (target.dataset.osNewsMode){ osNewsReadingMode = osNewsMode(target.dataset.osNewsMode).mode; const host = document.getElementById('os-news-result'); if (host) host.innerHTML = osNewsResultHtml(); document.querySelectorAll('[data-os-news-mode]').forEach(button => button.setAttribute('aria-pressed',String(button.dataset.osNewsMode === osNewsReadingMode))); return; }
  if (target.hasAttribute('data-os-optimize-selected')){ osOptimizeSelections(); return; }
  if (target.hasAttribute('data-os-copy-verdict')){ osCopyVerdict(); return; }
  if (target.hasAttribute('data-os-stress-test')){ osPrepareStressTest(); return; }
  if (target.dataset.osSaveTask){ osSaveTask(target.dataset.osSaveTask); return; }
  if (target.dataset.osPinTask){ osPinTask(target.dataset.osPinTask); return; }
}
function osDashboardChange(event){
  const target = event.target, tab = osLayout && osActiveTab(osLayout); if (!tab) return;
  if (target.dataset.osSkill){ osSelectedSkills = osToggleSkill(osSelectedSkills,target.dataset.osSkill,target.checked); osSyncSkills(); const optimize = document.querySelector('[data-os-optimize-selected]'); if (optimize) optimize.disabled = !osSelectedSkills.size; return; }
  if (target.dataset.osWidgetTitle){ const title = target.value.trim(); if (!title) return osNotify('Widget title cannot be empty.'); osLayout = osMutateWidget(osLayout,tab.id,target.dataset.osWidgetTitle,widgets => { widgets.find(widget => widget.id === target.dataset.osWidgetTitle).title = title; }); osPersist('Widget title saved.'); }
}
async function osDashboardSubmit(event){
  if (!['os-news-form','os-skills-form','os-learn-form'].includes(event.target.id)) return; event.preventDefault();
  if (event.target.id === 'os-news-form'){
    osNewsDraft = {url_or_headline:document.getElementById('os-news-input').value.trim(),source_text:document.getElementById('os-news-source').value,source_kind:document.getElementById('os-news-kind').value};
    const epoch = ++osStoryEpoch; try { const result = await osApi('/api/dashboard/open-news',osNewsDraft); if (epoch !== osStoryEpoch) return; osNewsResult = result; osNewsReadingMode = 'scan'; osRenderDashboard(); } catch (error) { osNotify(error.message); } return;
  }
  if (event.target.id === 'os-skills-form'){
    const query = document.getElementById('os-skill-query').value; osNewsDraft.skill_query = query;
    try { const result = await osApi('/api/skills/search',{query,limit:10}); osSkillResults = result.skills || []; const host = document.getElementById('os-skills-results'); if (host) host.innerHTML = osSkillResultsHtml(); } catch (error) { osNotify(error.message); } return;
  }
  const input = document.getElementById('os-learn-rule'); try { const result = await osApi('/api/skills/learn-preference',{rule:input.value}); input.value = ''; osNotify('Preference saved locally. '+result.rule_count+' bounded rule(s) will apply only to optimization.'); } catch (error) { osNotify(error.message); }
}
async function osOptimizeSelections(){
  const query = (document.getElementById('os-skill-query') && document.getElementById('os-skill-query').value) || (document.getElementById('prompt') && document.getElementById('prompt').value) || 'Selected local skill playbook';
  if (!osSelectedSkills.size) return osNotify('Select at least one discovered skill first.');
  try { osSkillBundle = await osApi('/api/skills/optimize-prompt',{query,skill_ids:[...osSelectedSkills].slice(0,8)}); const host = document.getElementById('os-skill-inspector') || document.getElementById('os-optimizer-inspector'); if (host) host.innerHTML = osBundleHtml(osSkillBundle); osNotify('Selected builder, challenger, and verification sections are ready for local inspection. Exact-preview approval is still required.'); } catch (error) { osNotify(error.message); }
}
async function osCopyVerdict(){
  if (!osNewsResult) return; const text = osNewsResult.verdict_card || '';
  try { await navigator.clipboard.writeText(text); osNotify('Verdict card copied. It retains FACT, INFERENCE, and COULDNT_VERIFY labels.'); }
  catch { const area = document.createElement('textarea'); area.value = text; area.setAttribute('aria-label','Selectable verdict card'); document.body.appendChild(area); area.select(); osNotify('Clipboard unavailable. The verdict text is selected for manual copy.'); setTimeout(() => area.remove(),10000); }
}
function osPrepareStressTest(){
  if (!osNewsResult) return; const draft = 'Stress-test this Open News analysis. Separate supplied facts, inference, and unverified claims. Do not treat framing hypotheses as live coverage.\n\n'+osNewsResult.verdict_card;
  const promptInput = document.getElementById('prompt'); if (promptInput){ promptInput.value = draft; osInvalidate(); promptInput.focus(); }
  else { try { sessionStorage.setItem('opentwin_news_stress_draft',draft); } catch {} }
  osNotify('Stress-test draft prepared locally. Review it in My Projects; nothing was sent.');
}
async function osSaveTask(taskId){
  const card = document.querySelector(`[data-os-task="${CSS.escape(taskId)}"]`), task = (osTasks || []).find(item => item.id === taskId); if (!card || !task) return;
  const budget = Number(card.querySelector('[data-os-task-budget]').value); if (!Number.isFinite(budget) || budget < 0 || budget > 10000) return osNotify('Budget cap must be between 0 and 10000 USD.');
  task.is_enabled = card.querySelector('[data-os-task-enabled]').checked; task.swarm_policy = card.querySelector('[data-os-task-policy]').value; task.budget_cap_usd = budget;
  task.triggers = [...card.querySelectorAll('[data-os-task-trigger]:checked')].map(input => input.dataset.osTaskTrigger);
  try { const result = await osApi('/api/tasks',{tasks:osTasks}); osTasks = result.tasks; osNotify('Task policy saved. No schedule or provider request was started.'); osRenderDashboard(); } catch (error) { osNotify(error.message); }
}
function osPinTask(taskId){
  const tab = osActiveTab(osLayout), task = (osTasks || []).find(item => item.id === taskId); if (!tab || !task) return;
  if (osLayout.tabs.some(item => item.widgets.some(widget => widget.type === 'custom_task_widget' && widget.config && widget.config.task_id === taskId))) return osNotify('This task already has one pinned result widget.');
  if (tab.widgets.length >= 12) return osNotify('The active tab is full. Remove a widget before pinning.');
  tab.widgets.push({id:'dash-task-'+taskId,type:'custom_task_widget',title:task.name+' · Results',span:'1x1',config:{task_id:taskId},order:tab.widgets.length}); osView = 'dashboard'; osPersist('Task result widget pinned to '+tab.title+'.');
}
function osOpenModelsDrawer(need){
  if (typeof document === 'undefined') return; document.querySelectorAll('.os-drawer,.os-backdrop').forEach(node => node.remove());
  const backdrop = document.createElement('div'); backdrop.className = 'os-backdrop'; backdrop.dataset.osDrawerClose = 'true';
  const drawer = document.createElement('aside'); drawer.className = 'os-drawer'; drawer.setAttribute('role','dialog'); drawer.setAttribute('aria-modal','true'); drawer.setAttribute('aria-label','My Models');
  drawer.innerHTML = `<div class="os-drawer-head"><div><span class="os-eyebrow">${osEscape(need || 'Session-local provider choices')}</span><h2>My Models</h2></div><button class="os-icon-btn" data-os-drawer-close aria-label="Close model drawer">×</button></div><p class="os-muted">Model routing selects an ID only. Credentials stay in the existing session-only connection flow.</p><div class="os-list">${osProviders().map(provider => `<div class="os-model-row"><div><strong>${osEscape(provider.name || provider.id)}</strong><p>${provider.configured ? 'Configured · access unverified' : 'Not configured'}</p></div><button class="os-btn" data-os-connect="${osEscape(provider.id)}">${provider.configured ? 'Manage' : 'Connect'}</button></div>`).join('') || '<div class="os-empty">No provider state loaded.</div>'}</div>${osMetricsHtml()}<section><h3>OpenRouter public model index</h3><p class="os-small os-muted">Optional public metadata only. No API key or prompt is sent. Fixed OpenRouter endpoint, 5 MB limit, 24-hour local cache, no redirects or retries.</p><label class="os-check"><input type="checkbox" id="os-market-consent"> I consent to one public-index network read when cached data is unavailable</label><div class="os-actions"><button class="os-btn" id="os-market-refresh">Load / refresh public index</button></div><div id="os-market-result">${osMarketHtml()}</div></section>`;
  document.body.append(backdrop,drawer); const close = drawer.querySelector('[data-os-drawer-close]'); if (close) close.focus();
}
function osMarketHtml(){
  if (!osMarket) return '<div class="os-empty">No public index loaded. Existing local model choices remain available.</div>';
  if (!osMarket.available) return `<div class="os-empty">${osEscape(osMarket.reason)}</div>`;
  return `<p class="os-small os-muted">${osMarket.cached ? '24-hour cache' : 'Fresh public response'} · ${osEscape(new Date(Number(osMarket.fetched_at)*1000).toLocaleString())}</p><div class="os-list">${(osMarket.models || []).slice(0,30).map(model => `<div class="os-list-row"><strong>${osEscape(model.id)}</strong><p>Published prompt/completion pricing: ${osEscape(JSON.stringify(model.pricing))} · not a live quote</p></div>`).join('')}</div>`;
}
async function osMarketRefresh(){
  const consent = document.getElementById('os-market-consent'); try { osMarket = await osApi('/api/models/market-index',{consent:Boolean(consent && consent.checked)}); const host = document.getElementById('os-market-result'); if (host) host.innerHTML = osMarketHtml(); } catch (error) { osNotify(error.message); }
}

function enhanceOpenTwinComposer(){
  if (typeof document === 'undefined') return;
  const composer = document.querySelector('.composer'); if (!composer || document.getElementById('os-composer-governance')) return;
  const panel = document.createElement('details'); panel.id = 'os-composer-governance'; panel.className = 'os-composer-governance';
  panel.innerHTML = `<summary>Optimize Skills &amp; Model · Smart Router · Swarm Governance</summary><p class="os-small os-muted">These controls prepare selections for inspection. They never bypass exact-preview approval or submit a model request.</p><div class="os-composer-grid"><section><h3>OpenSkills optimizer</h3><form class="os-form" id="os-composer-skills"><label>Task / discovery query<input id="os-composer-skill-query" maxlength="5000" placeholder="Use your prompt or a skill topic"></label><div class="os-actions"><button class="os-btn" type="submit">Discover</button><button class="os-btn" type="button" data-os-optimize-selected>Inspect selected</button></div></form><div id="os-composer-skill-results" class="os-results"></div><div id="os-optimizer-inspector"></div></section><section><h3>Smart Router</h3><div class="os-actions">${['auto_optimize','economy_lock','frontier_max'].map(mode => `<button class="os-pill" data-os-router-mode="${mode}" aria-pressed="${osRouterMode === mode}">${mode}</button>`).join('')}</div><div class="os-form" style="margin-top:8px"><label>Family<select id="os-router-family"><option value="kimi">Kimi</option><option value="gemini">Gemini</option><option value="claude">Claude</option><option value="openrouter">OpenRouter</option><option value="groq">Groq</option><option value="ollama">Ollama</option></select></label><label>Connected model IDs · comma separated<input id="os-router-connected" placeholder="Only models you have connected"></label><button class="os-btn" data-os-route>Route version locally</button></div><div class="os-router-output" id="os-router-output">No route evaluated. Unconnected models remain unavailable.</div></section><section><h3>Swarm Governance</h3><div class="os-actions"><button class="os-pill" data-os-swarm-policy="notify_accept" aria-pressed="true">Notify &amp; Accept</button><button class="os-pill" data-os-swarm-policy="auto_optimize" aria-pressed="false">Auto-Optimize</button></div><div class="os-form" style="margin-top:8px"><label>Budget cap USD<input id="os-swarm-budget" type="number" min="0" max="10000" value="0" step="0.01"></label><label>Cost per worker USD<input id="os-swarm-cost" type="number" min="0" value="0" step="0.01"></label><button class="os-btn" data-os-swarm-evaluate>Evaluate independence</button></div><div class="os-swarm-output" id="os-swarm-output">No swarm evaluated. Single-agent work remains the default.</div></section><section><h3>Consent boundary</h3><p class="os-small os-muted">Skill toggles update the existing composer selection and invalidate old previews. Router and swarm results are advisory. External writes always require separate approval. No TTFT, throughput, win-rate, or cache-saving measurement is claimed.</p></section></div>`;
  composer.parentNode.insertBefore(panel,composer);
  panel.addEventListener('click',osComposerClick); panel.addEventListener('submit',osComposerSubmit); panel.addEventListener('change',osComposerChange);
}
function osComposerChange(event){
  if (event.target.dataset.osSkill){ osSelectedSkills = osToggleSkill(osSelectedSkills,event.target.dataset.osSkill,event.target.checked); osSyncSkills(); }
}
async function osComposerSubmit(event){
  if (event.target.id !== 'os-composer-skills') return; event.preventDefault();
  const query = document.getElementById('os-composer-skill-query').value || (document.getElementById('prompt') && document.getElementById('prompt').value) || '';
  try { const result = await osApi('/api/skills/search',{query,limit:10}); osSkillResults = result.skills || []; document.getElementById('os-composer-skill-results').innerHTML = osSkillResultsHtml(); } catch (error) { osNotify(error.message); }
}
function osComposerPrompt(){ const input = document.getElementById('prompt'), query = document.getElementById('os-composer-skill-query'); return (input && input.value.trim()) || (query && query.value.trim()) || ''; }
async function osComposerClick(event){
  const button = event.target.closest('button'); if (!button) return;
  if (button.dataset.osRouterMode){ osRouterMode = button.dataset.osRouterMode; document.querySelectorAll('[data-os-router-mode]').forEach(node => node.setAttribute('aria-pressed',String(node.dataset.osRouterMode === osRouterMode))); return; }
  if (button.dataset.osSwarmPolicy){ osSwarmPolicy = button.dataset.osSwarmPolicy; document.querySelectorAll('[data-os-swarm-policy]').forEach(node => node.setAttribute('aria-pressed',String(node.dataset.osSwarmPolicy === osSwarmPolicy))); return; }
  if (button.hasAttribute('data-os-optimize-selected')){ await osOptimizeSelections(); return; }
  if (button.hasAttribute('data-os-route')){
    const prompt = osComposerPrompt(); if (!prompt) return osNotify('Write a prompt before routing.'); const connected = document.getElementById('os-router-connected').value.split(',').map(value => value.trim()).filter(Boolean);
    try { const result = await osApi('/api/models/route-version',{prompt,family:document.getElementById('os-router-family').value,connected_models:connected,mode:osRouterMode}); document.getElementById('os-router-output').textContent = osRouterLabel(result)+' · '+(result.reasons || []).join(' · ')+((result.alternatives || []).length ? ' · Alternatives: '+result.alternatives.join(', ') : ''); if (result.available && document.getElementById('model')){ document.getElementById('model').value = result.selected_model; osInvalidate(); } } catch (error) { osNotify(error.message); } return;
  }
  if (button.hasAttribute('data-os-swarm-evaluate')){
    const prompt = osComposerPrompt(); if (!prompt) return osNotify('Write a prompt before evaluating swarm fit.');
    const targets = prompt.match(/https?:\/\/[^\s,]+|\$[A-Z][A-Z0-9.-]{0,14}/g) || [];
    try { osSwarmResult = await osApi('/api/swarm/evaluate',{prompt,targets,swarm_policy:osSwarmPolicy,budget_cap_usd:Number(document.getElementById('os-swarm-budget').value),cost_per_worker_usd:Number(document.getElementById('os-swarm-cost').value),tier:'paid'}); osSwarmAccepted = false; osRenderSwarmResult(); } catch (error) { osNotify(error.message); } return;
  }
  if (button.hasAttribute('data-os-activate-swarm')){ const state = osSwarmAcceptance(osSwarmResult,true,false); osSwarmAccepted = state.activated; osRenderSwarmResult(); osNotify(osSwarmAccepted ? 'Swarm selection accepted for planning only. No workers started; exact-preview approval still applies.' : 'Swarm was not activated. External writes or eligibility still require review.'); return; }
  if (button.hasAttribute('data-os-keep-single')){ osSwarmAccepted = false; osSwarmResult = null; const host = document.getElementById('os-swarm-output'); if (host) host.textContent = 'Single-agent work selected. No workers started.'; }
}
function osRenderSwarmResult(){
  const host = document.getElementById('os-swarm-output'); if (!host || !osSwarmResult) return; const result = osSwarmResult;
  host.innerHTML = `<p>${result.recommend ? 'Eligible independent fan-out' : 'Single agent recommended'} · ${Number(result.worker_count)} worker(s) · estimated heuristic speedup ${Number(result.estimated_speedup)}× · worst-case $${Number(result.worst_case_cost_usd).toFixed(2)}</p><p>${osEscape((result.reasons || []).concat(result.collisions || []).join(' · ') || 'No collisions detected by the deterministic checks.')}</p>${result.recommend ? '<div class="os-actions"><button class="os-btn" data-os-activate-swarm>Activate Swarm for planning</button><button class="os-btn" data-os-keep-single>Keep Single Agent</button></div>' : ''}<p>${osSwarmAccepted ? 'Accepted locally · execution_started=false · exact-preview approval required' : 'No workers started'}</p>`;
}

if (typeof document !== 'undefined'){
  document.addEventListener('click',event => {
    const dashboard = event.target.closest && event.target.closest('#studio-dashboard'); if (dashboard) osDashboardClick(event);
    const close = event.target.closest && event.target.closest('[data-os-drawer-close]'); if (close) document.querySelectorAll('.os-drawer,.os-backdrop').forEach(node => node.remove());
    const connect = event.target.closest && event.target.closest('.os-drawer [data-os-connect]'); if (connect && typeof showConnect === 'function') showConnect(connect.dataset.osConnect);
    if (event.target.id === 'os-market-refresh') osMarketRefresh();
  });
  document.addEventListener('change',event => { if (event.target.closest && event.target.closest('#studio-dashboard')) osDashboardChange(event); });
  document.addEventListener('submit',event => { if (event.target.closest && event.target.closest('#studio-dashboard')) osDashboardSubmit(event); });
  document.addEventListener('dragstart',event => { const handle = event.target.closest && event.target.closest('[data-os-drag]'); if (!handle) return; osDragId = handle.dataset.osDrag; const card = handle.closest('[data-os-card]'); if (card) card.classList.add('os-dragging'); if (event.dataTransfer) event.dataTransfer.setData('text/plain',osDragId); });
  document.addEventListener('dragover',event => { const card = event.target.closest && event.target.closest('[data-os-card]'); if (!card || !osDragId) return; event.preventDefault(); card.classList.add('os-drop'); });
  document.addEventListener('dragleave',event => { const card = event.target.closest && event.target.closest('[data-os-card]'); if (card) card.classList.remove('os-drop'); });
  document.addEventListener('drop',event => { const card = event.target.closest && event.target.closest('[data-os-card]'); if (!card || !osDragId || !osLayout) return; event.preventDefault(); const tab = osActiveTab(osLayout), targetId = card.dataset.osCard; if (targetId !== osDragId){ const from = tab.widgets.findIndex(widget => widget.id === osDragId), to = tab.widgets.findIndex(widget => widget.id === targetId); if (from >= 0 && to >= 0){ osLayout = osClone(osLayout); const widgets = osActiveTab(osLayout).widgets, [moved] = widgets.splice(from,1); widgets.splice(to,0,moved); widgets.forEach((widget,order) => { widget.order = order; }); osPersist('Widget order saved.'); } } osDragId = null; document.querySelectorAll('.os-dragging,.os-drop').forEach(node => node.classList.remove('os-dragging','os-drop')); });
  document.addEventListener('keydown',event => {
    if (!osNewsResult || !osLayout || osLayout.active_tab !== 'news' || !['j','k','J','K'].includes(event.key)) return;
    if (['INPUT','TEXTAREA','SELECT'].includes(event.target.tagName) || (event.target.closest && event.target.closest('[contenteditable="true"]'))) return;
    const cards = [...document.querySelectorAll('[data-os-story]')]; if (!cards.length) return; event.preventDefault(); osNewsIndex = Math.max(0,Math.min(cards.length-1,osNewsIndex + (event.key.toLowerCase() === 'j' ? 1 : -1)));
    const reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches; cards[osNewsIndex].focus({preventScroll:true}); cards[osNewsIndex].scrollIntoView({behavior:reduced ? 'auto' : 'smooth',block:'nearest'});
  });
  if (typeof window !== 'undefined' && typeof window.enhanceStudioDashboard === 'function') window.enhanceStudioDashboard = enhanceOpenTwinOS;
  enhanceOpenTwinComposer();
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded',enhanceOpenTwinOS,{once:true}); else enhanceOpenTwinOS();
}

const OpenTwinOSExports = {osActiveTab,osSelectTab,osAddCustomTab,osRenameCustomTab,osDeleteCustomTab,osResizeWidget,osMoveWidget,osDeleteWidget,osUndoDelete,osToggleSkill,osRouterLabel,osSwarmAcceptance,osNewsMode,osModelMetrics,osEscape,osApplyLens,enhanceOpenTwinOS,enhanceOpenTwinComposer};
if (typeof module !== 'undefined' && module.exports) module.exports = OpenTwinOSExports;
if (typeof window !== 'undefined') window.OpenTwinOS = OpenTwinOSExports;
