/* ═══════════════════════════════════════════════════
   SAATHI AI v2 — Complete Frontend Application
   ═══════════════════════════════════════════════════ */
'use strict';

const API = 'https://saathi-backend-rdli.onrender.com/api';
const TK = 'saathi_token';
const UK = 'saathi_user';

/* ── State ──────────────────────────────────────── */
const S = {
  docs: [],
  activeDocId: null,
  selectedIds: new Set(),
  multiMode: false,
  tab: 'chat',
  theme: localStorage.getItem('saathi-theme') || 'light',

  flashcards: [],
  fcCount: 10,
  fcDone: 0,

  examQs: [],
  examCount: 5,
  examCorrect: 0,
  examAnswered: 0,

  /* Podcast */
  podSegs: [],
  podScript: '',
  podPlaying: false,
  podPaused: false,
  podIdx: 0,
  podRate: 1,

  summaryType: 'short',

  mayaGestureTimer: null,
  mayaGestureStep: 0,
};


/* ── DOM helpers ────────────────────────────────── */
const $ = id => document.getElementById(id);
const $$ = sel => document.querySelectorAll(sel);


/* ══════════════════════════════════════════════════
   BROWSER VOICES
   ══════════════════════════════════════════════════ */

let availableVoices = [];


/*
 * Load all voices available from the browser/OS.
 *
 * Browser voices are sometimes loaded asynchronously,
 * so we also listen for "voiceschanged".
 */
function loadVoices() {

  if (!('speechSynthesis' in window)) {
    console.warn('Speech synthesis is not supported.');
    return;
  }

  availableVoices = speechSynthesis.getVoices();

  console.log(
    'Available browser voices:',
    availableVoices.map(
      voice => `${voice.name} (${voice.lang})`
    )
  );
}


loadVoices();


if ('speechSynthesis' in window) {
  speechSynthesis.onvoiceschanged = loadVoices;
}


/*
 * Select a browser voice for Maya or Alex.
 *
 * We try to find a suitable English voice first.
 * If the preferred voice is unavailable, we fall
 * back to another English voice.
 */
function getVoiceForSpeaker(speaker) {

  if (!availableVoices.length) {
    return null;
  }

  const englishVoices = availableVoices.filter(voice =>
    voice.lang &&
    voice.lang.toLowerCase().startsWith('en')
  );

  if (!englishVoices.length) {
    return null;
  }

  const isMaya =
    String(speaker).toLowerCase() === 'maya';

  const preferred = isMaya
    ? [
      'jenny',
      'aria',
      'zira',
      'samantha',
      'hazel',
      'heera'
    ]
    : [
      'guy',
      'david',
      'ryan',
      'mark',
      'george'
    ];

  /*
   * Prefer natural/neural/online voices.
   */
  const naturalVoices = englishVoices.filter(v => {
    const name = v.name.toLowerCase();

    return (
      name.includes('natural') ||
      name.includes('neural') ||
      name.includes('online')
    );
  });

  /*
   * First try preferred speaker + natural voice.
   */
  for (const keyword of preferred) {

    const voice = naturalVoices.find(v =>
      v.name.toLowerCase().includes(keyword)
    );

    if (voice) {
      return voice;
    }
  }

  /*
   * Then try preferred speaker voice.
   */
  for (const keyword of preferred) {

    const voice = englishVoices.find(v =>
      v.name.toLowerCase().includes(keyword)
    );

    if (voice) {
      return voice;
    }
  }

  /*
   * Prefer English US/GB/India.
   */
  return (
    englishVoices.find(v =>
      /^en-(US|GB|IN)$/i.test(v.lang)
    ) ||
    englishVoices[0]
  );
}

/* ══════════════════════════════════════════════════
   BOOT
   ══════════════════════════════════════════════════ */

document.addEventListener('DOMContentLoaded', boot);


async function boot() {

  const token = localStorage.getItem(TK);

  // No token → go directly to login
  if (!token) {
    location.replace('login.html');
    return;
  }

  try {

    const r = await fetch(
      `${API}/auth/me`,
      {
        headers: authHdr()
      }
    );

    // Invalid/expired token
    if (!r.ok) {
      signOut();
      return;
    }

    const d = await r.json();

    localStorage.setItem(
      UK,
      JSON.stringify(d.user)
    );

    // Authentication successful → reveal app
    document.body.classList.remove('auth-pending');
    document.body.classList.add('auth-ready');

  } catch (e) {

    console.error('Authentication check failed:', e);

    // Keep the app hidden while authentication is uncertain
    showBanner();

    return;
  }

  applyTheme(S.theme);
  renderUserBadge();

  bindEvents();

  await loadDocs();

  showUI();
}
/* ══════════════════════════════════════════════════
   THEME
   ══════════════════════════════════════════════════ */

function applyTheme(t) {

  S.theme = t;

  document.documentElement.setAttribute(
    'data-theme',
    t
  );

  localStorage.setItem(
    'saathi-theme',
    t
  );

  const btn = $('theme-btn');

  if (btn) {
    btn.textContent =
      t === 'dark' ? '☀️' : '🌙';
  }
}


/* ══════════════════════════════════════════════════
   AUTH
   ══════════════════════════════════════════════════ */

function getToken() {
  return localStorage.getItem(TK);
}


function authHdr(extra = {}) {

  const h = {
    'Content-Type': 'application/json',
    ...extra
  };

  const t = getToken();

  if (t) {
    h['Authorization'] = 'Bearer ' + t;
  }

  return h;
}


function signOut() {

  const t = getToken();

  if (t) {

    fetch(
      `${API}/auth/logout`,
      {
        method: 'POST',
        headers: authHdr()
      }
    ).catch(() => { });
  }


  localStorage.removeItem(TK);
  localStorage.removeItem(UK);

  location.replace('login.html');
}


/* ══════════════════════════════════════════════════
   API
   ══════════════════════════════════════════════════ */

async function GET(ep) {

  const r = await fetch(
    API + ep,
    {
      headers: authHdr()
    }
  );


  if (r.status === 401) {

    signOut();

    throw new Error(
      'Session expired'
    );
  }


  if (!r.ok) {

    const e =
      await r.json().catch(() => ({}));

    throw new Error(
      e.error || r.statusText
    );
  }


  return r.json();
}


async function POST(ep, body) {

  const r = await fetch(
    API + ep,
    {
      method: 'POST',
      headers: authHdr(),
      body: JSON.stringify(body)
    }
  );


  if (r.status === 401) {

    signOut();

    throw new Error(
      'Session expired'
    );
  }


  if (!r.ok) {

    const e =
      await r.json().catch(() => ({}));

    throw new Error(
      e.error || r.statusText
    );
  }


  return r.json();
}


async function DEL(ep) {

  const r = await fetch(
    API + ep,
    {
      method: 'DELETE',
      headers: authHdr()
    }
  );


  if (r.status === 401) {

    signOut();

    throw new Error(
      'Session expired'
    );
  }


  if (!r.ok) {

    const e =
      await r.json().catch(() => ({}));

    throw new Error(
      e.error || r.statusText
    );
  }


  return r.json();
}


/* ══════════════════════════════════════════════════
   SERVER BANNER
   ══════════════════════════════════════════════════ */

function showBanner() {

  if ($('srv-banner')) {
    return;
  }


  const b =
    document.createElement('div');

  b.id = 'srv-banner';

  b.className =
    'server-banner';


  b.innerHTML =
    '⚠️ Cannot reach backend on port 3001. ' +
    'Run <code>npm run dev</code> in ' +
    '<code>saathi/backend</code> ' +
    '<button onclick="location.reload()">Retry</button>';


  document.body.prepend(b);
}


/* ══════════════════════════════════════════════════
   EVENTS
   ══════════════════════════════════════════════════ */

function bindEvents() {

  /* Theme */
  $('theme-btn').onclick = () => {

    applyTheme(
      S.theme === 'dark'
        ? 'light'
        : 'dark'
    );

  };


  /* Upload */
  $('browse-btn').onclick =
    () => $('file-input').click();


  $('start-btn').onclick =
    () => $('file-input').click();


  $('file-input').onchange =
    e => handleUpload(e.target.files);


  /* Drag and drop */
  const da = $('drop-area');


  if (da) {

    da.addEventListener(
      'dragover',
      e => {

        e.preventDefault();

        da.classList.add(
          'drag-over'
        );

      }
    );


    da.addEventListener(
      'dragleave',
      () =>
        da.classList.remove(
          'drag-over'
        )
    );


    da.addEventListener(
      'drop',
      e => {

        e.preventDefault();

        da.classList.remove(
          'drag-over'
        );

        handleUpload(
          e.dataTransfer.files
        );

      }
    );

  }


  /* Tabs */
  $$('.tab').forEach(btn => {

    btn.onclick = () =>
      switchTab(
        btn.dataset.tab
      );

  });


  /* Chat */
  $('send-btn').onclick =
    sendMsg;


  $('chat-input').addEventListener(
    'keydown',
    e => {

      if (
        e.key === 'Enter' &&
        !e.shiftKey
      ) {

        e.preventDefault();

        sendMsg();
      }

    }
  );


  $('chat-input').addEventListener(
    'input',
    () =>
      autoResize(
        $('chat-input')
      )
  );


  /* Suggestions */
  const suggestions =
    $('suggestions');


  if (suggestions) {

    suggestions.addEventListener(
      'click',
      e => {

        const c =
          e.target.closest('.chip');

        if (c) {

          $('chat-input').value =
            c.textContent.replace(
              /^[^\s]+\s/,
              ''
            );

          sendMsg();
        }

      }
    );

  }


  /* Summary */
  $('gen-summary-btn').onclick =
    genSummary;


  $$('.type-btn').forEach(b => {

    b.onclick = () => {

      $$('.type-btn').forEach(
        x =>
          x.classList.remove(
            'active'
          )
      );


      b.classList.add('active');

      S.summaryType =
        b.dataset.type;


      if (S.activeDocId) {
        genSummary();
      }

    };

  });


  $('compare-btn2').onclick =
    compareDoc;


  /* Flashcards */
  $('gen-fc-btn').onclick =
    genFlashcards;


  $('fc-minus').onclick = () => {

    S.fcCount =
      Math.max(
        5,
        S.fcCount - 5
      );

    $('fc-count').textContent =
      S.fcCount;
  };


  $('fc-plus').onclick = () => {

    S.fcCount =
      Math.min(
        20,
        S.fcCount + 5
      );

    $('fc-count').textContent =
      S.fcCount;
  };


  $('shuffle-btn').onclick =
    shuffleFC;


  $('dl-fc-btn').onclick =
    dlFlashcards;


  $('diff-filter').addEventListener(
    'click',
    e => {

      const b =
        e.target.closest(
          '.diff-btn'
        );

      if (!b) {
        return;
      }


      $$('.diff-btn').forEach(
        x =>
          x.classList.remove(
            'active'
          )
      );


      b.classList.add('active');

      filterFC(
        b.dataset.diff
      );

    }
  );


  /* ═══════════════════════════════════════════════
     PODCAST
     ═══════════════════════════════════════════════ */

  $('gen-pod-btn').onclick =
    genPodcast;


  $('play-btn').onclick =
    togglePlay;


  $('stop-btn').onclick =
    stopPod;


  $('restart-btn').onclick =
    restartPodcast;


  $('dl-script-btn').onclick =
    () =>
      dlText(
        S.podScript,
        'podcast-script.txt'
      );


  $$('.sp-btn').forEach(b => {

    b.onclick = () => {

      $$('.sp-btn').forEach(
        x =>
          x.classList.remove(
            'active'
          )
      );


      b.classList.add(
        'active'
      );


      const rate =
        parseFloat(
          b.dataset.speed
        );


      if (
        Number.isFinite(rate)
      ) {

        S.podRate = rate;

      }

    };

  });


  /* Exam */
  $('gen-exam-btn').onclick =
    genExam;


  $('ex-minus').onclick = () => {

    S.examCount =
      Math.max(
        3,
        S.examCount - 1
      );

    $('ex-count').textContent =
      S.examCount;
  };


  $('ex-plus').onclick = () => {

    S.examCount =
      Math.min(
        10,
        S.examCount + 1
      );

    $('ex-count').textContent =
      S.examCount;
  };


  /* Clear and download */
  $('clear-btn').onclick =
    clearHistory;


  $('dl-btn').onclick =
    dlCurrent;


  /* Multi-document */
  $('multi-btn').onclick =
    startMulti;


  $('compare-btn').onclick =
    () => {

      switchTab('summary');

      compareDoc();

    };
    initMobileNavigation();

}


/* ══════════════════════════════════════════════════
   DOCUMENTS
   ══════════════════════════════════════════════════ */

async function loadDocs() {

  try {

    const d =
      await GET('/documents');

    S.docs =
      d.documents || [];

    renderDocs();

  } catch { }

}


function renderDocs() {

  $('doc-count').textContent =
    S.docs.length;


  const list =
    $('doc-list');


  list.innerHTML = '';


  if (!S.docs.length) {

    list.innerHTML =
      '<div class="doc-empty" id="doc-empty">' +
      '<div style="font-size:32px;margin-bottom:8px">📂</div>' +
      '<p>No documents yet</p>' +
      '<p style="font-size:11px;margin-top:4px;color:var(--text-muted)">' +
      'Upload files to get started' +
      '</p>' +
      '</div>';

    return;
  }


  S.docs.forEach(doc => {

    const el =
      document.createElement('div');


    el.className =
      'doc-item' +
      (
        doc.id === S.activeDocId
          ? ' active'
          : ''
      ) +
      (
        S.selectedIds.has(doc.id)
          ? ' checked'
          : ''
      );


    el.dataset.id =
      doc.id;


    const ext =
      (doc.originalName || '')
        .split('.')
        .pop()
        .toUpperCase();


    const icon =
      ext === 'PDF'
        ? '📕'
        : '📄';


    el.innerHTML = `
      <div class="doc-check"></div>
      <span class="doc-icon">${icon}</span>

      <div class="doc-info">
        <div
          class="doc-name"
          title="${esc(doc.originalName)}"
        >
          ${esc(doc.originalName)}
        </div>

        <div class="doc-meta">
          ${doc.pageCount || '?'}p ·
          ${doc.chunkCount || '?'} chunks ·
          ${fmtBytes(doc.size)}
        </div>
      </div>

      <span class="doc-status ${doc.status || 'ready'}">
        ${doc.status || 'ready'}
      </span>

      <button
        class="doc-del"
        title="Delete"
      >
        ×
      </button>
    `;


    el.addEventListener(
      'click',
      e => {

        if (
          e.target.closest(
            '.doc-del'
          )
        ) {

          delDoc(
            doc.id,
            doc.originalName
          );

          return;
        }


        if (
          e.target.closest(
            '.doc-check'
          ) ||
          e.ctrlKey ||
          e.metaKey ||
          e.shiftKey
        ) {

          toggleSel(
            doc.id,
            el
          );

          return;
        }


        openDoc(doc.id);

      }
    );


    list.appendChild(el);

  });


  updateMultiUI();
}


function toggleSel(id, el) {

  if (
    S.selectedIds.has(id)
  ) {

    S.selectedIds.delete(id);

    el.classList.remove(
      'checked'
    );

  } else {

    S.selectedIds.add(id);

    el.classList.add(
      'checked'
    );

  }


  updateMultiUI();
}


function updateMultiUI() {

  const n =
    S.selectedIds.size;


  $('multi-bar').style.display =
    n > 0
      ? 'flex'
      : 'none';


  $('compare-btn').style.display =
    n >= 2
      ? 'block'
      : 'none';


  $('sel-count').textContent =
    `${n} selected`;


  const cmp =
    $('compare-section');


  if (cmp) {

    cmp.style.display =
      n >= 2
        ? 'block'
        : 'none';

  }

}


function openDoc(id) {

  S.activeDocId = id;

  S.multiMode = false;


  $$('.doc-item').forEach(
    el =>
      el.classList.toggle(
        'active',
        el.dataset.id === id
      )
  );


  const doc =
    S.docs.find(
      d => d.id === id
    );


  $('ws-name').textContent =
    doc?.originalName ||
    'Document';


  $('ws-meta').textContent =
    `${doc?.pageCount || '?'} pages · ` +
    `${doc?.chunkCount || '?'} chunks`;


  $('active-indicator').textContent =
    `📄 ${doc?.originalName || ''}`;


  const cw =
    $('cw-text');


  if (cw) {

    cw.textContent =
      `Ask me anything about "${doc?.originalName || 'your document'}"`;

  }


  showWorkspace();

  resetPanels();

  loadHistory(id);

  switchTab('chat');
}


function startMulti() {

  if (
    S.selectedIds.size < 2
  ) {
    return;
  }


  S.multiMode = true;


  const ids =
    [...S.selectedIds];


  S.activeDocId =
    ids[0];


  const names =
    ids.map(
      id =>
        S.docs.find(
          d => d.id === id
        )?.originalName || id
    );


  $('ws-name').textContent =
    `${ids.length} Documents`;


  $('ws-meta').textContent =
    names
      .join(', ')
      .slice(0, 60) +
    '...';


  $('active-indicator').textContent =
    `⚡ ${ids.length} docs`;


  showWorkspace();

  resetPanels();

  clearChatUI();


  const cw =
    $('chat-welcome');


  if (cw) {

    cw.innerHTML =
      `<div class="cw-icon">⚡</div>
       <p>
         Multi-doc chat active —
         <strong>${ids.length} documents</strong>
         selected
       </p>`;

  }


  switchTab('chat');
}


async function delDoc(id, name) {

  if (
    !confirm(
      `Delete "${name}"?`
    )
  ) {
    return;
  }


  try {

    await DEL(
      `/documents/${id}`
    );


    S.docs =
      S.docs.filter(
        d => d.id !== id
      );


    S.selectedIds.delete(id);


    if (
      S.activeDocId === id
    ) {

      S.activeDocId = null;

      showWelcome();

    }


    renderDocs();


    toast(
      `🗑️ Deleted "${name}"`,
      'info'
    );

  } catch (e) {

    toast(
      'Delete failed: ' +
      e.message,
      'error'
    );

  }

}


/* ══════════════════════════════════════════════════
   UPLOAD
   ══════════════════════════════════════════════════ */

async function handleUpload(files) {

  if (!files?.length) {
    return;
  }


  const token =
    getToken();


  if (!token) {

    toast(
      'Please sign in first',
      'error'
    );

    return;
  }


  const fd =
    new FormData();


  Array.from(files).forEach(
    f =>
      fd.append(
        'files',
        f
      )
  );


  showOverlay(
    files.length
  );


  try {

    const r =
      await fetch(
        `${API}/upload`,
        {
          method: 'POST',
          headers: {
            'Authorization':
              'Bearer ' + token
          },
          body: fd
        }
      );


    if (r.status === 401) {

      signOut();

      return;
    }


    if (!r.ok) {

      const e =
        await r.json()
          .catch(() => ({}));


      toast(
        'Upload failed: ' +
        (
          e.error ||
          r.statusText
        ),
        'error'
      );


      hideOverlay();

      return;
    }


    const d =
      await r.json();


    hideOverlay();


    $('file-input').value =
      '';


    if (d.errors?.length) {

      d.errors.forEach(
        e =>
          toast(
            `❌ ${e.file}: ${e.error}`,
            'error'
          )
      );

    }


    if (d.uploaded?.length) {

      toast(
        `✅ ${d.uploaded.length} file(s) ready!`,
        'success'
      );


      await loadDocs();


      if (d.uploaded[0]) {

        openDoc(
          d.uploaded[0].id
        );

      }

    }

  } catch (e) {

    hideOverlay();

    toast(
      'Cannot reach server — is backend running?',
      'error'
    );

  }

}


/* ══════════════════════════════════════════════════
   CHAT
   ══════════════════════════════════════════════════ */

async function sendMsg() {

  const q =
    $('chat-input')
      .value
      .trim();


  if (!q) {
    return;
  }


  const ids =
    S.multiMode
      ? [...S.selectedIds]
      : S.activeDocId
        ? [S.activeDocId]
        : [];


  if (!ids.length) {

    toast(
      'Select a document first',
      'warning'
    );

    return;
  }


  $('chat-input').value =
    '';


  autoResize(
    $('chat-input')
  );


  $('send-btn').disabled =
    true;


  const cw =
    $('chat-welcome');


  if (cw) {
    cw.remove();
  }


  appendUserMsg(q);


  const tid =
    showTyping();


  try {

    const d =
      await POST(
        '/chat',
        {
          query: q,
          docIds: ids
        }
      );


    removeTyping(tid);


    appendAIMsg(
      d.answer || d.raw,
      d.sources || []
    );

  } catch (e) {

    removeTyping(tid);


    appendAIMsg(
      '❌ ' + e.message,
      []
    );

  } finally {

    $('send-btn').disabled =
      false;


    $('chat-input').focus();

  }

}


function appendUserMsg(text) {

  const d =
    document.createElement(
      'div'
    );


  d.className =
    'msg user';


  d.innerHTML =
    `<div class="msg-avatar">U</div>
     <div class="msg-body">
       <div class="msg-bubble">
         ${esc(text)}
       </div>
       <div class="msg-time">
         ${fmtTime()}
       </div>
     </div>`;


  $('chat-msgs')
    .appendChild(d);


  scrollBottom();
}


function appendAIMsg(
  text,
  sources = []
) {

  const d =
    document.createElement(
      'div'
    );


  d.className =
    'msg assistant';


  const srcHtml =
    sources.length
      ? buildSources(sources)
      : '';


  d.innerHTML =
    `<div class="msg-avatar">🤖</div>
     <div class="msg-body">

       <div class="msg-bubble fmt">
         ${renderMd(text)}
       </div>

       ${srcHtml}

       <div class="msg-time">
         ${fmtTime()}
       </div>

     </div>`;


  const hdr =
    d.querySelector(
      '.sources-hdr'
    );


  if (hdr) {

    hdr.onclick = () => {

      const list =
        d.querySelector(
          '.sources-list'
        );


      const tog =
        d.querySelector(
          '.src-toggle'
        );


      if (list) {

        list.style.display =
          list.style.display === 'none'
            ? ''
            : 'none';


        if (tog) {

          tog.textContent =
            list.style.display === 'none'
              ? '▼'
              : '▲';

        }

      }

    };

  }


  $('chat-msgs')
    .appendChild(d);


  scrollBottom();
}


function buildSources(srcs) {

  const items =
    srcs
      .map(
        s =>
          `<div class="source-item">
             ${s.page
            ? `<span class="src-page">
                      Page ${s.page}
                    </span>`
            : ''
          }

             <div class="src-quote">
               "${esc(
            (s.quote || '')
              .slice(0, 200)
          )}"
             </div>
           </div>`
      )
      .join('');


  return `
    <div class="sources">

      <div class="sources-hdr">
        <span>
          📎 Sources (${srcs.length})
        </span>

        <span class="src-toggle">
          ▲
        </span>
      </div>

      <div class="sources-list">
        ${items}
      </div>

    </div>
  `;
}


function showTyping() {

  const id =
    'typing-' +
    Date.now();


  const d =
    document.createElement(
      'div'
    );


  d.id = id;

  d.className =
    'typing';


  d.innerHTML =
    `<div
       class="msg-avatar"
       style="
         background:var(--bg-elevated);
         border:1px solid var(--border)
       "
     >
       🤖
     </div>

     <div class="typing-dots">
       <span></span>
       <span></span>
       <span></span>
     </div>`;


  $('chat-msgs')
    .appendChild(d);


  scrollBottom();


  return id;
}


function removeTyping(id) {

  const e =
    $(id);


  if (e) {
    e.remove();
  }
}


function scrollBottom() {

  const m =
    $('chat-msgs');


  if (m) {
    m.scrollTop =
      m.scrollHeight;
  }

}


async function loadHistory(docId) {

  clearChatUI();


  try {

    const d =
      await GET(
        `/documents/${docId}/history`
      );


    const h =
      d.history || [];


    if (!h.length) {

      renderChatWelcome();

      return;
    }


    h.forEach(m => {

      if (m.role === 'user') {

        appendUserMsg(
          m.content
        );

      } else {

        appendAIMsg(
          m.content,
          m.sources || []
        );

      }

    });


    scrollBottom();

  } catch {

    renderChatWelcome();

  }

}


function clearChatUI() {

  $('chat-msgs').innerHTML =
    '';

}


function renderChatWelcome() {

  const doc =
    S.docs.find(
      d => d.id === S.activeDocId
    );


  const nm =
    doc?.originalName ||
    'your document';


  $('chat-msgs').innerHTML =
    `<div
       class="chat-welcome"
       id="chat-welcome"
     >

       <div class="cw-icon">
         🤖
       </div>

       <p id="cw-text">
         Ask me anything about
         <strong>
           ${esc(nm)}
         </strong>
       </p>

       <div
         class="suggestions"
         id="suggestions"
       >

         <button class="chip">
           📋 What is this document about?
         </button>

         <button class="chip">
           🔑 List the key points
         </button>

         <button class="chip">
           💡 What are the main conclusions?
         </button>

         <button class="chip">
           ❓ Explain the most important concept
         </button>

       </div>

     </div>`;


  $('suggestions')
    ?.addEventListener(
      'click',
      e => {

        const c =
          e.target.closest(
            '.chip'
          );


        if (c) {

          $('chat-input').value =
            c.textContent.replace(
              /^[^\s]+\s/,
              ''
            );


          sendMsg();

        }

      }
    );

}


async function clearHistory() {

  if (!S.activeDocId) {
    return;
  }


  try {

    await DEL(
      `/documents/${S.activeDocId}/history`
    );


    clearChatUI();

    renderChatWelcome();


    toast(
      '🗑️ Chat cleared',
      'info'
    );

  } catch (e) {

    toast(
      e.message,
      'error'
    );

  }

}


/* ══════════════════════════════════════════════════
   SUMMARY
   ══════════════════════════════════════════════════ */

async function genSummary() {

  const id =
    S.activeDocId;


  if (!id) {

    return toast(
      'Open a document first',
      'warning'
    );

  }


  const btn =
    $('gen-summary-btn');


  btn.disabled = true;

  btn.textContent =
    'Generating...';


  $('summary-out').innerHTML =
    `<div class="loading-row">
       <div class="mini-spin"></div>
       Generating summary...
     </div>`;


  try {

    const d =
      await POST(
        '/summary',
        {
          docId: id,
          type: S.summaryType
        }
      );


    $('summary-out').innerHTML =
      `<div class="fmt">
         ${renderMd(d.summary)}
       </div>`;


    toast(
      '✅ Summary ready!',
      'success'
    );

  } catch (e) {

    $('summary-out').innerHTML =
      `<div class="placeholder">
         ❌<br/>
         ${esc(e.message)}
       </div>`;


    toast(
      e.message,
      'error'
    );

  } finally {

    btn.disabled = false;

    btn.textContent =
      '✨ Generate Summary';

  }

}


async function compareDoc() {

  const ids =
    [...S.selectedIds];


  if (ids.length < 2) {

    return toast(
      'Select 2+ documents',
      'warning'
    );

  }


  const btn =
    $('compare-btn2');


  btn.disabled = true;

  btn.textContent =
    'Comparing...';


  $('compare-out').innerHTML =
    `<div class="loading-row">
       <div class="mini-spin"></div>
       Comparing documents...
     </div>`;


  try {

    const d =
      await POST(
        '/summary/compare',
        {
          docIds: ids
        }
      );


    $('compare-out').innerHTML =
      `<div class="fmt">
         ${renderMd(d.comparison)}
       </div>`;


    toast(
      '📊 Comparison ready!',
      'success'
    );

  } catch (e) {

    $('compare-out').innerHTML =
      `<p style="color:var(--danger)">
         ${esc(e.message)}
       </p>`;

  } finally {

    btn.disabled = false;

    btn.textContent =
      '📊 Compare Selected Documents';

  }

}


/* ══════════════════════════════════════════════════
   FLASHCARDS
   ══════════════════════════════════════════════════ */

async function genFlashcards() {

  const id =
    S.activeDocId;


  if (!id) {

    return toast(
      'Open a document first',
      'warning'
    );

  }


  const btn =
    $('gen-fc-btn');


  btn.disabled = true;

  btn.textContent =
    'Generating...';


  $('fc-area').innerHTML =
    `<div class="loading-row">
       <div class="mini-spin"></div>
       Generating flashcards...
     </div>`;


  try {

    const d =
      await POST(
        '/flashcards',
        {
          docId: id,
          count: S.fcCount
        }
      );


    S.flashcards =
      d.flashcards || [];


    renderFC(
      S.flashcards
    );


    toast(
      `🃏 ${S.flashcards.length} flashcards ready!`,
      'success'
    );

  } catch (e) {

    $('fc-area').innerHTML =
      `<div class="placeholder">
         ❌<br/>
         ${esc(e.message)}
       </div>`;


    toast(
      e.message,
      'error'
    );

  } finally {

    btn.disabled = false;

    btn.textContent =
      '🃏 Generate Flashcards';

  }

}


function renderFC(cards) {

  if (!cards.length) {

    $('fc-area').innerHTML =
      `<div class="placeholder">
         No cards generated
       </div>`;

    return;
  }


  $('fc-stats').style.display =
    'flex';


  $('diff-filter').style.display =
    'flex';


  $('fc-total').textContent =
    `${cards.length} cards`;


  S.fcDone = 0;


  $('fc-done').textContent =
    '0 reviewed';


  $('fc-area').innerHTML =
    '';


  cards.forEach(
    (c, i) => {

      const el =
        document.createElement(
          'div'
        );


      const dCls =
        c.difficulty ||
        'medium';


      el.className =
        'flashcard';


      el.dataset.diff =
        dCls;


      el.dataset.i =
        i;


      const dIcon =
        {
          easy: '🟢',
          medium: '🟡',
          hard: '🔴'
        }[dCls] || '🟡';


      const dLabel =
        {
          easy: 'Easy',
          medium: 'Medium',
          hard: 'Hard'
        }[dCls] || 'Medium';


      const topicLabel =
        c.topic ||
        'General';


      el.innerHTML =
        `<div class="fc-front">

          <div class="fc-top-row">

            <span class="fc-num">
              ${String(i + 1).padStart(2, '0')}
            </span>

            <span class="fc-diff ${dCls}">
              ${dIcon} ${dLabel}
            </span>

          </div>

          <div class="fc-q">
            ${esc(c.q)}
          </div>

          <div class="fc-hint">
            <span class="fc-hint-icon">
              👆
            </span>

            <span>
              Click to reveal answer
            </span>
          </div>

        </div>

        <div class="fc-back">

          <div class="fc-back-label">
            ✅ Answer
          </div>

          <div class="fc-topic">
            ${esc(topicLabel)}
          </div>

          <div>
            ${esc(c.a)}
          </div>

        </div>`;


      el.onclick = () => {

        const wasOpen =
          el.classList.contains(
            'open'
          );


        el.classList.toggle(
          'open'
        );


        const hint =
          el.querySelector(
            '.fc-hint span:last-child'
          );


        if (hint) {

          hint.textContent =
            el.classList.contains(
              'open'
            )
              ? 'Click to hide answer'
              : 'Click to reveal answer';

        }


        if (!wasOpen) {

          S.fcDone++;


          $('fc-done').textContent =
            `${S.fcDone} reviewed`;

        }

      };


      $('fc-area')
        .appendChild(el);

    }
  );

}


function shuffleFC() {

  S.flashcards =
    [...S.flashcards]
      .sort(
        () => Math.random() - 0.5
      );


  renderFC(
    S.flashcards
  );

}


function filterFC(diff) {

  $$('#fc-area .flashcard')
    .forEach(el => {

      el.style.display =
        (
          diff === 'all' ||
          el.dataset.diff === diff
        )
          ? ''
          : 'none';

    });

}


function dlFlashcards() {

  if (!S.flashcards.length) {
    return;
  }


  const txt =
    S.flashcards
      .map(
        (c, i) =>
          `Q${i + 1} [${c.difficulty}]: ${c.q}\n` +
          `A: ${c.a}\n`
      )
      .join('\n');


  dlText(
    txt,
    'saathi-flashcards.txt'
  );

}


/* ══════════════════════════════════════════════════
   PODCAST
   ══════════════════════════════════════════════════ */

async function genPodcast() {

  const id =
    S.activeDocId;


  if (!id) {

    return toast(
      'Open a document first',
      'warning'
    );

  }


  /*
   * Stop any existing podcast.
   */
  stopPod();


  const btn =
    $('gen-pod-btn');


  btn.disabled = true;

  btn.textContent =
    'Generating script...';


  try {

    const d =
      await POST(
        '/podcast',
        {
          docId: id
        }
      );


    S.podSegs =
      Array.isArray(d.segments)
        ? d.segments
        : [];


    S.podScript =
      d.script || '';


    S.podIdx = 0;

    S.podPlaying = false;

    S.podPaused = false;


    if (!S.podSegs.length) {

      throw new Error(
        'No valid Alex/Maya dialogue was generated.'
      );

    }


    const doc =
      S.docs.find(
        x => x.id === id
      );


    $('player-title').textContent =
      doc?.originalName ||
      'Podcast';


    $('player-dur').textContent =
      `~${d.estimatedDuration || 5} min`;


    const totalWords =
      S.podSegs.reduce(
        (total, segment) => {

          return total +
            String(
              segment.text || ''
            )
              .split(/\s+/)
              .filter(Boolean)
              .length;

        },
        0
      );


    const estimatedSeconds =
      Math.ceil(
        totalWords / 2.3
      );


    $('t-tot').textContent =
      fmtDur(
        estimatedSeconds
      );


    $('t-cur').textContent =
      '0:00';


    $('prog-fill').style.width =
      '0%';


    $('sp-line').textContent =
      '';


    $('player').style.display =
      'flex';


    renderTranscript(
      S.podSegs
    );


    $('transcript').style.display =
      'block';


    toast(
      '🎙️ Script ready — hit play!',
      'success'
    );


  } catch (e) {

    toast(
      e.message,
      'error'
    );

  } finally {

    btn.disabled = false;

    btn.textContent =
      '🎙️ Generate Podcast Script';

  }

}


/*
 * Render the transcript from the parsed segments.
 *
 * We use the actual S.podSegs rather than reparsing
 * the raw script, which means the transcript and
 * playback always use the same segment indexes.
 */
function renderTranscript(segments) {

  const body =
    $('transcript-body');


  if (!body) {
    return;
  }


  body.innerHTML =
    '';


  segments.forEach(
    (segment, index) => {

      const el =
        document.createElement(
          'div'
        );


      el.className =
        'tr-line pod-segment';


      el.dataset.index =
        index;


      const speaker =
        String(
          segment.speaker || ''
        ).toLowerCase();


      const displayName =
        speaker === 'maya'
          ? 'Maya'
          : 'Alex';


      const speakerClass =
        speaker === 'maya'
          ? 'maya'
          : 'alex';


      el.innerHTML =
        `<span class="tr-spk ${speakerClass}">
           ${esc(displayName)}:
         </span>

         <span>
           ${esc(segment.text || '')}
         </span>`;


      body.appendChild(el);

    }
  );

}


/*
 * Highlight the current transcript segment.
 */
function highlightTranscript(index) {

  const lines =
    $$('.pod-segment');


  lines.forEach(
    (el, i) => {

      el.classList.toggle(
        'active',
        i === index
      );

    }
  );

}


/*
 * Update the currently displayed speaker
 * in the podcast player.
 */
function updatePodcastSpeaker(segment) {

  if (!segment) {
    return;
  }


  const speaker =
    String(
      segment.speaker || 'Alex'
    ).toLowerCase();


  const isMaya =
    speaker === 'maya';


  const displayName =
    isMaya
      ? 'Maya'
      : 'Alex';


  const avatar =
    $('sp-avatar');


  if (avatar) {

    avatar.textContent =
      isMaya
        ? 'M'
        : 'A';


    avatar.className =
      'sp-avatar' +
      (
        isMaya
          ? ' sam'
          : ''
      );

  }


  const name =
    $('sp-name');


  if (name) {

    name.textContent =
      displayName;

  }


  const line =
    $('sp-line');


  if (line) {

    line.textContent =
      String(
        segment.text || ''
      ).slice(0, 120) +
      (
        String(
          segment.text || ''
        ).length > 120
          ? '...'
          : ''
      );

  }

}


/*
 * Update podcast progress.
 */
function updatePodcastProgress(index) {

  if (!S.podSegs.length) {
    return;
  }


  const percent =
    (
      index /
      S.podSegs.length
    ) * 100;


  const fill =
    $('prog-fill');


  if (fill) {

    fill.style.width =
      `${percent}%`;

  }


  const elapsed =
    S.podSegs
      .slice(0, index)
      .reduce(
        (total, segment) => {

          const words =
            String(
              segment.text || ''
            )
              .split(/\s+/)
              .filter(Boolean)
              .length;


          return total +
            Math.ceil(
              words / 2.3
            );

        },
        0
      );


  const current =
    $('t-cur');


  if (current) {

    current.textContent =
      fmtDur(elapsed);

  }

}


/*
 * Avatar state.
 *
 * We use both "active" and "speaking"
 * so this remains compatible with the
 * existing avatar CSS.
 */
function updateAvatar(speaker) {

  const maya =
    $('maya-avatar');


  const alex =
    $('alex-avatar');


  if (!maya || !alex) {
    return;
  }


  maya.classList.remove(
    'active',
    'speaking'
  );


  alex.classList.remove(
    'active',
    'speaking'
  );


  if (
    String(speaker)
      .toLowerCase() === 'maya'
  ) {

    maya.classList.add(
      'active',
      'speaking'
    );

  } else {

    alex.classList.add(
      'active',
      'speaking'
    );

  }

}


/*
 * Split a dialogue segment into sentences.
 *
 * This is one of the main improvements over
 * speaking the entire paragraph as one utterance.
 */
function splitIntoSentences(text) {

  if (!text) {
    return [];
  }


  const sentences =
    String(text)
      .match(
        /[^.!?]+[.!?]+|[^.!?]+$/g
      );


  return (
    sentences || []
  )
    .map(
      sentence =>
        sentence.trim()
    )
    .filter(Boolean);

}


/*
 * Promise-based pause.
 */
function pause(ms) {

  return new Promise(
    resolve =>
      setTimeout(
        resolve,
        ms
      )
  );

}


/*
 * Speak one sentence using the browser voice.
 *
 * speechText is supported if the backend eventually
 * supplies a speech-friendly version.
 *
 * Otherwise the normal displayed text is spoken.
 */
function speakSentence(
  text,
  speaker
) {

  return new Promise(
    resolve => {

      if (
        !('speechSynthesis' in window)
      ) {

        resolve();

        return;
      }


      const cleanText =
        String(text || '')
          .trim();


      if (!cleanText) {

        resolve();

        return;
      }


      const utterance =
        new SpeechSynthesisUtterance(
          cleanText
        );


      const voice =
        getVoiceForSpeaker(
          speaker
        );


      if (voice) {

        utterance.voice =
          voice;


        utterance.lang =
          voice.lang;

      } else {

        utterance.lang =
          'en-US';

      }


      /*
       * Maya is slightly slower because
       * she is the teacher.
       *
       * Alex is slightly faster and more
       * conversational.
       */
      if (String(speaker).toLowerCase() === 'maya') {

        utterance.rate = 0.91 * S.podRate;
        utterance.pitch = 1.02;

      } else {

        utterance.rate = 0.96 * S.podRate;
        utterance.pitch = 1.03;

      }

      utterance.volume = 1;


      let finished =
        false;


      const finish =
        () => {

          if (finished) {
            return;
          }


          finished = true;

          resolve();

        };


      utterance.onend =
        finish;


      utterance.onerror =
        event => {

          console.warn(
            'Speech synthesis error:',
            event
          );


          finish();

        };


      speechSynthesis.speak(
        utterance
      );

    }
  );

}

function sync3DWithSpeaker(segment) {

  if (!window.saathi3D || !segment) {
    return;
  }

  const speaker =
    String(segment.speaker || '')
      .toLowerCase();

  const text =
    String(segment.text || '')
      .toLowerCase();


  // ==========================================
  // MAYA
  // ==========================================

  if (speaker === 'maya') {

    /*
     * Start automatic body-language changes
     * for the whole Maya answer.
     */
    startMayaGestureCycle();

    /*
     * Use the actual content to choose the
     * first gesture.
     */

    if (
      text.includes('important') ||
      text.includes('remember') ||
      text.includes('key point') ||
      text.includes('main idea')
    ) {

      window.saathi3D.mayaGesture(
        'pointing'
      );

      return;
    }


    if (
      text.includes('think about') ||
      text.includes('consider') ||
      text.includes('imagine') ||
      text.includes('why')
    ) {

      window.saathi3D.mayaGesture(
        'thinking'
      );

      return;
    }


    /*
     * Otherwise begin naturally with talking.
     */
    window.saathi3D.mayaGesture(
      'talking'
    );

    return;
  }


  // ==========================================
  // ALEX
  // ==========================================

  if (speaker === 'alex') {

    /*
     * Maya has finished her answer.
     */
    stopMayaGestureCycle();

    window.saathi3D.alexTalking();

    return;
  }


  // ==========================================
  // NO SPEAKER
  // ==========================================

  stopMayaGestureCycle();

  window.saathi3D.setSpeaker('');
}
function startMayaGestureCycle() {
  if (!window.saathi3D) return;

  // Stop any previous cycle
  if (S.mayaGestureTimer) {
    clearInterval(S.mayaGestureTimer);
    S.mayaGestureTimer = null;
  }

  const gestures = [
    'talking',
    'talking2',
    'pointing',
    'talking2',
    'thinking',
    'talking',
    'pointing',
    'talking2'
  ];

  S.mayaGestureStep = 0;

  // Start immediately
  window.saathi3D.mayaGesture(
    gestures[S.mayaGestureStep]
  );

  /*
   * Change Maya's body language every few seconds.
   *
   * This makes a single long answer feel
   * like a real teaching conversation.
   */
  const gestureDelays = [
    7000,
    8500,
    6500,
    9000,
    7500,
    8500
  ];

  let delayIndex = 0;

  function scheduleNextMayaGesture() {

    if (!S.podPlaying) {
      return;
    }

    const delay =
      gestureDelays[
      delayIndex % gestureDelays.length
      ];

    delayIndex++;

    S.mayaGestureTimer = setTimeout(() => {

      if (
        !S.podPlaying ||
        S.podPaused
      ) {
        scheduleNextMayaGesture();
        return;
      }

      S.mayaGestureStep =
        (S.mayaGestureStep + 1) %
        gestures.length;

      window.saathi3D.mayaGesture(
        gestures[S.mayaGestureStep]
      );

      scheduleNextMayaGesture();

    }, delay);
  }

  scheduleNextMayaGesture();
}


function stopMayaGestureCycle() {

  if (S.mayaGestureTimer) {
    clearTimeout(S.mayaGestureTimer);
    S.mayaGestureTimer = null;
  }

  S.mayaGestureStep = 0;
}
/*
 * Play one complete dialogue segment.
 *
 * Each segment is divided into sentences.
 */
async function playSegment(
  index
) {

  if (!S.podPlaying) {
    return;
  }


  if (
    index >= S.podSegs.length
  ) {

    finishPodcast();

    return;
  }


  S.podIdx =
    index;


  const segment =
    S.podSegs[index];


  if (!segment) {

    await playSegment(
      index + 1
    );

    return;
  }


  updatePodcastSpeaker(
    segment
  );


  updateAvatar(
    segment.speaker
  );

  sync3DWithSpeaker(segment);

  updatePodcastProgress(
    index
  );


  highlightTranscript(
    index
  );


  /*
   * Support speechText if you later add
   * dynamic speech preparation.
   *
   * For now the backend returns text,
   * so this falls back automatically.
   */
  const speechText =
    segment.speechText ||
    segment.text ||
    '';


  const sentences =
    splitIntoSentences(
      speechText
    );


  for (
    let sentenceIndex = 0;
    sentenceIndex < sentences.length;
    sentenceIndex++
  ) {

    if (!S.podPlaying) {
      return;
    }


    /*
     * If the user pressed pause while we were
     * between sentences, wait until resumed.
     */
    while (
      S.podPaused &&
      S.podPlaying
    ) {

      await pause(100);

    }


    if (!S.podPlaying) {
      return;
    }


    await speakSentence(
      sentences[sentenceIndex],
      segment.speaker
    );


    if (!S.podPlaying) {
      return;
    }


    /*
     * Small pause between sentences.
     */
    await pause(180);

  }


  if (!S.podPlaying) {
    return;
  }


  /*
   * Slightly longer pause between speakers.
   */
  await pause(550);


  if (S.podPlaying) {

    await playSegment(
      index + 1
    );

  }

}


/*
 * Start or resume the podcast.
 */
function startPlay() {

  if (!S.podSegs.length) {

    toast(
      'Generate a podcast first',
      'warning'
    );

    return;
  }


  if (
    !('speechSynthesis' in window)
  ) {

    toast(
      'Browser TTS is not supported',
      'warning'
    );

    return;
  }


  /*
   * If speech is currently paused by the browser,
   * resume it instead of starting another utterance.
   */
  if (
    S.podPlaying &&
    S.podPaused &&
    speechSynthesis.paused
  ) {

    S.podPaused = false;

    speechSynthesis.resume();

    updatePlayUI();

    return;
  }


  /*
   * Already playing.
   */
  if (
    S.podPlaying &&
    !S.podPaused
  ) {

    return;
  }


  S.podPlaying = true;
  S.podPaused = false;


  updatePlayUI();


  playSegment(
    S.podIdx
  );

}


/*
 * Pause/resume podcast.
 */
function togglePlay() {

  if (!S.podSegs.length) {

    toast(
      'Generate a podcast first',
      'warning'
    );

    return;
  }


  if (!S.podPlaying) {

    startPlay();

    return;
  }


  /*
   * Currently playing -> pause.
   */
  if (!S.podPaused) {

    S.podPaused = true;

    speechSynthesis.pause();

    updatePlayUI();

    return;
  }


  /*
   * Currently paused -> resume.
   */
  S.podPaused = false;

  speechSynthesis.resume();

  updatePlayUI();

}


/*
 * Update play button, spinning disc,
 * and sound waves.
 */
function updatePlayUI() {

  const playBtn =
    $('play-btn');


  if (playBtn) {

    playBtn.textContent =
      (
        S.podPlaying &&
        !S.podPaused
      )
        ? '⏸️'
        : '▶️';

  }


  const disc =
    $('disc');


  if (disc) {

    disc.classList.toggle(
      'spin',
      S.podPlaying &&
      !S.podPaused
    );

  }


  const waves =
    $('waves');


  if (waves) {

    waves.classList.toggle(
      'active',
      S.podPlaying &&
      !S.podPaused
    );

  }

}


/*
 * Completely stop the podcast.
 *
 * Unlike pause, this resets playback.
 */
function stopPod() {

  S.podPlaying =
    false;


  S.podPaused =
    false;


  speechSynthesis.cancel();


  S.podIdx =
    0;


  updatePlayUI();


  const fill =
    $('prog-fill');


  if (fill) {

    fill.style.width =
      '0%';

  }


  const current =
    $('t-cur');


  if (current) {

    current.textContent =
      '0:00';

  }


  const line =
    $('sp-line');


  if (line) {

    line.textContent =
      '';

  }


  const speaker =
    $('sp-name');


  if (speaker) {

    speaker.textContent =
      '';

  }


  const maya =
    $('maya-avatar');

  const alex =
    $('alex-avatar');

  if (maya) {

    maya.classList.remove(
      'active',
      'speaking'
    );

  }


  if (alex) {

    alex.classList.remove(
      'active',
      'speaking'
    );

  }


  $$('.pod-segment')
    .forEach(
      el =>
        el.classList.remove(
          'active'
        )
    );

  // Reset 3D characters
  if (window.saathi3D) {
    window.saathi3D.setSpeaker('');
  }
  stopMayaGestureCycle();
}

/*
 * Restart podcast from the beginning.
 */
function restartPodcast() {

  stopPod();


  S.podIdx =
    0;


  setTimeout(
    () => {

      startPlay();

    },
    150
  );

}


/*
 * Called when the podcast reaches the end.
 */
function finishPodcast() {

  S.podPlaying =
    false;


  S.podPaused =
    false;


  speechSynthesis.cancel();


  /*
   * Show 100% completion.
   */
  const fill =
    $('prog-fill');


  if (fill) {

    fill.style.width =
      '100%';

  }


  const total =
    $('t-tot');


  if (total) {

    const current =
      $('t-cur');

    if (current) {
      current.textContent =
        total.textContent;
    }

  }


  updatePlayUI();


  const maya =
    $('maya-avatar');


  const alex =
    $('alex-avatar');


  if (maya) {

    maya.classList.remove(
      'speaking'
    );

  }


  if (alex) {

    alex.classList.remove(
      'speaking'
    );

  }

}


/* ══════════════════════════════════════════════════
   PODCAST SPEED BUTTONS
   ══════════════════════════════════════════════════ */

$$('.sp-btn').forEach(
  b => {

    b.onclick = () => {

      $$('.sp-btn').forEach(
        x =>
          x.classList.remove(
            'active'
          )
      );


      b.classList.add(
        'active'
      );


      const rate =
        parseFloat(
          b.dataset.speed
        );


      if (
        Number.isFinite(rate)
      ) {

        S.podRate =
          rate;

      }

    };

  }
);


/* ══════════════════════════════════════════════════
   EXAM
   ══════════════════════════════════════════════════ */

async function genExam() {

  const id =
    S.activeDocId;


  if (!id) {

    return toast(
      'Open a document first',
      'warning'
    );

  }


  const btn =
    $('gen-exam-btn');


  btn.disabled = true;

  btn.textContent =
    'Generating...';


  $('exam-area').innerHTML =
    `<div class="loading-row">
       <div class="mini-spin"></div>
       Generating exam...
     </div>`;


  S.examCorrect = 0;

  S.examAnswered = 0;

  updateScore();


  try {

    const d =
      await POST(
        '/flashcards/exam',
        {
          docId: id,
          count: S.examCount
        }
      );


    S.examQs =
      d.questions || [];


    renderExam(
      S.examQs
    );


    $('score-bar').style.display =
      'flex';


    toast(
      `🎓 ${S.examQs.length} questions ready!`,
      'success'
    );

  } catch (e) {

    $('exam-area').innerHTML =
      `<div class="placeholder">
         ❌<br/>
         ${esc(e.message)}
       </div>`;


    toast(
      e.message,
      'error'
    );

  } finally {

    btn.disabled = false;

    btn.textContent =
      '🎓 Start Exam';

  }

}


function renderExam(qs) {

  $('exam-area').innerHTML =
    '';


  qs.forEach(
    (q, i) => {

      const el =
        document.createElement(
          'div'
        );


      el.className =
        'exam-q';


      el.dataset.answered =
        'false';


      const typeLabel =
        q.type === 'mcq'
          ? 'Multiple Choice'
          : 'Short Answer';


      const typeCls =
        q.type === 'mcq'
          ? 'mcq'
          : 'short';


      let inputHtml =
        '';


      if (
        q.type === 'mcq' &&
        q.options
      ) {

        inputHtml =
          `<div class="eq-opts">
             ${(q.options || [])
            .map(
              o =>
                `<div
                      class="eq-opt"
                      data-key="${o[0]}"
                    >
                      <span class="eq-key">
                        ${o[0]}
                      </span>

                      <span>
                        ${esc(
                  o.slice(3)
                )}
                      </span>
                    </div>`
            )
            .join('')}
           </div>`;

      } else {

        inputHtml =
          `<div class="eq-sa">

             <textarea
               placeholder="Type your answer here..."
             ></textarea>

             <button class="eq-submit">
               Submit Answer
             </button>

           </div>`;

      }


      el.innerHTML =
        `<div class="eq-header">

          <span class="eq-num">
            Q${i + 1}
          </span>

          <span class="eq-type ${typeCls}">
            ${typeLabel}
          </span>

        </div>

        <div class="eq-text">
          ${esc(q.question)}
        </div>

        ${inputHtml}

        <div class="eq-feedback"></div>`;


      /* MCQ */
      if (
        q.type === 'mcq'
      ) {

        el
          .querySelectorAll(
            '.eq-opt'
          )
          .forEach(
            opt => {

              opt.onclick = () => {

                if (
                  el.dataset.answered ===
                  'true'
                ) {
                  return;
                }


                el.dataset.answered =
                  'true';


                const sel =
                  opt.dataset.key;


                const cor =
                  q.correct;


                el
                  .querySelectorAll(
                    '.eq-opt'
                  )
                  .forEach(
                    o => {

                      if (
                        o.dataset.key ===
                        cor
                      ) {

                        o.classList.add(
                          'correct'
                        );

                      } else if (
                        o === opt &&
                        sel !== cor
                      ) {

                        o.classList.add(
                          'wrong'
                        );

                      }

                    }
                  );


                const fb =
                  el.querySelector(
                    '.eq-feedback'
                  );


                const ok =
                  sel === cor;


                if (ok) {
                  S.examCorrect++;
                }


                fb.className =
                  'eq-feedback ' +
                  (
                    ok
                      ? 'correct'
                      : 'wrong'
                  );


                fb.style.display =
                  'block';


                fb.innerHTML =
                  (
                    ok
                      ? '✅ Correct! '
                      : '❌ Incorrect. Correct: ' +
                      cor +
                      '. '
                  ) +
                  (
                    q.explanation ||
                    ''
                  );


                S.examAnswered++;

                updateScore();

              };

            }
          );

      }


      /* Short answer */
      if (
        q.type !== 'mcq'
      ) {

        const sb =
          el.querySelector(
            '.eq-submit'
          );


        if (sb) {

          sb.onclick =
            async () => {

              if (
                el.dataset.answered ===
                'true'
              ) {
                return;
              }


              const ans =
                el
                  .querySelector(
                    'textarea'
                  )
                  .value
                  .trim();


              if (!ans) {

                toast(
                  'Please write an answer',
                  'warning'
                );

                return;
              }


              el.dataset.answered =
                'true';


              sb.disabled =
                true;


              sb.textContent =
                'Evaluating...';


              try {

                const r =
                  await POST(
                    '/flashcards/evaluate',
                    {
                      question:
                        q.question,

                      userAnswer:
                        ans,

                      modelAnswer:
                        q.model_answer ||
                        ''
                    }
                  );


                const ok =
                  r.score >= 60;


                if (ok) {
                  S.examCorrect++;
                }


                const fb =
                  el.querySelector(
                    '.eq-feedback'
                  );


                fb.className =
                  'eq-feedback ' +
                  (
                    ok
                      ? 'correct'
                      : 'wrong'
                  );


                fb.style.display =
                  'block';


                fb.innerHTML =
                  `<strong>
                     Score: ${r.score}/100
                   </strong>
                   <br/>
                   ${esc(
                    r.feedback || ''
                  )}`;


                S.examAnswered++;

                updateScore();

              } catch (e) {

                sb.disabled =
                  false;


                sb.textContent =
                  'Submit Answer';

              }

            };

        }

      }


      $('exam-area')
        .appendChild(el);

    }
  );

}


function updateScore() {

  const tot =
    S.examQs.length;


  $('sc-correct').textContent =
    S.examCorrect;


  $('sc-total').textContent =
    tot;


  $('sc-pct').textContent =
    S.examAnswered > 0
      ? Math.round(
        S.examCorrect /
        S.examAnswered *
        100
      ) + '%'
      : '—';

}


/* ══════════════════════════════════════════════════
   UI HELPERS
   ══════════════════════════════════════════════════ */

function showWelcome() {

  $('welcome').style.display =
    'flex';


  $('workspace').style.display =
    'none';

}


function showWorkspace() {

  $('welcome').style.display =
    'none';


  $('workspace').style.display =
    'flex';

}


function showUI() {

  if (!S.activeDocId) {
    showWelcome();
  }

}


function switchTab(name) {

  S.tab =
    name;


  $$('.tab').forEach(
    b => {

      b.classList.toggle(
        'active',
        b.dataset.tab === name
      );


      b.setAttribute(
        'aria-selected',
        b.dataset.tab === name
      );

    }
  );


  $$('.tab-panel').forEach(
    p => {

      p.classList.toggle(
        'active',
        p.id ===
        'tab-' + name
      );

    }
  );


  if (
    name === 'summary'
  ) {

    const cs =
      $('compare-section');


    if (cs) {

      cs.style.display =
        S.selectedIds.size >= 2
          ? 'block'
          : 'none';

    }

  }

}


function resetPanels() {

  $('summary-out').innerHTML =
    `<div class="placeholder">
       📝<br/>
       Click Generate to create a summary
     </div>`;


  $('fc-area').innerHTML =
    `<div class="placeholder">
       🃏<br/>
       Generate flashcards to start studying
     </div>`;


  $('exam-area').innerHTML =
    `<div class="placeholder">
       🎓<br/>
       Start an exam to test your knowledge
     </div>`;


  $('fc-stats').style.display =
    'none';


  $('diff-filter').style.display =
    'none';


  $('score-bar').style.display =
    'none';


  $('player').style.display =
    'none';


  $('transcript').style.display =
    'none';


  S.flashcards = [];

  S.examQs = [];


  stopPod();

}


function renderUserBadge() {

  let user;


  try {

    user =
      JSON.parse(
        localStorage.getItem(UK)
      );

  } catch { }


  if (!user) {
    return;
  }


  const initials =
    (
      (user.firstName?.[0] || '') +
      (user.lastName?.[0] || '')
    )
      .toUpperCase() ||
    user.email?.[0]
      ?.toUpperCase() ||
    'U';


  $('user-badge').innerHTML =
    `<div class="ub-avatar">
       ${initials}
     </div>

     <div class="ub-info">

       <div class="ub-name">
         ${esc(
      (
        user.firstName +
        ' ' +
        (user.lastName || '')
      ).trim()
    )}
       </div>

       <div class="ub-email">
         ${esc(
      user.email || ''
    )}
       </div>

     </div>

     <button
       class="ub-logout"
       onclick="signOut()"
       title="Sign out"
     >
       ⏻
     </button>`;

}


function showOverlay(n) {
  const title = $('ov-title');
  const msg = $('ov-msg');
  const overlay = $('overlay');

  if (title) {
    title.textContent = `Processing ${n} file${n > 1 ? 's' : ''}...`;
  }
  if (msg) {
    msg.textContent = 'Extracting text and building knowledge index';
  }
  if (overlay) {
    overlay.style.display = 'flex';
  }
}

function hideOverlay() {
  const overlay = $('overlay');
  if (overlay) {
    overlay.style.display = 'none';
  }
}


function dlCurrent() {

  if (
    S.tab === 'summary'
  ) {

    const t =
      $('summary-out').innerText;


    if (
      t &&
      !t.includes(
        'Click Generate'
      )
    ) {

      dlText(
        t,
        'summary.txt'
      );

    }

  } else if (
    S.tab === 'flashcards'
  ) {

    dlFlashcards();

  } else if (
    S.tab === 'podcast'
  ) {

    dlText(
      S.podScript,
      'podcast-script.txt'
    );

  } else if (
    S.tab === 'chat'
  ) {

    dlText(
      $('chat-msgs').innerText,
      'chat-history.txt'
    );

  }

}


/* ══════════════════════════════════════════════════
   TOAST
   ══════════════════════════════════════════════════ */

function toast(
  msg,
  type = 'info'
) {

  const icons = {
    success: '✅',
    error: '❌',
    warning: '⚠️',
    info: 'ℹ️'
  };


  const el =
    document.createElement(
      'div'
    );


  el.className =
    `toast ${type}`;


  el.innerHTML =
    `<span>
       ${icons[type] || 'ℹ️'}
     </span>

     <span style="flex:1">
       ${esc(msg)}
     </span>

     <span class="toast-close">
       ×
     </span>`;


  const close =
    () => {

      el.classList.add(
        'out'
      );


      setTimeout(
        () => el.remove(),
        300
      );

    };


  el.querySelector(
    '.toast-close'
  ).onclick =
    close;


  $('toasts')
    .appendChild(el);


  setTimeout(
    close,
    4000
  );

}


/* ══════════════════════════════════════════════════
   UTILITIES
   ══════════════════════════════════════════════════ */

function esc(s) {

  if (!s) {
    return '';
  }


  return String(s)
    .replace(
      /&/g,
      '&amp;'
    )
    .replace(
      /</g,
      '&lt;'
    )
    .replace(
      />/g,
      '&gt;'
    )
    .replace(
      /"/g,
      '&quot;'
    );

}


function renderMd(text) {

  if (!text) {
    return '';
  }


  return text

    .replace(
      /&/g,
      '&amp;'
    )

    .replace(
      /</g,
      '&lt;'
    )

    .replace(
      />/g,
      '&gt;'
    )

    .replace(
      /\*\*([^*]+)\*\*/g,
      '<strong>$1</strong>'
    )

    .replace(
      /\*([^*]+)\*/g,
      '<em>$1</em>'
    )

    .replace(
      /`([^`]+)`/g,
      '<code>$1</code>'
    )

    .replace(
      /^### (.+)$/gm,
      '<h3>$1</h3>'
    )

    .replace(
      /^## (.+)$/gm,
      '<h2>$1</h2>'
    )

    .replace(
      /^# (.+)$/gm,
      '<h1>$1</h1>'
    )

    .replace(
      /^[•\-\*] (.+)$/gm,
      '<li>$1</li>'
    )

    .replace(
      /^\d+\. (.+)$/gm,
      '<li>$1</li>'
    )

    .replace(
      /(<li>.*<\/li>\n?)+/g,
      '<ul>$&</ul>'
    )

    .replace(
      /\n\n/g,
      '</p><p>'
    )

    .replace(
      /\n/g,
      '<br/>'
    );

}


function fmtBytes(b) {

  if (!b) {
    return '0B';
  }


  if (b < 1024) {
    return b + 'B';
  }


  if (b < 1048576) {

    return (
      b / 1024
    ).toFixed(1) + 'KB';

  }


  return (
    b / 1048576
  ).toFixed(1) + 'MB';

}


function fmtTime() {

  return new Date()
    .toLocaleTimeString(
      [],
      {
        hour: '2-digit',
        minute: '2-digit'
      }
    );

}


function fmtDur(s) {

  return (
    `${Math.floor(s / 60)}:` +
    `${String(
      s % 60
    ).padStart(2, '0')}`
  );

}


function autoResize(el) {

  el.style.height =
    'auto';


  el.style.height =
    Math.min(
      el.scrollHeight,
      120
    ) + 'px';

}


function dlText(
  text,
  name
) {

  const a =
    document.createElement(
      'a'
    );


  a.href =
    URL.createObjectURL(
      new Blob(
        [text],
        {
          type: 'text/plain'
        }
      )
    );


  a.download =
    name;


  a.click();

}
/* =========================================================
   MOBILE NAVIGATION
   ========================================================= */

let mobilePreviousTab = 'chat';


function openMobileNav() {
  document.body.classList.add('mobile-nav-open');
}


function closeMobileNav() {
  document.body.classList.remove('mobile-nav-open');
}


function updateMobileNavigation() {

  // Highlight active navigation item
  $$('.mobile-nav-item[data-mobile-nav]').forEach(btn => {

    btn.classList.toggle(
      'active',
      btn.dataset.mobileNav === S.tab
    );

  });


  // Show back button except on main chat screen
  if (S.tab && S.tab !== 'chat') {
    document.body.classList.add('mobile-show-back');
  } else {
    document.body.classList.remove('mobile-show-back');
  }
}


function mobileNavigate(tab) {

  if (!tab) return;

  if (S.tab !== tab) {
    mobilePreviousTab = S.tab;
  }

  switchTab(tab);

  updateMobileNavigation();

  closeMobileNav();

  // Scroll to top on mobile
  window.scrollTo({
    top: 0,
    behavior: 'smooth'
  });
}


function mobileGoBack() {

  /*
   * If we came from another tab,
   * return there.
   */
  if (
    mobilePreviousTab &&
    mobilePreviousTab !== S.tab
  ) {

    const previous = mobilePreviousTab;

    mobilePreviousTab = 'chat';

    switchTab(previous);

    updateMobileNavigation();

    window.scrollTo({
      top: 0,
      behavior: 'smooth'
    });

    return;
  }


  /*
   * Otherwise return to Chat.
   */
  if (S.tab !== 'chat') {

    switchTab('chat');

    updateMobileNavigation();

    window.scrollTo({
      top: 0,
      behavior: 'smooth'
    });

    return;
  }


  /*
   * If already on Chat, return to login.
   */
  if (confirm('Leave Saathi and return to the login page?')) {
    location.href = 'login.html';
  }
}


/* =========================================================
   MOBILE USER INFORMATION
   ========================================================= */

function renderMobileUser() {

  const box = $('mobile-nav-user');

  if (!box) return;

  let user = null;

  try {
    user = JSON.parse(
      localStorage.getItem(UK)
    );
  } catch (e) {
    user = null;
  }


  if (!user) {

    box.innerHTML = `
      <div class="mobile-user-row">
        <div class="mobile-user-avatar">U</div>

        <div class="mobile-user-info">
          <div class="mobile-user-name">
            Welcome
          </div>

          <div class="mobile-user-email">
            Saathi AI
          </div>
        </div>
      </div>
    `;

    return;
  }


  const initials =
    (
      (user.firstName?.[0] || '') +
      (user.lastName?.[0] || '')
    )
      .toUpperCase()
      ||
    user.email?.[0]?.toUpperCase()
    ||
    'U';


  const fullName =
    (
      user.firstName +
      ' ' +
      (user.lastName || '')
    ).trim();


  box.innerHTML = `
    <div class="mobile-user-row">

      <div class="mobile-user-avatar">
        ${esc(initials)}
      </div>

      <div class="mobile-user-info">

        <div class="mobile-user-name">
          ${esc(fullName || 'User')}
        </div>

        <div class="mobile-user-email">
          ${esc(user.email || '')}
        </div>

      </div>

    </div>
  `;
}


/* =========================================================
   MOBILE NAV INITIALIZATION
   ========================================================= */

function initMobileNavigation() {

  const menuBtn = $('mobile-menu-btn');
  const closeBtn = $('mobile-close-btn');
  const backdrop = $('mobile-nav-backdrop');
  const backBtn = $('mobile-back-btn');

  const themeBtn = $('mobile-theme-btn');
  const themeToggle = $('mobile-theme-toggle');

  const documentsBtn = $('mobile-documents-btn');
  const logoutBtn = $('mobile-logout-btn');


  /* Open menu */

  if (menuBtn) {
    menuBtn.onclick = openMobileNav;
  }


  /* Close menu */

  if (closeBtn) {
    closeBtn.onclick = closeMobileNav;
  }


  if (backdrop) {
    backdrop.onclick = closeMobileNav;
  }


  /* Back */

  if (backBtn) {
    backBtn.onclick = mobileGoBack;
  }


  /* Navigation */

  $$('.mobile-nav-item[data-mobile-nav]').forEach(btn => {

    btn.onclick = () => {

      mobileNavigate(
        btn.dataset.mobileNav
      );

    };

  });


  /* Documents */

  if (documentsBtn) {

    documentsBtn.onclick = () => {

      closeMobileNav();

      /*
       * Keep the current document/workspace visible.
       * Scroll to the document section in the sidebar.
       */
      const docList = $('doc-list');

      if (docList) {

        docList.scrollIntoView({
          behavior: 'smooth',
          block: 'start'
        });

      }

    };

  }


  /* Theme */

  if (themeBtn) {

    themeBtn.onclick = () => {

      const existing = $('theme-btn');

      if (existing) {
        existing.click();
      }

    };

  }


  if (themeToggle) {

    themeToggle.onclick = () => {

      const existing = $('theme-btn');

      if (existing) {
        existing.click();
      }

      closeMobileNav();

    };

  }


  /* Sign out */

  if (logoutBtn) {

    logoutBtn.onclick = () => {

      closeMobileNav();

      signOut();

    };

  }


  /* User */

  renderMobileUser();

  updateMobileNavigation();
}


/* =========================================================
   KEEP MOBILE NAV IN SYNC WITH EXISTING TABS
   ========================================================= */

const originalSwitchTab = switchTab;

switchTab = function(name) {

  originalSwitchTab(name);

  updateMobileNavigation();

};