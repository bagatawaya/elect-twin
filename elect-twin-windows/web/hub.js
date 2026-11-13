'use strict';

// Opt-in UI adapter. All Hub traffic stays behind the authenticated local bridge.
// No provider keys, automatic project export, storage, polling, or automatic retries.
class OpenTwinHubSession {
  constructor(call, changed = () => {}) {
    this.call = call;
    this.changed = changed;
    this.connection = 'off';
    this.verified = false;
    this.epoch = 0;
    this.busy = false;
    this.connectionQueue = Promise.resolve();
    this.connectionRevision = 0;
    this.message = 'Local-only. No Hub request has been made.';
    this.draft = '';
    this.draftRevision = 0;
    this.uncertainSend = null;
    this.clearViews();
  }
  clearViews() {
    this.epoch += 1;
    this.rooms = [];
    this.publicListings = [];
    this.events = [];
    this.room = null;
    this.pending = null;
    this.previewing = false;
    this.busy = false;
  }
  dismiss() {
    const connecting = this.connection === 'connecting';
    const inFlight = this.busy && !this.previewing;
    this.clearViews();
    if (connecting) return this.disconnect();
    if (inFlight) this.message = 'View closed. A dispatched request may have completed; no automatic retry was made.';
    this.changed();
  }
  async connect(token, consent) {
    if (!consent || this.connection !== 'off') return;
    if (!/^[A-Za-z0-9_.~-]{20,512}$/.test(token)) {
      this.message = 'Enter a valid operator-provisioned Hub token.';
      this.changed();
      return;
    }
    this.clearViews();
    const revision = ++this.connectionRevision;
    this.connection = 'connecting';
    this.message = 'Configuring the local bridge. This does not contact the Hub.';
    this.changed();
    // Serialize configuration so dismissal/disconnect cannot race a late connect.
    const credentials = {consent: true, token};
    const operation = this.connectionQueue.then(() => this.call('/api/zoo/hub/connect', credentials)).finally(() => { credentials.token = ''; });
    token = '';
    this.connectionQueue = operation.catch(() => {});
    try {
      const result = await operation;
      if (revision !== this.connectionRevision) return;
      if (result.status !== 'configured') throw new Error('Unexpected configuration result');
      this.connection = 'configured';
      this.message = 'Configured for this server session · unverified. Review a rooms request to verify access.';
    } catch {
      if (revision !== this.connectionRevision) return;
      // Configuration may have reached the server. Only disconnect is safe now.
      this.connection = 'uncertain';
      this.message = 'Configuration outcome is unknown. Disconnect before trying again.';
    }
    this.changed();
  }
  async disconnect() {
    this.clearViews();
    this.verified = false;
    this.connection = 'disconnecting';
    this.message = 'Private views cleared. Removing the Hub token from local server memory…';
    this.changed();
    const revision = ++this.connectionRevision;
    const operation = this.connectionQueue.then(() => this.call('/api/zoo/hub/disconnect', {}));
    this.connectionQueue = operation.catch(() => {});
    try {
      const result = await operation;
      if (revision !== this.connectionRevision) return;
      if (result.status !== 'disconnected') throw new Error('Unexpected disconnect result');
      this.connection = 'off';
      this.message = 'Disconnected · local-only. Private views cleared; your own draft is retained. Already shared copies are not recalled.';
    } catch {
      if (revision !== this.connectionRevision) return;
      this.connection = 'uncertain';
      this.message = 'Private views cleared, but server-side disconnect is unconfirmed. Retry Disconnect or quit the local server to remove its session token.';
    }
    this.changed();
  }
  selectRoom(id) {
    if (this.busy) return;
    const room = this.rooms.find(item => item.id === id);
    if (!room || !/^[A-Za-z0-9_-]{1,128}$/.test(id)) return;
    this.room = {id, title: String(room.title || id)};
    this.events = [];
    this.pending = null;
    this.changed();
  }
  review(kind, value = '') {
    if (this.connection !== 'configured' || this.busy) return;
    let request;
    if (kind === 'rooms') request = {method: 'GET', path: '/v1/rooms', payload: null, audience: 'The local Hub receives your bearer credential and this read request. Returns only rooms accessible to your Hub identity.'};
    if (kind === 'public') request = {method: 'GET', path: '/v1/zoo', payload: null, audience: 'The local Hub receives your bearer credential and this read request. Returns the anonymous public listing projection only.'};
    if (kind === 'create' && value.trim() && value.trim().length <= 200) request = {method: 'POST', path: '/v1/rooms', payload: {title: value.trim()}, audience: 'The local Hub stores this title. The new room initially has only your Hub identity as owner/member.'};
    if (kind === 'events' && this.room) request = {method: 'GET', path: '/v1/rooms/' + this.room.id + '/events?after=' + (this.events.at(-1)?.seq || 0), payload: null, audience: 'Read up to 100 more events from “' + this.room.title + '”. Only current members can access this private room.'};
    if (kind === 'send') return this.previewSharedText('draft', {text: this.draft});
    if (kind === 'context') return this.previewSharedText('context', value);
    if (kind === 'retry' && this.uncertainSend) request = this.uncertainSend;
    if (!request) return;
    // Freeze the exact reviewed body, independent of later form edits or selection.
    this.pending = JSON.parse(JSON.stringify({...request, kind}));
    this.message = 'Review the destination, audience, and exact request. Nothing has been sent.';
    this.changed();
  }
  updateDraft(text) {
    this.draft = text;
    this.draftRevision += 1;
    if (this.pending || this.previewing) this.cancelReview();
  }
  async previewSharedText(source, selection) {
    if (this.connection !== 'configured' || !this.room || this.busy) return;
    if (source === 'draft' && (!this.draft.trim() || this.draft.length > 8000)) return;
    if (source === 'context' && (!selection?.project_id || !(selection.document_ids?.length || selection.decision_ids?.length))) {
      this.pending = null;
      this.message = 'Choose a project and at least one document or decision. Nothing is selected automatically.';
      this.changed();
      return;
    }
    const epoch = this.epoch;
    const room = {...this.room};
    const draftRevision = this.draftRevision;
    this.pending = null;
    this.busy = true;
    this.previewing = true;
    this.message = 'Preparing a sanitized preview on this Mac. Nothing is being sent to the Hub.';
    this.changed();
    try {
      const result = await this.call(source === 'context' ? '/api/zoo/hub/context-preview' : '/api/zoo/hub/text-preview', JSON.parse(JSON.stringify(selection)));
      if (epoch !== this.epoch) return;
      if (typeof result.text !== 'string' || !result.text.trim() || result.text.length > 8000 || result.requires_exact_preview_approval !== true) throw new Error('Invalid sanitized preview');
      this.pending = {
        kind: 'send', source, draftRevision,
        method: 'POST', path: '/v1/rooms/' + room.id + '/events',
        payload: {text: result.text, request_id: crypto.randomUUID()},
        audience: 'All current and future members of “' + room.title + '” can read the exact sanitized text shown below. It is stored by the local Hub. ' + (source === 'context' ? 'Only explicitly selected document/decision text is included. No project identity, filenames, history, profile, or telemetry is included automatically.' : 'No local project history, profile, or telemetry is included.'),
        warning: typeof result.warning === 'string' ? result.warning : 'Automatic redaction cannot identify every private fact. Review every character before sharing.'
      };
      this.message = 'Sanitized preview ready. Check every character and the room audience before approving. Nothing has been sent to the Hub.';
    } catch {
      if (epoch !== this.epoch) return;
      this.pending = null;
      this.message = 'Sanitized preview unavailable. Nothing was sent to the Hub. Check your local connection or select less text, then try again.';
    }
    if (epoch === this.epoch) { this.busy = false; this.previewing = false; }
    this.changed();
  }
  cancelReview() {
    if (this.busy && !this.previewing) return;
    if (this.previewing) { this.epoch += 1; this.previewing = false; this.busy = false; }
    this.pending = null;
    this.message = 'Review cancelled. No Hub request was sent.';
    this.changed();
  }
  async send(consent) {
    if (!consent || !this.pending || this.busy || this.connection !== 'configured') return;
    const request = this.pending;
    const epoch = this.epoch;
    this.busy = true;
    this.pending = null;
    if (request.kind === 'send' || request.kind === 'retry') this.uncertainSend = request;
    this.message = 'Request dispatched to the local Hub. No automatic retry will be made.';
    this.changed();
    try {
      const result = await this.call('/api/zoo/hub/request', {consent: true, method: request.method, path: request.path, payload: request.payload});
      if (epoch !== this.epoch) return;
      if (result.status !== 'ok') {
        const status = result.http_status;
        if (result.clear_private_views || [401, 403, 404].includes(status)) this.clearViews();
        if (status === 401) { this.connection = 'off'; this.verified = false; }
        this.message = status === 401 ? 'Hub authorization expired or was revoked. Disconnected and private views cleared.' : 'Hub request failed (' + (status || 'unknown status') + ').' + ([403, 404].includes(status) ? ' Private views cleared. Access is not available.' : '') + ' No automatic retry was made.';
      } else {
        const data = result.data;
        if (request.kind === 'rooms') {
          this.rooms = Array.isArray(data) ? data.filter(item => item && /^[A-Za-z0-9_-]{1,128}$/.test(item.id)).map(item => ({id: item.id, title: String(item.title || item.id)})) : [];
          if (this.room && !this.rooms.some(room => room.id === this.room.id)) { this.room = null; this.events = []; }
          this.verified = true;
        } else if (request.kind === 'public') {
          this.publicListings = Array.isArray(data) ? data.map(item => ({id: String(item.id || ''), label: String(item.label || 'Shared Twin'), category: String(item.category || '')})) : [];
        } else if (request.kind === 'events') {
          const bySequence = new Map(this.events.map(item => [item.seq, item]));
          for (const event of Array.isArray(data) ? data : []) {
            if (event && Number.isSafeInteger(event.seq) && event.seq > 0) bySequence.set(event.seq, {seq: event.seq, author: String(event.author || ''), text: String(event.text || '')});
          }
          this.events = [...bySequence.values()].sort((a, b) => a.seq - b.seq);
        } else if (request.kind === 'create') {
          this.message = 'Room created. Review a rooms request to load it.';
        } else {
          this.uncertainSend = null;
          if (request.source === 'draft' && request.draftRevision === this.draftRevision) this.draft = '';
        }
        if (request.kind !== 'create') this.message = request.method === 'GET' ? 'Read completed. Results are a snapshot, not a live feed.' : 'Exact text stored by the Hub. Review a room read to retrieve events.';
      }
    } catch {
      if (epoch !== this.epoch) return;
      // Includes local authorization loss, unreadable replies, and transport failures.
      this.clearViews();
      this.verified = false;
      this.message = 'Request failed or its outcome is unknown. Private views cleared. No automatic retry was made.' + (this.uncertainSend ? ' You may review the identical send with its original request ID after checking access.' : '');
    }
    if (epoch === this.epoch) this.busy = false;
    this.changed();
  }
}

const HUB_DESTINATION = 'http://127.0.0.1:18765';
let hubSession;
let hubReturnFocus;
function hubEscape(value) { return String(value ?? '').replace(/[&<>"']/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char])); }
function hubStatusLabel() { return hubSession.connection === 'configured' ? (hubSession.verified ? 'Connected · rooms access checked' : 'Configured · unverified') : hubSession.connection === 'off' ? 'Off · local-only' : 'Connection ' + hubSession.connection; }
function enhanceHubBridge() {
  if (typeof page === 'undefined' || page !== 'zoo' || document.getElementById('hub-launcher')) return;
  const target = document.querySelector('.zoo-pagehead');
  if (!target || !hubSession) return;
  target.insertAdjacentHTML('afterend', `<section class="card hub-card" id="hub-launcher" aria-labelledby="hub-card-title"><div><span class="eyebrow">Optional local bridge</span><h2 id="hub-card-title">OpenTwin Hub</h2><p>Keep local examples separate. Connect deliberately to an operator-started Hub on this Mac.</p><span class="badge" id="hub-card-status">${hubEscape(hubStatusLabel())}</span></div><button type="button" data-hub-open>Manage Hub connection</button></section>`);
}
function hubRender() {
  const badge = document.getElementById('hub-card-status');
  if (badge) badge.textContent = hubStatusLabel();
  const status = document.getElementById('hub-status');
  if (!status) return;
  status.textContent = hubSession.message;
  document.getElementById('hub-state').textContent = hubStatusLabel();
  const configured = hubSession.connection === 'configured';
  const off = hubSession.connection === 'off';
  document.getElementById('hub-connect-form').hidden = !off;
  document.getElementById('hub-controls').hidden = !configured;
  const disconnect = document.getElementById('hub-disconnect');
  disconnect.hidden = false;
  disconnect.textContent = off ? 'Clear any stored Hub token' : 'Disconnect and clear private views';
  disconnect.disabled = hubSession.connection === 'disconnecting';
  const disabled = hubSession.busy ? 'disabled' : '';
  document.getElementById('hub-room-list').innerHTML = hubSession.rooms.map(room => `<button type="button" data-hub-room="${hubEscape(room.id)}" ${disabled} aria-pressed="${hubSession.room?.id === room.id}">${hubEscape(room.title)} <small>Room ${hubEscape(room.id)}</small></button>`).join('') || '<p>No rooms loaded. Review a rooms request to check membership.</p>';
  document.getElementById('hub-public-list').innerHTML = hubSession.publicListings.map(item => `<li><strong>${hubEscape(item.label)}</strong> · ${hubEscape(item.category)}<small>${hubEscape(item.id)}</small></li>`).join('');
  document.getElementById('hub-room-work').hidden = !configured || !hubSession.room;
  document.getElementById('hub-room-title').textContent = hubSession.room?.title || '';
  const draft = document.getElementById('hub-draft');
  if (draft.value !== hubSession.draft) draft.value = hubSession.draft;
  document.getElementById('hub-events').innerHTML = hubSession.events.map(item => `<article><small>#${item.seq} · ${hubEscape(item.author)}</small><p>${hubEscape(item.text)}</p></article>`).join('') || '<p>No events loaded. Read the room only when you choose.</p>';
  document.getElementById('hub-retry').hidden = !configured || !hubSession.uncertainSend;
  for (const button of document.querySelectorAll('#hub-controls button')) button.disabled = hubSession.busy;
  const review = document.getElementById('hub-review');
  review.hidden = !hubSession.pending && !hubSession.previewing;
  document.getElementById('hub-preview-warning').textContent = hubSession.pending?.warning || (hubSession.previewing ? 'Preparing a local preview. You can cancel before it completes.' : '');
  document.getElementById('hub-request-consent').disabled = !hubSession.pending;
  document.getElementById('hub-request-consent').checked = false;
  document.getElementById('hub-send').disabled = true;
  document.getElementById('hub-audience').textContent = hubSession.pending?.audience || '';
  document.getElementById('hub-request-body').textContent = hubSession.pending ? JSON.stringify({method: hubSession.pending.method, path: hubSession.pending.path, payload: hubSession.pending.payload}, null, 2) : '';
}
function hubOpen(launcher) {
  hubReturnFocus = launcher;
  hubResetContext();
  hubRender();
  document.getElementById('hub-dialog').showModal();
  document.getElementById('hub-title').focus();
}
function hubResetContext() {
  const projects = typeof state === 'undefined' ? [] : state.projects || [];
  document.getElementById('hub-context-project').innerHTML = '<option value="">Choose a local project</option>' + projects.map(project => `<option value="${hubEscape(project.id)}">${hubEscape(project.name)}</option>`).join('');
  document.getElementById('hub-context-items').replaceChildren();
  document.getElementById('hub-context-picker').open = false;
}
function hubContextItems() {
  hubSession.cancelReview();
  const project = (typeof state === 'undefined' ? [] : state.projects || []).find(item => item.id === document.getElementById('hub-context-project').value);
  document.getElementById('hub-context-items').innerHTML = !project ? '' : '<h4>Documents</h4>' + (project.documents || []).map(item => `<label class="hub-check"><input type="checkbox" data-hub-document value="${hubEscape(item.id)}"><span>${hubEscape(item.name || 'Untitled document')}</span></label>`).join('') + '<h4>Decisions</h4>' + (project.decisions || []).map((item, index) => `<label class="hub-check"><input type="checkbox" data-hub-decision value="${hubEscape(item.id)}"><span>Decision ${index + 1}: ${hubEscape(String(item.text || '').slice(0, 160))}</span></label>`).join('');
}
function initializeHubBridge() {
  document.body.insertAdjacentHTML('beforeend', `<dialog id="hub-dialog" aria-labelledby="hub-title" aria-describedby="hub-description"><div class="dialoghead"><div><span class="eyebrow">OpenTwin · optional local Hub</span><h2 id="hub-title" tabindex="-1">Your Hub connection</h2></div><button type="button" id="hub-close">Close</button></div>
    <p id="hub-description">Fixed destination: <strong>${HUB_DESTINATION}</strong>. Start and verify the intended Hub yourself before connecting. Local HTTP cannot prove which process is listening. No discovery, background sync, provider call, or automatic project upload occurs here.</p>
    <p><span class="badge" id="hub-state"></span></p><p id="hub-status" role="status" aria-live="polite"></p>
    <form id="hub-connect-form"><label for="hub-token">Operator-provisioned Hub token, not a provider API key</label><input id="hub-token" type="password" autocomplete="off" spellcheck="false" minlength="20" maxlength="512" required><label class="hub-check"><input id="hub-connect-consent" type="checkbox" required><span>I verified the intended local Hub and choose to store this token in the local server’s memory for this session. Connecting alone makes no Hub request.</span></label><button type="submit" class="primary">Configure local bridge</button></form>
    <button type="button" class="danger" id="hub-disconnect">Disconnect and clear private views</button>
    <div id="hub-controls" hidden><hr><div class="actions"><button type="button" data-hub-review="rooms">Review my rooms request</button><button type="button" data-hub-review="public">Review public listings request</button></div><div id="hub-room-list" class="hub-room-list"></div><ul id="hub-public-list"></ul>
      <form id="hub-create-form"><label for="hub-new-title">New private Hub room</label><input id="hub-new-title" maxlength="200" required placeholder="Room title"><button type="submit">Review creating this room</button></form>
      <section id="hub-room-work" hidden><h3 id="hub-room-title"></h3><button type="button" data-hub-review="events">Review next room events</button><div id="hub-events"></div><form id="hub-message-form"><label for="hub-draft">Text you choose to share with this room</label><textarea id="hub-draft" maxlength="8000" required placeholder="Only text entered here is included"></textarea><button type="submit">Sanitize and review this text</button></form><details id="hub-context-picker"><summary>Choose local project text to share</summary><p>Select specific documents or decisions. All boxes start unchecked. Preview preparation stays on this Mac; only the exact approved sanitized text can be sent to the chosen room.</p><form id="hub-context-form"><label for="hub-context-project">Local project</label><select id="hub-context-project"></select><div id="hub-context-items"></div><button type="submit">Sanitize and review selected context</button></form></details></section>
      <button type="button" id="hub-retry" data-hub-review="retry" hidden>Review identical send again</button>
    </div>
    <section id="hub-review" hidden aria-labelledby="hub-review-title"><h3 id="hub-review-title" tabindex="-1">Review this Hub request</h3><p>Destination: ${HUB_DESTINATION}. Your Hub bearer token authenticates this request. Provider credentials are never forwarded.</p><p id="hub-audience"></p><p id="hub-preview-warning" class="notice"></p><pre id="hub-request-body"></pre><label class="hub-check"><input id="hub-request-consent" type="checkbox"><span>I choose to send exactly this request to the destination and audience shown above.</span></label><div class="actions"><button type="button" id="hub-cancel-review">Cancel review</button><button type="button" class="primary" id="hub-send" disabled>Send reviewed request</button></div></section>
    <p class="small">Closing or reloading does not remove a configured token from local server memory. Use Disconnect (or Clear any stored Hub token after reloading), or quit the server. Closing clears retrieved views and reviews. Your unsent text stays only in this page’s memory. Disconnect cannot undo a dispatched write or recall copies.</p></dialog>`);
  hubSession = new OpenTwinHubSession((route, data) => api(route, data), hubRender);
  const byId = id => document.getElementById(id);
  document.getElementById('page').addEventListener('click', event => {
    const launcher = event.target.closest('[data-hub-open]');
    if (launcher) hubOpen(launcher);
  });
  byId('hub-connect-form').addEventListener('submit', event => {
    event.preventDefault();
    const token = byId('hub-token').value.trim();
    const consent = byId('hub-connect-consent').checked;
    byId('hub-token').value = '';
    byId('hub-connect-consent').checked = false;
    hubSession.connect(token, consent);
  });
  byId('hub-disconnect').onclick = () => hubSession.disconnect();
  byId('hub-close').onclick = () => byId('hub-dialog').close();
  byId('hub-dialog').addEventListener('close', () => {
    byId('hub-token').value = '';
    byId('hub-connect-consent').checked = false;
    hubSession.dismiss();
    hubResetContext();
    const launcher = hubReturnFocus?.isConnected ? hubReturnFocus : document.querySelector('[data-hub-open]');
    launcher?.focus();
  });
  byId('hub-dialog').addEventListener('click', async event => {
    const button = event.target.closest('[data-hub-review],[data-hub-room]');
    if (!button || button.disabled) return;
    if (button.dataset.hubRoom) { hubSession.selectRoom(button.dataset.hubRoom); hubResetContext(); }
    else {
      await hubSession.review(button.dataset.hubReview);
      if (hubSession.pending) byId('hub-review-title').focus();
    }
  });
  byId('hub-create-form').onsubmit = event => { event.preventDefault(); hubSession.review('create', byId('hub-new-title').value); if (hubSession.pending) byId('hub-review-title').focus(); };
  byId('hub-draft').oninput = event => hubSession.updateDraft(event.target.value);
  byId('hub-message-form').onsubmit = async event => { event.preventDefault(); await hubSession.review('send'); if (hubSession.pending) byId('hub-review-title').focus(); };
  byId('hub-context-project').onchange = hubContextItems;
  byId('hub-context-items').onchange = () => hubSession.cancelReview();
  byId('hub-context-form').onsubmit = async event => {
    event.preventDefault();
    const selection = {project_id: byId('hub-context-project').value, document_ids: [...byId('hub-context-items').querySelectorAll('[data-hub-document]:checked')].map(input => input.value), decision_ids: [...byId('hub-context-items').querySelectorAll('[data-hub-decision]:checked')].map(input => input.value)};
    await hubSession.review('context', selection);
    if (hubSession.pending) byId('hub-review-title').focus();
  };
  byId('hub-cancel-review').onclick = () => hubSession.cancelReview();
  byId('hub-request-consent').onchange = event => { byId('hub-send').disabled = !event.target.checked || hubSession.busy; };
  byId('hub-send').onclick = () => hubSession.send(byId('hub-request-consent').checked);
  window.addEventListener('popstate', () => { if (byId('hub-dialog').open) byId('hub-dialog').close(); else hubSession.dismiss(); });
  window.addEventListener('pagehide', () => { hubSession.clearViews(); byId('hub-token').value = ''; hubRender(); });
  hubRender();
  enhanceHubBridge();
}
if (typeof document !== 'undefined' && document.getElementById('page')) initializeHubBridge();
