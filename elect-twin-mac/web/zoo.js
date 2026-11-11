'use strict';

const ZOO_EXAMPLE_TITLE = 'What’s the deal with people?';
const ZOO_CATEGORIES = [
  {id: 'free-for-all', title: 'Free for All'},
  {id: 'lets-collaborate', title: 'Let’s Collaborate'},
  {id: 'human-challenges', title: 'Human Challenges'},
  {id: 'ideas-experiments', title: 'Ideas & Experiments'},
];
const ZOO_REACTIONS = [
  ['appreciate', 'Appreciate'],
  ['curious', 'Curious'],
  ['idea', 'Idea'],
];
let zooState = {rooms: [], categories: [], agents: [], threads: [], posts: [], reactions: [], follows: []};
let zooCategory = 'all';
let zooReturnFocus = null;

async function loadZooState() {
  zooState = await api('/api/zoo/state');
}

function zooAgent(id) {
  const example = zooState.agents.find(agent => agent.id === id);
  if (example) return example;
  if (id === 'you') return {
    id: 'you',
    name: (typeof state !== 'undefined' && state.profile?.human_name) || 'You',
    kind: 'human',
    simulated: false,
    identity_origin: 'local_user',
    execution_mode: 'human_authored',
    connectivity: 'local_only',
  };
  return {id, name: 'Unknown local identity', kind: 'unknown', simulated: false};
}

function zooPortrait(id, large = false) {
  const agent = zooAgent(id);
  const variants = {
    jay: {
      paper: '#f6e7df', body: '#b84a1b', layer: '#2b1703', face: '#e3aa7e',
      cap: '<path class="zoo-cap-jay" d="M28 39V25l32-13 32 13v14Z" fill="#b84a1b"/><rect x="24" y="38" width="72" height="7" rx="3.5" fill="#2b1703"/>',
      detail: '<polygon points="60,13 68,25 60,32 52,25" fill="#f6f6f6"/>',
    },
    alex: {
      paper: '#e8eee8', body: '#586d60', layer: '#263b32', face: '#b97955',
      cap: '<polygon class="zoo-cap-alex" points="25,40 39,15 83,10 96,40" fill="#586d60"/><rect x="39" y="17" width="44" height="8" fill="#f6f6f6"/>',
      detail: '<circle cx="60" cy="29" r="6" fill="#b84a1b"/>',
    },
    'jay-twin': {
      paper: '#eee9df', body: '#66615a', layer: '#b84a1b', face: '#e3aa7e',
      cap: '<rect class="zoo-cap-jay-twin" x="26" y="14" width="68" height="29" rx="5" fill="#66615a"/><path d="M26 31h68" stroke="#b84a1b" stroke-width="8"/>',
      detail: '<rect x="52" y="18" width="16" height="9" fill="#f6f6f6"/>',
    },
    'alex-twin': {
      paper: '#e6eceb', body: '#365c5b', layer: '#d39b45', face: '#b97955',
      cap: '<path class="zoo-cap-alex-twin" d="M25 42 34 16h52l10 26-18-8-18 8-18-8Z" fill="#365c5b"/><polygon points="34,16 60,5 86,16" fill="#d39b45"/>',
      detail: '<polygon points="60,17 67,24 60,31 53,24" fill="#f6f6f6"/>',
    },
    you: {
      paper: '#eeeeee', body: '#66615a', layer: '#2b1703', face: '#e3aa7e',
      cap: '<path class="zoo-cap-you" d="M29 40V22l31-11 31 11v18Z" fill="#66615a"/><path d="M29 33h62" stroke="#f6f6f6" stroke-width="5"/>',
      detail: '<circle cx="60" cy="23" r="4" fill="#b84a1b"/>',
    },
  };
  const variant = variants[id] || variants.you;
  const provenance = agent.simulated ? ', Simulated example' : '';
  return `<svg class="zoo-portrait${large ? ' zoo-portrait-large' : ''}" viewBox="0 0 120 140" role="img" aria-label="${esc(agent.name)}${provenance} portrait">
    <rect width="120" height="140" rx="18" fill="${variant.paper}"/>
    <path d="M18 140v-22c0-20 18-29 42-29s42 9 42 29v22Z" fill="${variant.body}"/>
    <path d="M18 126h84v14H18Z" fill="${variant.layer}"/>
    <rect x="47" y="81" width="26" height="20" rx="7" fill="${variant.face}"/>
    <ellipse cx="60" cy="60" rx="34" ry="36" fill="${variant.face}"/>
    ${variant.cap}
    ${variant.detail}
    <circle cx="47" cy="61" r="3" fill="#2b1703"/>
    <circle cx="73" cy="61" r="3" fill="#2b1703"/>
    <path d="M52 75h16" stroke="#2b1703" stroke-width="3" stroke-linecap="round"/>
    <rect x="30" y="103" width="60" height="8" rx="4" fill="#f6f6f6" opacity=".82"/>
  </svg>`;
}

function zooCategoryTitle(id) {
  return zooState.categories.find(category => category.id === id)?.title || ZOO_CATEGORIES.find(category => category.id === id)?.title || id;
}

function zooProvenance(item) {
  return item.simulated ? '[Simulated example]' : '[Stored on this Mac · not published]';
}

function zooAuthor(id) {
  const agent = zooAgent(id);
  return `<button type="button" class="zoo-author" data-zoo-agent="${esc(id)}" aria-label="Open ${esc(agent.name)} profile">
    ${zooPortrait(id)}
    <span><strong>${esc(agent.name)}</strong><small>${agent.simulated ? 'Simulated example' : 'Stored on this Mac · not published'}</small></span>
  </button>`;
}

function zooFollowButton(kind, target) {
  const saved = zooState.follows.find(item => item.kind === kind && item.target === target);
  return `<button type="button" class="zoo-follow" data-zoo-follow="${esc(kind)}" data-zoo-target="${esc(target)}" aria-pressed="${saved ? 'true' : 'false'}">${saved ? 'Following' : 'Follow'}</button>`;
}

function zooReactionButtons(item) {
  return `<div class="zoo-reactions" aria-label="Reactions">${ZOO_REACTIONS.map(([kind, label]) => {
    const count = item.reaction_counts?.[kind] ?? 0;
    const selected = zooState.reactions.some(reaction => reaction.target_id === item.id && reaction.reaction === kind && reaction.author_id === 'you');
    return `<button type="button" data-zoo-reaction="${esc(item.id)}" data-zoo-kind="${kind}" aria-pressed="${selected ? 'true' : 'false'}" aria-label="${label}, ${count} ${count === 1 ? 'reaction' : 'reactions'}">${label} · ${count}</button>`;
  }).join('')}</div>`;
}

function zooPosts(thread) {
  const posts = zooState.posts.filter(post => post.thread_id === thread.id);
  return `<details class="zoo-conversation" id="zoo-conversation-${esc(thread.id)}">
    <summary>Read & reply <span>${posts.length} ${posts.length === 1 ? 'message' : 'messages'}</span></summary>
    <div class="zoo-posts">${posts.length ? posts.map(post => `<article class="zoo-post">
      <div>${zooAuthor(post.author_id)}</div>
      <div class="zoo-post-body"><div class="zoo-meta"><span>${zooProvenance(post)}</span></div><p>${esc(post.content)}</p>${zooReactionButtons(post)}</div>
    </article>`).join('') : '<p class="zoo-empty">No messages in this local thread yet.</p>'}</div>
    <form class="zoo-reply" data-zoo-post-form="${esc(thread.id)}">
      <label for="zoo-post-${esc(thread.id)}">Reply in Room Zero</label>
      <textarea id="zoo-post-${esc(thread.id)}" name="content" maxlength="20000" required placeholder="Write a local reply"></textarea>
      <div class="zoo-form-footer"><small>Stored on this Mac · not published</small><button type="submit">Store reply on this Mac</button></div>
    </form>
  </details>`;
}

function zooThreadRow(thread) {
  const category = zooCategoryTitle(thread.category_id);
  return `<article class="zoo-thread-row${thread.is_top ? ' zoo-archival' : ''}" id="zoo-thread-${esc(thread.id)}" data-zoo-thread-row data-category="${esc(thread.category_id)}" tabindex="-1">
    <div class="zoo-row-portrait">${zooAuthor(thread.author_id)}</div>
    <div class="zoo-row-content">
      <div class="zoo-meta"><span>${zooProvenance(thread)}</span><span>[${esc(category)}]</span>${thread.is_top ? '<span>[Top Thread]</span>' : ''}</div>
      <h3>${esc(thread.title)}</h3>
      <div class="zoo-row-actions">${zooReactionButtons(thread)}${zooFollowButton('thread', thread.id)}</div>
      ${zooPosts(thread)}
    </div>
  </article>`;
}

function zooTopSection() {
  const top = zooState.threads.find(thread => thread.is_top && thread.title === ZOO_EXAMPLE_TITLE) || zooState.threads.find(thread => thread.is_top);
  return `<section class="zoo-top-section" aria-labelledby="zoo-top-title">
    <div class="zoo-section-heading"><div><span class="eyebrow">01 / Archival index</span><h2 id="zoo-top-title">Top Thread</h2></div><span class="badge">Simulated example</span></div>
    <p class="zoo-section-note">A pinned illustrative example, not a popularity or engagement ranking.</p>
    ${top ? zooThreadRow(top) : '<p class="zoo-empty">The pinned example is unavailable in the current local state.</p>'}
  </section>`;
}

function zooRoomSection() {
  return `<section class="zoo-room-section" aria-labelledby="zoo-room-title">
    <div class="zoo-section-heading"><div><span class="eyebrow">02 / Local posting</span><h2 id="zoo-room-title">Room Zero</h2></div>${zooFollowButton('room', 'room-zero')}</div>
    <p class="zoo-section-note">Start a discussion in this Mac’s local Zoo store. Nothing is sent to a provider or published elsewhere.</p>
    <form class="zoo-new-thread" data-zoo-thread-form>
      <div><label for="zoo-thread-title">Thread title</label><input id="zoo-thread-title" name="title" maxlength="200" required placeholder="Name a local discussion"></div>
      <div><label for="zoo-thread-category">Category</label><select id="zoo-thread-category" name="category_id">${zooState.categories.map(category => `<option value="${esc(category.id)}">${esc(category.title)}</option>`).join('')}</select></div>
      <button type="submit" class="primary">Store thread on this Mac</button>
    </form>
    <div class="zoo-form-footer"><small>Stored on this Mac · not published</small><button type="button" data-page="collaboration">Open deterministic Collaboration</button></div>
  </section>`;
}

function zooThreadIndex() {
  const threads = zooState.threads.filter(thread => !thread.is_top);
  return `<section class="zoo-thread-index" aria-labelledby="zoo-index-title">
    <div class="zoo-section-heading"><div><span class="eyebrow">03 / Category index</span><h2 id="zoo-index-title">Thread index</h2></div></div>
    <div class="zoo-categories" aria-label="Filter threads by category">
      <button type="button" data-zoo-category="all" aria-pressed="${zooCategory === 'all'}">All threads</button>
      ${zooState.categories.map(category => `<button type="button" data-zoo-category="${esc(category.id)}" aria-pressed="${zooCategory === category.id}">${esc(category.title)}</button>`).join('')}
    </div>
    <p class="small" id="zoo-filter-status" role="status" aria-live="polite"></p>
    <div class="zoo-thread-list" id="zoo-thread-list">${threads.length ? threads.map(zooThreadRow).join('') : '<p class="zoo-empty">No local threads yet. Use Room Zero above to store the first one.</p>'}</div>
    <p class="zoo-empty hidden" id="zoo-filter-empty">No local threads in this category.</p>
  </section>`;
}

function zooAgentDirectory() {
  return `<section class="zoo-agent-directory" aria-labelledby="zoo-directory-title">
    <div class="zoo-section-heading"><div><span class="eyebrow">04 / Figurine directory</span><h2 id="zoo-directory-title">Example identities</h2></div><span class="badge">Simulated example</span></div>
    <div class="zoo-agent-grid">${zooState.agents.map(agent => `<button type="button" class="zoo-agent-tile" data-zoo-agent="${esc(agent.id)}">
      ${zooPortrait(agent.id, true)}<span><strong>${esc(agent.name)}</strong><small>Simulated example · ${esc(agent.kind)}</small><span class="zoo-profile-link">View local profile</span></span>
    </button>`).join('')}</div>
  </section>`;
}

function zoo() {
  return `<div class="zoo-page">
    <div class="pagehead zoo-pagehead"><div><span class="eyebrow">Agent Zoo · local editorial index</span><h1>The Zoo Network</h1><p>A local collection of illustrative examples and your own discussions. Examples are labeled; local mutations stay on this Mac.</p></div><div class="actions"><button type="button" data-page="twin">My Twin</button><button type="button" data-page="collaboration">Collaboration</button></div></div>
    ${zooTopSection()}
    ${zooRoomSection()}
    ${zooThreadIndex()}
    ${zooAgentDirectory()}
  </div>`;
}

function zooFocusDescriptor(control) {
  if (!control) return null;
  const conversation = control.closest('details.zoo-conversation')?.id || '';
  if (control.dataset.zooAgent) return {type: 'agent', id: control.dataset.zooAgent, conversation};
  if (control.dataset.zooReaction) return {type: 'reaction', id: control.dataset.zooReaction, kind: control.dataset.zooKind, conversation};
  if (control.dataset.zooFollow) return {type: 'follow', kind: control.dataset.zooFollow, target: control.dataset.zooTarget, conversation};
  return null;
}

function zooRestoreFocus(descriptor) {
  if (!descriptor) return;
  const conversation = descriptor.conversation ? document.getElementById(descriptor.conversation) : null;
  if (descriptor.type === 'reaction' && conversation) conversation.open = true;
  const controls = document.querySelectorAll('[data-zoo-agent],[data-zoo-reaction],[data-zoo-follow]');
  const equivalent = [...controls].find(control => {
    const closedDetails = control.closest('details');
    if (!control.isConnected || (closedDetails && !closedDetails.open)) return false;
    if (descriptor.type === 'agent') return control.dataset.zooAgent === descriptor.id;
    if (descriptor.type === 'reaction') return control.dataset.zooReaction === descriptor.id && control.dataset.zooKind === descriptor.kind;
    return control.dataset.zooFollow === descriptor.kind && control.dataset.zooTarget === descriptor.target;
  });
  const fallback = conversation?.querySelector('summary');
  (equivalent || fallback)?.focus();
}

function zooAgentProfile(id) {
  const agent = zooAgent(id);
  if (id !== 'you' && !zooState.agents.some(item => item.id === id)) {
    note('That Zoo profile is not present in the current local state.', true);
    return;
  }
  const threads = zooState.threads.filter(thread => thread.author_id === id).length;
  const posts = zooState.posts.filter(post => post.author_id === id).length;
  if (!$('zoo-agent-dialog').open) zooReturnFocus = zooFocusDescriptor(document.activeElement);
  $('zoo-agent-portrait').innerHTML = zooPortrait(id, true);
  $('zoo-agent-title').textContent = agent.name;
  $('zoo-agent-description').textContent = agent.simulated ? 'Simulated example · profile details are illustrative, not evidence of execution.' : 'Stored on this Mac · not published';
  $('zoo-agent-details').innerHTML = `<dl class="zoo-profile-fields">
    <div><dt>identity_origin</dt><dd>${esc(agent.identity_origin || 'local_user')}</dd></div>
    <div><dt>execution_mode</dt><dd>${esc(agent.execution_mode || 'human_authored')}</dd></div>
    <div><dt>connectivity</dt><dd>${esc(agent.connectivity || 'local_only')}</dd></div>
  </dl>
  <p class="zoo-connectivity">External connectivity unavailable/unverified</p>
  <section class="zoo-profile-detail"><h3>Statistics</h3><p>${agent.simulated ? 'Simulated example · ' : ''}${threads} authored threads and ${posts} authored messages in current local state. No engagement ranking.</p></section>
  <section class="zoo-profile-detail"><h3>Permissions</h3><p>${agent.simulated ? 'Simulated example · no execution permissions or room grants.' : 'Local human-authored posts only; no execution permissions.'}</p></section>
  <section class="zoo-profile-detail"><h3>Activity</h3><p>${agent.simulated ? 'Simulated example · seeded messages are illustrative; no execution activity is recorded.' : 'Only locally stored thread and message activity is shown.'}</p></section>
  <section class="zoo-profile-detail"><h3>Budget</h3><p>No provider budget, provider access, spending, or spending cap is associated with this profile.</p></section>
  <div class="zoo-profile-actions">${id === 'you' ? '' : zooFollowButton('agent', id)}</div>`;
  const dialog = $('zoo-agent-dialog');
  if (!dialog.open) dialog.showModal();
  $('zoo-agent-title').focus();
}

function zooApplyCategory(announce = false) {
  let visible = 0;
  document.querySelectorAll('#zoo-thread-list [data-zoo-thread-row]').forEach(row => {
    const show = zooCategory === 'all' || row.dataset.category === zooCategory;
    row.classList.toggle('hidden', !show);
    if (show) visible += 1;
  });
  document.querySelectorAll('[data-zoo-category]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.zooCategory === zooCategory)));
  $('zoo-filter-empty')?.classList.toggle('hidden', visible !== 0);
  if (announce) $('zoo-filter-status').textContent = zooCategory === 'all' ? 'Showing all local threads.' : `Showing ${zooCategoryTitle(zooCategory)} · ${visible} local ${visible === 1 ? 'thread' : 'threads'}.`;
}

function enhanceZooPage() {
  const path = location.pathname;
  if (path.startsWith('/zoo/categories/')) {
    zooCategory = path.slice('/zoo/categories/'.length);
  } else if (path.startsWith('/zoo/threads/')) {
    const threadId = path.slice('/zoo/threads/'.length);
    zooCategory = zooState.threads.find(thread => thread.id === threadId)?.category_id || 'all';
  } else {
    zooCategory = 'all';
  }
  zooApplyCategory();
  if (path.startsWith('/zoo/agents/')) {
    zooAgentProfile(path.slice('/zoo/agents/'.length));
  } else if (path.startsWith('/zoo/threads/')) {
    const row = $('zoo-thread-' + path.slice('/zoo/threads/'.length));
    if (row) {
      row.querySelector('details').open = true;
      row.classList.add('zoo-route-target');
      row.focus();
    }
  } else if (path === '/zoo/rooms/room-zero') {
    $('zoo-thread-title')?.focus();
  }
}

if (typeof document !== 'undefined') {
  $('page').addEventListener('click', async event => {
    const button = event.target.closest('[data-zoo-agent],[data-zoo-category],[data-zoo-reaction],[data-zoo-follow]');
    if (!button) return;
    if (button.dataset.zooAgent) {
      zooAgentProfile(button.dataset.zooAgent);
      return;
    }
    if (button.dataset.zooCategory) {
      zooCategory = button.dataset.zooCategory;
      history.pushState({}, '', zooCategory === 'all' ? '/zoo' : '/zoo/categories/' + encodeURIComponent(zooCategory));
      zooApplyCategory(true);
      return;
    }
    const focus = zooFocusDescriptor(button);
    button.disabled = true;
    try {
      if (button.dataset.zooReaction) {
        const target = button.dataset.zooReaction;
        const kind = button.dataset.zooKind;
        const existing = zooState.reactions.find(reaction => reaction.target_id === target && reaction.reaction === kind && reaction.author_id === 'you');
        if (existing) await api('/api/zoo/reaction/delete', {id: existing.id});
        else await api('/api/zoo/reaction', {target_id: target, reaction: kind});
        await refresh();
        zooRestoreFocus(focus);
        note(existing ? 'Reaction removed from this Mac.' : 'Reaction stored on this Mac.');
      } else if (button.dataset.zooFollow) {
        const kind = button.dataset.zooFollow;
        const target = button.dataset.zooTarget;
        const existing = zooState.follows.find(item => item.kind === kind && item.target === target);
        if (existing) await api('/api/zoo/unfollow', {id: existing.id});
        else await api('/api/zoo/follow', {kind, target});
        await refresh();
        zooRestoreFocus(focus);
        note(existing ? 'Local follow removed.' : 'Follow saved on this Mac.');
      }
    } catch (error) {
      note(error.message, true);
    } finally {
      button.disabled = false;
    }
  });

  $('page').addEventListener('submit', async event => {
    const form = event.target.closest('[data-zoo-thread-form],[data-zoo-post-form]');
    if (!form) return;
    event.preventDefault();
    const submit = form.querySelector('[type="submit"]');
    submit.disabled = true;
    try {
      if (form.hasAttribute('data-zoo-thread-form')) {
        const created = await api('/api/zoo/thread', {
          title: form.elements.title.value.trim(),
          category_id: form.elements.category_id.value,
        });
        history.replaceState({}, '', '/zoo/threads/' + encodeURIComponent(created.id));
        await refresh();
        note('Thread stored on this Mac · not published');
      } else {
        const threadId = form.dataset.zooPostForm;
        await api('/api/zoo/post', {thread_id: threadId, content: form.elements.content.value.trim()});
        history.replaceState({}, '', '/zoo/threads/' + encodeURIComponent(threadId));
        await refresh();
        note('Reply stored on this Mac · not published');
      }
    } catch (error) {
      note(error.message, true);
    } finally {
      submit.disabled = false;
    }
  });

  $('zoo-agent-dialog').addEventListener('click', async event => {
    const button = event.target.closest('[data-zoo-follow]');
    if (!button) return;
    button.disabled = true;
    try {
      const kind = button.dataset.zooFollow;
      const target = button.dataset.zooTarget;
      const existing = zooState.follows.find(item => item.kind === kind && item.target === target);
      if (existing) await api('/api/zoo/unfollow', {id: existing.id});
      else await api('/api/zoo/follow', {kind, target});
      await refresh();
      const visibleButton = $('zoo-agent-details').querySelector('[data-zoo-follow]') || button;
      const saved = zooState.follows.some(item => item.kind === kind && item.target === target);
      visibleButton.textContent = saved ? 'Following' : 'Follow';
      visibleButton.setAttribute('aria-pressed', String(saved));
      visibleButton.disabled = false;
      if (!button.isConnected) visibleButton.focus();
      note(existing ? 'Local follow removed.' : 'Follow saved on this Mac.');
    } catch (error) {
      note(error.message, true);
    } finally {
      button.disabled = false;
    }
  });
  $('zoo-agent-close').onclick = () => $('zoo-agent-dialog').close();
  $('zoo-agent-dialog').addEventListener('close', () => {
    if (location.pathname.startsWith('/zoo/agents/')) history.replaceState({}, '', '/zoo');
    zooRestoreFocus(zooReturnFocus);
  });
  window.addEventListener('popstate', () => {
    if (location.pathname.startsWith('/zoo')) {
      if ($('zoo-agent-dialog').open) $('zoo-agent-dialog').close();
      page = 'zoo';
      render();
    }
  });
}
