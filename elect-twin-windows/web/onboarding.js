'use strict';

const ONBOARDING_PROVIDERS = [
  ['openai', 'OpenAI', 'setup-key-openai', 'OpenAI API key'],
  ['anthropic', 'Anthropic', 'setup-key-anthropic', 'Anthropic API key'],
  ['gemini', 'Gemini', 'setup-key-gemini', 'Gemini API key'],
  ['mistral', 'Mistral', 'setup-key-mistral', 'Mistral API key'],
  ['groq', 'Groq', 'setup-key-groq', 'Groq API key'],
];
const ONBOARDING_STEPS = ['welcome', 'providers', 'collaborators'];
const INVITATION_CONSENT = 'Local preview only — nothing was sent, no account was created, no membership changed, and no access was granted.';
const INVITATION_PREVIEW_ONLY = 'Accepting, declining, or cancelling changes only this preview record: nothing is sent, no account, membership, or access changes, and no private project content is shared.';
let setupStep = 'welcome';
let setupReturnFocus = null;
let activeInvitationId = '';
let invitationMode = 'inviter';
let invitationReturnFocus = null;

function localStatus(id, message, error = false) {
  const status = $(id);
  status.textContent = message;
  status.setAttribute('role', error ? 'alert' : 'status');
  status.setAttribute('aria-live', error ? 'assertive' : 'polite');
}

function setupProgress() {
  const labels = {welcome: 'Welcome / privacy', providers: 'Providers', collaborators: 'Collaborators'};
  return `<nav class="setup-progress" aria-label="Setup steps">${ONBOARDING_STEPS.map((step, index) => `<button type="button" data-setup-step="${step}" aria-current="${setupStep === step ? 'step' : 'false'}"><span>${index + 1}</span>${labels[step]}</button>`).join('')}</nav>`;
}

function setupActions() {
  return `<div class="actions setup-actions"><button type="button" data-setup-skip>Skip setup</button><button type="button" data-setup-not-now>Not now</button>${setupStep === 'collaborators' ? '<button type="button" class="primary" data-setup-complete>Complete setup</button>' : ''}</div>`;
}

function setupWelcome() {
  return `<section class="setup-step" aria-label="Welcome and privacy">
    <h3>Your workspace stays optional and local</h3>
    <p>OpenTwin stores its local database as local plaintext on this Mac. Projects are private by default; local storage is not a cryptographic boundary against this Mac’s operator.</p>
    <p>You can browse without a provider, skip any step, and return from My Models or People. No provider request or invitation delivery is part of setup.</p>
    <div class="actions" style="margin-top:20px;display:flex;gap:12px;align-items:center"><button type="button" class="primary" data-setup-step="providers">Connect a model</button><button type="button" class="secondary" data-setup-not-now>Explore first</button></div>
    <div style="margin-top:14px;display:flex;gap:16px;font-size:12px;color:var(--text-tertiary)"><button type="button" data-setup-step="collaborators" style="background:none;border:none;color:inherit;cursor:pointer;padding:0;text-decoration:underline">Collaborators preview</button></div>
  </section>`;
}

function setupProviders() {
  return `<section class="setup-step" aria-label="Optional provider setup">
    <p>Connect zero, one, or several providers independently. Every connection uses an API key; a web account is not used to sign in.</p>
    <ul class="setup-boundaries"><li>Ordinary web subscriptions do not automatically include API access.</li><li>Charges depend on the provider account.</li><li>Output limits are not a spending cap.</li></ul>
    <p>Fixture/local configuration is session-only and unverified until a real provider request. This wizard never makes a provider request. Stored keys are never displayed or logged.</p>
    <div class="setup-providers">${ONBOARDING_PROVIDERS.map(([id, name, keyId, keyLabel]) => {
      const configured = state.providers.find(provider => provider.id === id)?.configured;
      return `<form class="setup-provider" data-setup-provider-form="${id}">
        <div class="card-top"><h3>${name}</h3><span class="badge ${configured ? 'configured' : ''}" id="setup-provider-state-${id}">${configured ? 'Configured · session-only · unverified' : 'Not configured'}</span></div>
        <label for="${keyId}">${keyLabel}</label>
        <input id="${keyId}" name="key" type="password" autocomplete="off" spellcheck="false" required>
        <div class="actions"><button type="submit">Save ${name} session key</button><button type="button" class="danger ${configured ? '' : 'hidden'}" id="setup-disconnect-${id}" data-setup-disconnect="${id}">Disconnect ${name}</button></div>
      </form>`;
    }).join('')}</div>
  </section>`;
}

function setupCollaborators() {
  return `<section class="setup-step" aria-label="Optional collaborator preview">
    <h3>Preview collaboration without inviting anyone</h3>
    <p>Create a local invitation-preview record with unchecked sharing choices. It does not send a message, create an account, change membership or access, or share private project content.</p>
    <p>People provides the return path to this step and to all saved local previews.</p>
    <div class="actions"><button type="button" data-new-invitation data-setup-invitation>Create local invitation preview</button><button type="button" data-setup-step="providers">Back to Providers</button></div>
  </section>`;
}

function renderSetupStep() {
  const titles = {welcome: 'Welcome / privacy', providers: 'Providers', collaborators: 'Collaborators'};
  const descriptions = {
    welcome: 'Optional local setup. Skip it or return at any time.',
    providers: 'Optional API-key configuration for five independent providers.',
    collaborators: 'Optional local invitation previews with no delivery or membership changes.',
  };
  $('setup-title').textContent = titles[setupStep];
  $('setup-description').textContent = descriptions[setupStep];
  localStatus('setup-status', '');
  $('setup-content').innerHTML = setupProgress() + (setupStep === 'welcome' ? setupWelcome() : setupStep === 'providers' ? setupProviders() : setupCollaborators()) + setupActions();
  if (!$('setup-dialog').open) $('setup-dialog').showModal();
  $('setup-title').focus();
}

function openSetup(step = 'welcome') {
  if (!ONBOARDING_STEPS.includes(step)) step = 'welcome';
  if (!$('setup-dialog').open) {
    setupReturnFocus = {step: document.activeElement?.dataset?.openSetup || step};
  }
  setupStep = step;
  renderSetupStep();
}

function maybeShowSetup() {
  if (setupShown || $('setup-dialog').open || state.profile.onboarding?.status !== 'not_started') return;
  setupShown = true;
  openSetup('welcome');
}

function enhanceLocalPages() {
  document.querySelectorAll('[data-open-setup]').forEach(button => {
    button.setAttribute('aria-haspopup', 'dialog');
    button.setAttribute('aria-controls', 'setup-dialog');
  });
  document.querySelectorAll('[data-new-invitation],[data-invitation-id]').forEach(button => {
    button.setAttribute('aria-haspopup', 'dialog');
    if (!button.hasAttribute('data-invitation-copy') && !button.hasAttribute('data-invitation-delete')) button.setAttribute('aria-controls', 'invitation-dialog');
  });
}

async function persistOnboarding(status) {
  try {
    const payload = status === 'completed' ? {status: 'completed'} : {status: 'skipped'};
    await api('/api/onboarding', payload);
    await refresh();
    localStatus('setup-status', status === 'completed' ? 'Setup completed locally.' : 'Setup skipped for now; return from My Models or People.');
    $('setup-dialog').close();
    note(status === 'completed' ? 'Setup completed. Provider access remains unverified.' : 'Setup skipped. You can return from My Models or People.');
  } catch (error) {
    localStatus('setup-status', error.message, true);
  }
}

function updateSetupProvider(id) {
  const configured = state.providers.find(provider => provider.id === id)?.configured;
  $('setup-provider-state-' + id).textContent = configured ? 'Configured · session-only · unverified' : 'Not configured';
  $('setup-provider-state-' + id).classList.toggle('configured', Boolean(configured));
  $('setup-disconnect-' + id).classList.toggle('hidden', !configured);
}

async function configureSetupProvider(form) {
  const id = form.dataset.setupProviderForm;
  const name = ONBOARDING_PROVIDERS.find(provider => provider[0] === id)?.[1] || id;
  const keyField = form.elements.key;
  const key = keyField.value.trim();
  keyField.value = '';
  try {
    await api('/api/connect', {provider: id, key});
    await refresh();
    updateSetupProvider(id);
    localStatus('setup-status', `${name} configured for this session; access remains unverified. No provider request was made.`);
  } catch (error) {
    localStatus('setup-status', error.message, true);
  } finally {
    keyField.value = '';
  }
}

async function disconnectSetupProvider(id) {
  const name = ONBOARDING_PROVIDERS.find(provider => provider[0] === id)?.[1] || id;
  const field = $('setup-key-' + id);
  if (field) field.value = '';
  try {
    await api('/api/disconnect', {provider: id});
    await refresh();
    updateSetupProvider(id);
    localStatus('setup-status', `${name} disconnected. Other providers are unchanged; remaining configuration is session-only and unverified. No provider request was made.`);
  } catch (error) {
    localStatus('setup-status', error.message, true);
  }
}

function invitationJoinSteps() {
  return `<section class="invitation-join"><h3>Join steps</h3><ol><li>Install and open Elect Twin on the invitee’s own Mac using the authorized internal build.</li><li>Review the recipient, project, proposed role, and consent choices in this local preview.</li><li>Arrange any real project handoff separately with the owner; accepting this preview does not join a project.</li></ol><p>Internal build limitation: this internal build is ad-hoc signed, not Developer ID signed or notarized. Do not bypass Gatekeeper; public distribution requires proper signing and notarization.</p><p>No public acceptance link is generated.</p></section>`;
}

function invitationDetails(item) {
  const sharing = item.sharing || {};
  return `<dl class="invitation-fields"><div><dt>Recipient</dt><dd>${esc(item.recipient_name)}</dd></div><div><dt>Contact</dt><dd>${esc(item.contact || 'Not provided')}</dd></div><div><dt>Project</dt><dd>${esc(item.project_name)}</dd></div><div><dt>Proposed role</dt><dd>${esc(item.role)}</dd></div><div><dt>Sharing consent flags</dt><dd>Goal: ${sharing.goal ? 'selected' : 'not selected'}; Documents: ${sharing.documents ? 'selected' : 'not selected'}; History: ${sharing.history ? 'selected' : 'not selected'}</dd></div><div><dt>Status</dt><dd>${esc(item.status)} · simulated preview outcome</dd></div><div><dt>Delivery</dt><dd>${esc(item.delivery)}</dd></div><div><dt>Membership changed</dt><dd>${item.membership_changed ? 'true' : 'false'}</dd></div></dl>`;
}

function invitationCopyText(item) {
  const sharing = item.sharing || {};
  return `Local invitation preview
Recipient: ${item.recipient_name}
Contact: ${item.contact || 'Not provided'}
Project: ${item.project_name}
Proposed role: ${item.role}
Sharing consent flags only — Goal: ${sharing.goal ? 'selected' : 'not selected'}; Documents: ${sharing.documents ? 'selected' : 'not selected'}; History: ${sharing.history ? 'selected' : 'not selected'}
Preview status: ${item.status} (simulated preview outcome)

${INVITATION_CONSENT}
${INVITATION_PREVIEW_ONLY}

Join steps
1. Install and open Elect Twin on the invitee’s own Mac using the authorized internal build.
2. Review the recipient, project, proposed role, and consent choices in this local preview.
3. Arrange any real project handoff separately with the owner; accepting this preview does not join a project.
Internal build limitation: this internal build is ad-hoc signed, not Developer ID signed or notarized. Do not bypass Gatekeeper; public distribution requires proper signing and notarization.
No public acceptance link is generated. No private project content is included.`;
}

function resetInvitationCopyFallback() {
  $('invitation-copy-fallback').classList.add('hidden');
  $('invitation-copy-text').value = '';
}

function showInvitationPreview(id) {
  const mode = arguments.length > 1 ? arguments[1] : 'inviter';
  const item = (state.invitation_previews || []).find(preview => preview.id === id);
  if (!item) {
    note('That local invitation preview is not available.', true);
    return;
  }
  if (!$('invitation-dialog').open) {
    const launcher = document.activeElement;
    invitationReturnFocus = {
      id: launcher?.dataset?.invitationId || id,
      view: launcher?.dataset?.invitationInvitee !== undefined ? 'invitee' : 'inviter',
    };
  }
  activeInvitationId = id;
  invitationMode = mode === 'invitee' ? 'invitee' : 'inviter';
  $('invitation-title').textContent = invitationMode === 'invitee' ? 'Invitee preview' : 'Inviter preview';
  $('invitation-description').textContent = INVITATION_CONSENT;
  localStatus('invitation-status', '');
  resetInvitationCopyFallback();
  const statusActions = item.status === 'draft' ? (invitationMode === 'invitee' ? `<button type="button" class="primary" data-invitation-status="${esc(id)}" data-status="accepted_preview">Accept simulated preview</button><button type="button" data-invitation-status="${esc(id)}" data-status="declined_preview">Decline simulated preview</button>` : `<button type="button" data-invitation-status="${esc(id)}" data-status="cancelled_preview">Cancel simulated preview</button>`) : '';
  $('invitation-content').innerHTML = `<p class="invitation-consent"><strong>${INVITATION_CONSENT}</strong></p><p>${INVITATION_PREVIEW_ONLY}</p>${invitationDetails(item)}${invitationJoinSteps()}<div class="actions"><button type="button" data-invitation-mode="${invitationMode === 'invitee' ? 'inviter' : 'invitee'}">View ${invitationMode === 'invitee' ? 'inviter' : 'invitee'} preview</button>${statusActions}<button type="button" data-invitation-copy="${esc(id)}">Copy local explanatory preview</button><button type="button" class="danger" data-invitation-delete="${esc(id)}">Delete local preview</button></div>`;
  if (!$('invitation-dialog').open) $('invitation-dialog').showModal();
  $('invitation-title').focus();
}

function openInvitationCreate() {
  if (!$('invitation-dialog').open) {
    invitationReturnFocus = {
      id: '',
      createSource: document.activeElement?.dataset?.setupInvitation !== undefined ? 'setup' : 'page',
    };
  }
  activeInvitationId = '';
  invitationMode = 'create';
  $('invitation-title').textContent = 'Create local invitation preview';
  $('invitation-description').textContent = INVITATION_CONSENT;
  localStatus('invitation-status', '');
  resetInvitationCopyFallback();
  const projects = state.projects || [];
  $('invitation-content').innerHTML = projects.length ? `<p>${INVITATION_PREVIEW_ONLY}</p><form data-invitation-create class="invitation-create"><label for="invitation-recipient">Recipient display name</label><input id="invitation-recipient" name="recipient_name" maxlength="200" required><label for="invitation-contact">Optional contact</label><input id="invitation-contact" name="contact" maxlength="320" autocomplete="off"><label for="invitation-project">Project reference</label><select id="invitation-project" name="project_id" required>${projects.map(project => `<option value="${esc(project.id)}">${esc(project.name)}</option>`).join('')}</select><label for="invitation-role">Proposed role</label><select id="invitation-role" name="role"><option>Reviewer</option><option>Editor</option><option>Viewer</option></select><fieldset><legend>Sharing consent flags · unchecked by default</legend><label><input type="checkbox" name="sharing_goal"> Project goal</label><label><input type="checkbox" name="sharing_documents"> Document references only</label><label><input type="checkbox" name="sharing_history"> History references only</label></fieldset><p>These choices record consent flags only. No private project content is copied or shared.</p><div class="actions"><button type="submit" class="primary">Create local preview</button><button type="button" data-invitation-close>Not now</button></div></form>` : '<p>Create a local project before creating an invitation preview. Nothing was sent or shared.</p><div class="actions"><button type="button" data-invitation-close>Not now</button></div>';
  if (!$('invitation-dialog').open) $('invitation-dialog').showModal();
  $('invitation-title').focus();
}

function invitationPreviewList() {
  const items = state.invitation_previews || [];
  return `<section class="section invitation-previews" aria-labelledby="invitation-list-title"><div class="sectionhead"><div><h2 id="invitation-list-title">Local invitation previews</h2><p class="small">No delivery, accounts, membership, access, or private content sharing.</p></div><button type="button" data-new-invitation>Create local preview</button></div>${items.length ? `<div class="list">${items.map(item => `<article class="list-row"><div><span class="badge">${esc(item.status)} · simulated</span><h3>${esc(item.recipient_name)}</h3><p>${esc(item.project_name)} · ${esc(item.role)}</p><small>${INVITATION_CONSENT}</small></div><div class="actions"><button type="button" data-invitation-id="${esc(item.id)}" data-invitation-view="inviter">Inviter preview</button><button type="button" data-invitation-id="${esc(item.id)}" data-invitation-invitee>Invitee preview</button><button type="button" data-invitation-id="${esc(item.id)}" data-invitation-copy="${esc(item.id)}">Copy local preview</button><button type="button" class="danger" data-invitation-id="${esc(item.id)}" data-invitation-delete="${esc(item.id)}">Delete</button></div></article>`).join('')}</div>` : '<p class="empty">No local invitation previews. Creating one never sends an invitation.</p>'}</section>`;
}

async function createInvitationPreview(form) {
  const fields = form.elements;
  const data = {
    recipient_name: fields.recipient_name.value.trim(),
    contact: fields.contact.value.trim(),
    project_id: fields.project_id.value,
    role: fields.role.value,
    sharing: {
      goal: fields.sharing_goal.checked,
      documents: fields.sharing_documents.checked,
      history: fields.sharing_history.checked,
    },
  };
  try {
    const created = await api('/api/invitation-preview', data);
    await refresh();
    showInvitationPreview(created.id, 'inviter');
    localStatus('invitation-status', 'Local preview created with your sharing consent flags. Nothing was sent and no private project content was shared.');
  } catch (error) {
    localStatus('invitation-status', error.message, true);
  }
}

async function updateInvitationStatus(id, status) {
  if (!['accepted_preview', 'declined_preview', 'cancelled_preview'].includes(status)) return;
  try {
    await api('/api/invitation-preview/status', {id, status});
    await refresh();
    showInvitationPreview(id, invitationMode);
    localStatus('invitation-status', 'Simulated outcome saved; this changes only this preview record. Nothing was sent, no account/membership/access changed, and no private project content was shared.');
  } catch (error) {
    localStatus('invitation-status', error.message, true);
  }
}

async function copyInvitationPreview(id) {
  const item = (state.invitation_previews || []).find(preview => preview.id === id);
  if (!item) return;
  const text = invitationCopyText(item);
  resetInvitationCopyFallback();
  try {
    await navigator.clipboard.writeText(text);
    localStatus('invitation-status', 'Local explanatory preview copied. Nothing was sent and no acceptance link was created.');
  } catch {
    const fallback = $('invitation-copy-text');
    $('invitation-copy-fallback').classList.remove('hidden');
    fallback.value = text;
    fallback.readOnly = true;
    fallback.focus();
    fallback.select();
    localStatus('invitation-status', 'Clipboard unavailable. Select and copy the local explanatory preview manually; nothing was sent.');
  }
}

async function deleteInvitationPreview(id) {
  try {
    await api('/api/invitation-preview/delete', {id});
    await refresh();
    if ($('invitation-dialog').open) $('invitation-dialog').close();
    note('Local invitation preview deleted. Nothing was sent and no membership or access changed.');
  } catch (error) {
    if ($('invitation-dialog').open) localStatus('invitation-status', error.message, true);
    else note(error.message, true);
  }
}

function restoreSetupLauncher() {
  const launchers = [...document.querySelectorAll('[data-open-setup]')].filter(button => button.isConnected);
  const equivalent = launchers.find(button => button.dataset.openSetup === setupReturnFocus?.step) || launchers[0];
  equivalent?.focus();
  setupReturnFocus = null;
}

function restoreInvitationLauncher() {
  const descriptor = invitationReturnFocus || {};
  const launchers = [...document.querySelectorAll('[data-invitation-id]')].filter(button => button.isConnected);
  const equivalent = descriptor.id && launchers.find(button => {
    if (button.dataset.invitationId !== descriptor.id) return false;
    return descriptor.view === 'invitee' ? button.dataset.invitationInvitee !== undefined : button.dataset.invitationInvitee === undefined;
  });
  const fallback = [...document.querySelectorAll('[data-new-invitation]')].find(button => {
    const source = button.dataset.setupInvitation !== undefined ? 'setup' : 'page';
    return button.isConnected && source === (descriptor.createSource || 'page');
  });
  (equivalent || fallback)?.focus();
  invitationReturnFocus = null;
}

if (typeof document !== 'undefined') {
  $('page').addEventListener('click', async event => {
    const button = event.target.closest('[data-open-setup],[data-new-invitation],[data-invitation-id]');
    if (!button) return;
    if (button.dataset.openSetup !== undefined) return openSetup(button.dataset.openSetup);
    if (button.dataset.newInvitation !== undefined) return openInvitationCreate();
    if (button.dataset.invitationCopy !== undefined) return copyInvitationPreview(button.dataset.invitationCopy);
    if (button.dataset.invitationDelete !== undefined) return deleteInvitationPreview(button.dataset.invitationDelete);
    if (button.dataset.invitationId) return showInvitationPreview(button.dataset.invitationId, button.dataset.invitationInvitee !== undefined ? 'invitee' : 'inviter');
  });

  $('setup-dialog').addEventListener('click', async event => {
    const button = event.target.closest('[data-setup-step],[data-setup-skip],[data-setup-not-now],[data-setup-complete],[data-setup-disconnect],[data-new-invitation]');
    if (!button) return;
    if (button.dataset.setupStep) return openSetup(button.dataset.setupStep);
    if (button.dataset.setupSkip !== undefined) return persistOnboarding('skipped');
    if (button.dataset.setupNotNow !== undefined) return persistOnboarding('skipped');
    if (button.dataset.setupComplete !== undefined) return persistOnboarding('completed');
    if (button.dataset.setupDisconnect) return disconnectSetupProvider(button.dataset.setupDisconnect);
    if (button.dataset.newInvitation !== undefined) return openInvitationCreate();
  });
  $('setup-dialog').addEventListener('submit', event => {
    const form = event.target.closest('[data-setup-provider-form]');
    if (!form) return;
    event.preventDefault();
    return configureSetupProvider(form);
  });
  $('setup-dialog').addEventListener('close', restoreSetupLauncher);

  $('invitation-dialog').addEventListener('click', async event => {
    const button = event.target.closest('[data-invitation-status],[data-invitation-copy],[data-invitation-delete],[data-invitation-mode],[data-invitation-close]');
    if (!button) return;
    if (button.dataset.invitationStatus) return updateInvitationStatus(button.dataset.invitationStatus, button.dataset.status);
    if (button.dataset.invitationCopy) return copyInvitationPreview(button.dataset.invitationCopy);
    if (button.dataset.invitationDelete) return deleteInvitationPreview(button.dataset.invitationDelete);
    if (button.dataset.invitationMode) return showInvitationPreview(activeInvitationId, button.dataset.invitationMode);
    if (button.dataset.invitationClose !== undefined) return $('invitation-dialog').close();
  });
  $('invitation-dialog').addEventListener('submit', event => {
    const form = event.target.closest('[data-invitation-create]');
    if (!form) return;
    event.preventDefault();
    return createInvitationPreview(form);
  });
  $('invitation-dialog').addEventListener('close', restoreInvitationLauncher);
  if (typeof page !== 'undefined' && page === 'home' && typeof state !== 'undefined' && state.profile?.onboarding?.status === 'not_started') {
    enhanceLocalPages();
    maybeShowSetup();
  }
}
