(() => {
  'use strict';

  // ============================================================ helpers
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const EXT = ['.pdf', '.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp', '.webp', '.gif'];
  // Languages we want to surface first. The full list comes from /api/info.
  const WANTED_LANGS = ['eng', 'ben', 'hin', 'urd', 'ara'];
  const LANG_FALLBACK = { eng: 'English', ben: 'Bangla', hin: 'Hindi', urd: 'Urdu', ara: 'Arabic' };

  const fmtSize = (n) => n < 1024 * 1024
    ? Math.max(1, Math.round(n / 1024)) + ' KB'
    : (n / 1048576).toFixed(1) + ' MB';
  const fmtInt = (n) => (n || 0).toLocaleString();
  const stemOf = (name) => name.replace(/\.[^.]+$/, '').replace(/[\u0000-\u001f\\/:*?"<>|]/g, '_').trim() || 'text';
  const extOf = (name) => { const i = name.lastIndexOf('.'); return i < 0 ? '' : name.slice(i).toLowerCase(); };
  const plural = (n, one, many) => n + ' ' + (n === 1 ? one : many);
  const extGroup = (ext) => ext === '.pdf' ? 'pdf' : (ext === '.tif' || ext === '.tiff') ? 'tif' : 'img';
  const safeExt = (ext) => (ext && EXT.includes(ext)) ? ext : '';
  const extLabel = (ext) => ext === '.pdf' ? 'PDF' : (ext === '.tif' || ext === '.tiff') ? 'TIF' : ((ext || '').slice(1) || '?').toUpperCase();

  // ============================================================ state
  const state = {
    items: [],            // [{ key, file, name, size, modified, status, progress, text, error, warning, meta, jobId, serverId, pagesDone, pagesTotal, chars }]
    selected: null,
    running: false,
    jobId: null,
    timer: null,
    nextKey: 1,
    info: null,
    startedAt: null,
    elapsedTimer: null,
    // search
    query: '',
    matches: [],          // [{start, end}]
    activeMatch: -1,
  };

  // ============================================================ elements
  const els = {
    input: $('#file-input'),
    sheet: $('#sheet'),
    list: $('#files'),
    go: $('#go'),
    goLabel: $('#go-label'),
    cancel: $('#cancel'),
    zip: $('#zip'),
    zipLabel: $('#zip-label'),
    langList: $('#lang-list'),
    langHint: $('#lang-hint'),
    force: $('#force-ocr'),
    markers: $('#page-markers'),
    dpi: $('#dpi'),

    // reader
    empty: $('#reader-empty'),
    body: $('#reader-body'),
    title: $('#reader-title'),
    meta: $('#reader-meta'),
    msg: $('#reader-msg'),
    textShell: $('#text-shell'),
    textRender: $('#text-render'),
    text: $('#reader-text'),
    copy: $('#copy'),
    download: $('#download'),
    search: $('#search'),
    searchCount: $('#search-count'),
    searchPrev: $('#search-prev'),
    searchNext: $('#search-next'),
    searchWrap: $('#search-wrap'),

    // stats
    statFiles: $('#stat-files'),
    statFilesSub: $('#stat-files-sub'),
    statPages: $('#stat-pages'),
    statPagesSub: $('#stat-pages-sub'),
    statChars: $('#stat-chars'),
    statCharsSub: $('#stat-chars-sub'),
    statTime: $('#stat-time'),
    statTimeSub: $('#stat-time-sub'),

    // status
    statusPill: $('#status-pill'),
    statusText: $('#status-text'),

    // toasts
    toastStack: $('#toast-stack'),
  };

  // DOM cache for file rows.
  const rows = new Map();

  // ============================================================ toasts
  const TOAST_ICONS = {
    info: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>',
    ok:   '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>',
    warn: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
    error:'<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',
  };

  function toast({ kind = 'info', title = '', message = '', timeout = 4500 }) {
    const el = document.createElement('div');
    el.className = 'toast ' + kind;
    el.innerHTML = `
      <span class="toast-icon" aria-hidden="true">${TOAST_ICONS[kind] || TOAST_ICONS.info}</span>
      <div class="toast-body">
        ${title ? `<div class="toast-title"></div>` : ''}
        ${message ? `<div class="toast-msg"></div>` : ''}
      </div>`;
    if (title) el.querySelector('.toast-title').textContent = title;
    if (message) el.querySelector('.toast-msg').textContent = message;
    els.toastStack.appendChild(el);
    const dismiss = () => {
      el.classList.add('is-leaving');
      el.addEventListener('animationend', () => el.remove(), { once: true });
    };
    if (timeout > 0) setTimeout(dismiss, timeout);
    el.addEventListener('click', dismiss);
    return dismiss;
  }

  // ============================================================ files
  function addFiles(fileList) {
    const rejected = [];
    let added = 0;
    for (const file of fileList) {
      if (!EXT.includes(extOf(file.name))) { rejected.push(file.name); continue; }
      if (state.items.some((it) => it.name === file.name && it.size === file.size && it.modified === file.lastModified)) continue;
      if (state.items.length >= ((state.info && state.info.max_files) || 30)) {
        toast({ kind: 'warn', title: 'File limit reached', message: `You can add up to ${(state.info && state.info.max_files) || 30} files at a time.` });
        break;
      }
      const ext = extOf(file.name);
      state.items.push({
        key: state.nextKey++,
        file, name: file.name, size: file.size, modified: file.lastModified,
        ext,
        status: 'ready', progress: 0, text: null, error: null, warning: null, meta: '',
        jobId: null, serverId: null, pagesDone: 0, pagesTotal: 0, chars: 0,
      });
      added++;
    }
    if (rejected.length) {
      const list = rejected.slice(0, 3).join(', ') + (rejected.length > 3 ? ', …' : '');
      toast({ kind: 'error', title: plural(rejected.length, 'file', 'files') + ' skipped', message: `${list}. Use PDF, PNG, JPG, TIFF, BMP, WebP or GIF.` });
    } else if (added) {
      toast({ kind: 'ok', title: plural(added, 'file', 'files') + ' added', timeout: 1800 });
    }
    if (!state.selected && state.items.length) state.selected = state.items[0].key;
    render();
  }

  function removeItem(key) {
    if (state.running) return;
    state.items = state.items.filter((it) => it.key !== key);
    if (state.selected === key) state.selected = state.items.length ? state.items[0].key : null;
    render();
  }

  function moveItem(fromKey, toIndex) {
    if (state.running) return;
    const from = state.items.findIndex((it) => it.key === fromKey);
    if (from < 0) return;
    const [item] = state.items.splice(from, 1);
    if (toIndex > from) toIndex -= 1;
    state.items.splice(Math.max(0, Math.min(state.items.length, toIndex)), 0, item);
    render();
  }

  // ============================================================ render: file list
  function statusLabel(it) {
    switch (it.status) {
      case 'ready':     return fmtSize(it.size);
      case 'queued':    return 'Waiting';
      case 'running':   return it.pagesTotal > 1
        ? 'Reading page ' + Math.min(it.pagesDone + 1, it.pagesTotal) + ' of ' + it.pagesTotal
        : 'Reading';
      case 'done':      return it.warning ? 'No text found' : fmtInt(it.chars) + ' characters';
      case 'failed':    return 'Could not read';
      case 'cancelled': return 'Cancelled';
      default: return '';
    }
  }

  function renderList() {
    const seen = new Set();
    state.items.forEach((it, index) => {
      seen.add(it.key);
      let row = rows.get(it.key);
      if (!row) {
        const li = document.createElement('li');
        li.className = 'file';
        li.draggable = !state.running;

        const handle = document.createElement('span');
        handle.className = 'file-handle';
        handle.setAttribute('aria-hidden', 'true');
        handle.textContent = '⋮⋮';

        const icon = document.createElement('span');
        icon.className = 'file-icon';

        const main = document.createElement('button');
        main.type = 'button';
        main.className = 'file-main';
        const name = document.createElement('span');
        name.className = 'file-name';
        const meta = document.createElement('span');
        meta.className = 'file-meta';
        main.append(name, meta);

        const status = document.createElement('span');
        status.className = 'file-status';

        const rm = document.createElement('button');
        rm.type = 'button';
        rm.className = 'file-remove';
        rm.setAttribute('aria-label', 'Remove');
        rm.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';

        li.append(handle, icon, main, status, rm);

        // ----- events
        main.addEventListener('click', () => { state.selected = it.key; render(); });
        rm.addEventListener('click', () => removeItem(it.key));

        // ----- drag to reorder
        li.addEventListener('dragstart', (e) => {
          if (state.running) { e.preventDefault(); return; }
          li.classList.add('dragging');
          e.dataTransfer.effectAllowed = 'move';
          e.dataTransfer.setData('text/plain', String(it.key));
        });
        li.addEventListener('dragend', () => {
          li.classList.remove('dragging');
          li.classList.remove('drop-before');
          li.classList.remove('drop-after');
        });
        li.addEventListener('dragover', (e) => {
          if (state.running) return;
          e.preventDefault();
          e.dataTransfer.dropEffect = 'move';
          const rect = li.getBoundingClientRect();
          const before = (e.clientY - rect.top) < rect.height / 2;
          li.classList.toggle('drop-before', before);
          li.classList.toggle('drop-after', !before);
        });
        li.addEventListener('dragleave', () => {
          li.classList.remove('drop-before');
          li.classList.remove('drop-after');
        });
        li.addEventListener('drop', (e) => {
          if (state.running) return;
          e.preventDefault();
          li.classList.remove('drop-before');
          li.classList.remove('drop-after');
          const fromKey = Number(e.dataTransfer.getData('text/plain'));
          if (!fromKey || fromKey === it.key) return;
          const rect = li.getBoundingClientRect();
          const before = (e.clientY - rect.top) < rect.height / 2;
          const target = state.items.findIndex((x) => x.key === it.key);
          moveItem(fromKey, before ? target : target + 1);
        });

        row = { li, icon, name, meta, status, rm };
        rows.set(it.key, row);
      }

      if (els.list.children[index] !== row.li) {
        els.list.insertBefore(row.li, els.list.children[index] || null);
      }
      row.icon.className = 'file-icon ' + extGroup(it.ext);
      row.icon.textContent = extLabel(it.ext);
      row.name.textContent = it.name;
      row.name.title = it.name;
      row.meta.textContent = statusLabel(it);
      row.status.textContent = ({
        ready: 'Ready', queued: 'Queued', running: 'Reading', done: 'Done', failed: 'Failed', cancelled: 'Cancelled'
      })[it.status] || '';
      const p = it.status === 'running' ? Math.round(it.progress * 100) + '%' : '0%';
      row.name.style.setProperty('--p', it.status === 'running' ? p : '0%');
      row.li.classList.toggle('is-running', it.status === 'running');
      row.li.classList.toggle('is-done', it.status === 'done');
      row.li.classList.toggle('is-failed', it.status === 'failed');
      row.li.draggable = !state.running;
      row.li.setAttribute('aria-current', state.selected === it.key ? 'true' : 'false');
      row.rm.hidden = state.running;
      row.rm.setAttribute('aria-label', 'Remove ' + it.name);
    });
    for (const [key, row] of rows) {
      if (!seen.has(key)) { row.li.remove(); rows.delete(key); }
    }
  }

  // ============================================================ render: reader
  function renderReader() {
    const it = state.items.find((x) => x.key === state.selected);
    els.empty.hidden = !!it;
    els.body.hidden = !it;
    if (!it) return;
    els.title.textContent = it.name;

    // text / progress
    if (it.status === 'done') {
      els.meta.textContent = it.meta;
      // show rendered (highlighted) view by default; switch to editable on focus
      els.textShell.hidden = false;
      if (document.activeElement !== els.text) {
        if (els.text.dataset.key !== String(it.key)) {
          els.text.value = it.text || '';
          els.text.dataset.key = String(it.key);
          renderTextView();
        }
      }
      els.copy.hidden = false;
      els.download.hidden = false;
      els.searchWrap.hidden = false;
      els.msg.hidden = !!it.warning ? false : true;
      els.msg.className = 'progress-line ' + (it.warning ? 'warn' : 'ok');
      els.msg.innerHTML = it.warning
        ? '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>' +
          ' ' + it.warning
        : '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>' +
          ' Done — ready to copy or download.';
    } else {
      els.text.dataset.key = '';
      els.textShell.hidden = true;
      els.copy.hidden = true;
      els.download.hidden = true;
      els.searchWrap.hidden = true;
      els.meta.textContent = fmtSize(it.size);
      if (it.status === 'ready') {
        els.msg.hidden = false;
        els.msg.className = 'progress-line';
        els.msg.textContent = 'Not extracted yet. Choose Extract text on the left.';
      } else if (it.status === 'queued') {
        els.msg.hidden = false;
        els.msg.className = 'progress-line';
        els.msg.textContent = 'Waiting for the files before it.';
      } else if (it.status === 'running') {
        els.msg.hidden = false;
        els.msg.className = 'progress-line';
        els.msg.innerHTML = '<span class="spinner"></span> ' + statusLabel(it) + '…';
      } else if (it.status === 'failed') {
        els.msg.hidden = false;
        els.msg.className = 'progress-line error';
        els.msg.textContent = it.error || 'This file could not be read.';
      } else if (it.status === 'cancelled') {
        els.msg.hidden = false;
        els.msg.className = 'progress-line warn';
        els.msg.textContent = 'Cancelled. Choose Extract text to try again.';
      } else {
        els.msg.hidden = true;
      }
    }
  }

  // ============================================================ render: controls + stats
  function renderControls() {
    const pending = state.items.filter((it) => it.status !== 'done');
    els.go.disabled = state.running || pending.length === 0;
    els.goLabel.textContent = pending.length > 1
      ? 'Extract text from ' + pending.length + ' files'
      : 'Extract text';
    els.cancel.hidden = !state.running;
    const doneCount = state.items.filter((it) => it.status === 'done').length;
    els.zip.hidden = doneCount < 2;
    els.zipLabel.textContent = doneCount >= 2
      ? 'Download all as .zip (' + doneCount + ')'
      : 'Download all as .zip';
  }

  function renderStats() {
    const total = state.items.length;
    const done = state.items.filter((it) => it.status === 'done');
    const failed = state.items.filter((it) => it.status === 'failed');
    const chars = done.reduce((s, it) => s + (it.chars || 0), 0);
    const pagesDone = state.items.reduce((s, it) => s + (it.pagesDone || 0), 0);
    const pagesTotal = state.items.reduce((s, it) => s + (it.pagesTotal || 0), 0);

    els.statFiles.textContent = total;
    els.statFiles.classList.toggle('is-active', state.running || pending() > 0);
    els.statFilesSub.textContent = total === 0
      ? 'No files yet'
      : doneCount() + ' done' + (failed.length ? ', ' + failed.length + ' failed' : '');

    els.statPages.textContent = pagesDone;
    els.statPages.classList.toggle('is-active', state.running && pagesTotal > 0 && pagesDone < pagesTotal);
    els.statPagesSub.textContent = pagesTotal
      ? pagesDone + ' of ' + pagesTotal + (state.running ? ' pages' : ' pages read')
      : 'Waiting to start';

    els.statChars.textContent = fmtInt(chars);
    els.statChars.classList.toggle('is-active', chars > 0 && !state.running);
    els.statCharsSub.textContent = done.length
      ? 'From ' + done.length + ' ' + (done.length === 1 ? 'file' : 'files')
      : 'No text extracted yet';
  }

  function doneCount() { return state.items.filter((it) => it.status === 'done').length; }
  function pending() { return state.items.filter((it) => it.status !== 'done').length; }

  function renderTime() {
    if (state.running && state.startedAt) {
      const secs = Math.max(0, Math.floor((Date.now() - state.startedAt) / 1000));
      const m = Math.floor(secs / 60);
      const s = secs % 60;
      els.statTime.textContent = m + ':' + String(s).padStart(2, '0');
      els.statTimeSub.textContent = 'Extracting…';
      els.statTime.classList.add('is-active');
    } else {
      els.statTime.classList.remove('is-active');
      if (state.items.length === 0) {
        els.statTime.textContent = '0:00';
        els.statTimeSub.textContent = 'Idle';
      } else {
        const done = doneCount();
        if (done > 0) {
          els.statTimeSub.textContent = 'Finished';
        } else {
          els.statTimeSub.textContent = 'Ready';
        }
      }
    }
  }

  function render() {
    renderList();
    renderReader();
    renderControls();
    renderStats();
  }

  // ============================================================ languages
  function renderLanguages(info) {
    els.langList.textContent = '';
    const have = new Set(info.languages.map((l) => l.code));
    const priority = WANTED_LANGS.filter((c) => have.has(c))
      .map((c) => ({ code: c, name: info.languages.find((l) => l.code === c).name, missing: false }));
    const missing = WANTED_LANGS.filter((c) => !have.has(c))
      .map((c) => ({ code: c, name: LANG_FALLBACK[c] || c, missing: true }));
    const rest = info.languages.filter((l) => !WANTED_LANGS.includes(l.code));
    const shown = [...priority, ...missing, ...rest];
    for (const lang of shown) {
      const label = document.createElement('label');
      label.className = 'lang-chip' + (lang.missing ? ' missing' : '');
      const box = document.createElement('input');
      box.type = 'checkbox';
      box.value = lang.code;
      box.checked = !lang.missing && info.default.includes(lang.code);
      box.disabled = !!lang.missing;
      const mark = document.createElement('span');
      mark.className = 'check-mark';
      const name = document.createElement('span');
      name.textContent = lang.name + (lang.missing ? ' (not installed)' : '');
      label.append(box, mark, name);
      els.langList.appendChild(label);
    }

    // Build a hint that mentions every missing priority language, with the
    // install command for the user's platform. Avoids the old hard-coded
    // "install Bangla" message when, say, only Hindi is missing.
    if (!info.tesseract) {
      els.langHint.innerHTML = 'The text reader (Tesseract) is not installed. PDFs that already contain text still work. Scanned pages and images need Tesseract; see the <a href="https://github.com/tesseract-ocr/tesseract" target="_blank" rel="noopener">setup steps in the README</a>.';
    } else if (missing.length > 0) {
      const names = missing.map((m) => m.name).join(', ');
      const packages = missing.map((m) => 'tesseract-ocr-' + m.code).join(' ');
      const platform = navigator.userAgent.includes('Mac') ? 'macOS' : navigator.userAgent.includes('Windows') ? 'Windows' : 'Ubuntu';
      const cmd = platform === 'macOS'
        ? 'brew install ' + packages
        : platform === 'Windows'
          ? '(use the UB Mannheim installer and tick the languages)'
          : 'sudo apt install ' + packages;
      els.langHint.innerHTML =
        '<strong>Not installed:</strong> ' + names + '. On ' + platform + ' run <code>' +
        cmd + '</code> then restart this app.';
    } else {
      els.langHint.textContent = 'Pick every language that appears in your files.';
    }
  }

  function selectedLangs() { return $$('input:checked', els.langList).map((b) => b.value); }

  // ============================================================ status pill
  function setStatus(kind, text) {
    els.statusPill.classList.remove('is-ok', 'is-bad', 'is-warn');
    if (kind) els.statusPill.classList.add('is-' + kind);
    els.statusText.textContent = text;
  }

  // ============================================================ job lifecycle
  async function start() {
    const todo = state.items.filter((it) => it.status !== 'done');
    if (!todo.length || state.running) return;
    const langs = selectedLangs();
    if (state.info && state.info.tesseract && !langs.length) {
      toast({ kind: 'warn', title: 'Pick a language', message: 'At least one language must be selected before extracting.' });
      return;
    }
    const form = new FormData();
    for (const it of todo) form.append('files', it.file, it.name);
    form.append('lang', langs.join('+'));
    form.append('dpi', els.dpi.value);
    form.append('force_ocr', els.force.checked ? '1' : '0');
    form.append('page_markers', els.markers.checked ? '1' : '0');

    state.running = true;
    state.startedAt = Date.now();
    todo.forEach((it, i) => {
      it.status = 'queued'; it.progress = 0; it.error = null; it.warning = null;
      it.serverId = 'f' + i; it.pagesDone = 0; it.pagesTotal = 0; it.chars = 0; it.text = null;
    });
    if (!todo.some((it) => it.key === state.selected)) state.selected = todo[0].key;
    startElapsedTimer();
    render();
    setStatus('warn', 'Extracting…');

    try {
      const res = await fetch('/api/jobs', { method: 'POST', body: form });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || 'The upload failed. Try again.');
      state.jobId = data.job_id;
      todo.forEach((it) => { it.jobId = data.job_id; });
      poll();
    } catch (err) {
      state.running = false;
      stopElapsedTimer();
      todo.forEach((it) => { it.status = 'ready'; });
      setStatus('bad', 'Upload failed');
      toast({ kind: 'error', title: 'Could not start', message: err.message || 'Is the app still running?' });
      render();
    }
  }

  async function poll() {
    clearTimeout(state.timer);
    try {
      const res = await fetch('/api/jobs/' + state.jobId);
      if (!res.ok) throw new Error('lost');
      const job = await res.json();
      for (const f of job.files) {
        const it = state.items.find((x) => x.jobId === state.jobId && x.serverId === f.id);
        if (!it) continue;
        const wasDone = it.status === 'done';
        it.status = f.status; it.pagesDone = f.pages_done; it.pagesTotal = f.pages_total;
        it.progress = f.pages_total ? f.pages_done / f.pages_total : 0;
        it.chars = f.chars; it.error = f.error; it.warning = f.warning;
        if (f.status === 'done' && !wasDone) {
          const t = await fetch('/api/jobs/' + state.jobId + '/files/' + f.id + '/text');
          it.text = t.ok ? await t.text() : '';
          const parts = [];
          if (f.text_pages) parts.push(plural(f.text_pages, 'page', 'pages') + ' with text');
          if (f.ocr_pages) parts.push(plural(f.ocr_pages, 'page', 'pages') + ' read as images');
          parts.push(it.text.length.toLocaleString() + ' characters');
          it.meta = parts.join(', ');
          it.chars = it.text.length;
        }
      }
      render();
      if (job.status === 'done' || job.status === 'cancelled') { finish(job); return; }
    } catch (err) {
      state.running = false;
      stopElapsedTimer();
      state.items.forEach((it) => { if (it.status === 'queued' || it.status === 'running') it.status = 'ready'; });
      setStatus('bad', 'Lost contact');
      toast({ kind: 'error', title: 'Lost contact with the app', message: 'Your files were not changed.' });
      render();
      return;
    }
    state.timer = setTimeout(poll, 600);
  }

  function finish(job) {
    state.running = false;
    stopElapsedTimer();
    const done = job.files.filter((f) => f.status === 'done').length;
    const failed = job.files.filter((f) => f.status === 'failed').length;
    if (job.status === 'cancelled') {
      setStatus('warn', 'Cancelled');
      toast({ kind: 'warn', title: 'Cancelled', message: 'Files already finished are kept.' });
    } else if (failed) {
      setStatus('warn', done + ' done, ' + failed + ' failed');
      toast({ kind: 'error', title: plural(done, 'file', 'files') + ' done', message: failed + ' could not be read. Select a file to see why.' });
    } else {
      setStatus('ok', plural(done, 'file', 'files') + ' extracted');
      toast({ kind: 'ok', title: 'All done!', message: plural(done, 'file', 'files') + ' extracted.' });
    }
    render();
  }

  async function cancel() {
    if (!state.jobId) return;
    els.cancel.disabled = true;
    try { await fetch('/api/jobs/' + state.jobId + '/cancel', { method: 'POST' }); }
    finally { els.cancel.disabled = false; }
  }

  function startElapsedTimer() {
    stopElapsedTimer();
    state.elapsedTimer = setInterval(renderTime, 500);
  }
  function stopElapsedTimer() {
    if (state.elapsedTimer) { clearInterval(state.elapsedTimer); state.elapsedTimer = null; }
    renderTime();
  }

  // ============================================================ copy / download / search
  function currentItem() { return state.items.find((x) => x.key === state.selected); }

  async function copyText() {
    const it = currentItem(); if (!it) return;
    try { await navigator.clipboard.writeText(els.text.value); toast({ kind: 'ok', title: 'Copied', message: it.text.length.toLocaleString() + ' characters to clipboard.', timeout: 1800 }); }
    catch (e) { els.text.focus(); els.text.select(); document.execCommand('copy'); }
  }

  function saveBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = filename;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  }

  function downloadText() {
    const it = currentItem(); if (!it) return;
    saveBlob(new Blob([els.text.value], { type: 'text/plain;charset=utf-8' }), stemOf(it.name) + '.txt');
    toast({ kind: 'ok', title: 'Downloaded', message: stemOf(it.name) + '.txt', timeout: 1800 });
  }

  async function downloadZip() {
    const files = state.items.filter((it) => it.status === 'done')
      .map((it) => ({ name: it.name, text: it.key === state.selected ? els.text.value : (it.text || '') }));
    try {
      const res = await fetch('/api/zip', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ files }) });
      if (!res.ok) { toast({ kind: 'error', title: 'Could not build zip', message: 'Try downloading files one by one.' }); return; }
      saveBlob(await res.blob(), 'extracted-text.zip');
      toast({ kind: 'ok', title: 'Zip downloaded', message: files.length + ' ' + (files.length === 1 ? 'file' : 'files') + ' inside.', timeout: 2400 });
    } catch (e) {
      toast({ kind: 'error', title: 'Network error', message: 'Could not build zip file.' });
    }
  }

  // ----- rendered text view with search highlighting
  function renderTextView() {
    const text = els.text.value || '';
    state.matches = [];
    state.activeMatch = -1;
    const q = state.query;
    if (!q) {
      els.textRender.textContent = text;
      els.searchCount.textContent = '';
      els.searchPrev.disabled = true;
      els.searchNext.disabled = true;
      return;
    }
    const re = new RegExp(escapeRegExp(q), 'gi');
    let m, last = 0, html = '';
    while ((m = re.exec(text)) !== null) {
      const start = m.index, end = start + m[0].length;
      state.matches.push({ start, end });
      html += escapeHtml(text.slice(last, start));
      html += '<mark>' + escapeHtml(text.slice(start, end)) + '</mark>';
      last = end;
      if (m.index === re.lastIndex) re.lastIndex++; // safety
    }
    html += escapeHtml(text.slice(last));
    els.textRender.innerHTML = html;
    updateSearchCount();
  }

  function updateSearchCount() {
    if (!state.query) { els.searchCount.textContent = ''; return; }
    if (state.matches.length === 0) {
      els.searchCount.textContent = '0';
      els.searchCount.classList.add('is-zero');
    } else {
      els.searchCount.textContent = (state.activeMatch + 1) + ' / ' + state.matches.length;
      els.searchCount.classList.remove('is-zero');
    }
    els.searchPrev.disabled = state.matches.length === 0;
    els.searchNext.disabled = state.matches.length === 0;
    // highlight active match
    const marks = els.textRender.querySelectorAll('mark');
    marks.forEach((m, i) => m.classList.toggle('is-active', i === state.activeMatch));
    if (state.activeMatch >= 0 && marks[state.activeMatch]) {
      marks[state.activeMatch].scrollIntoView({ block: 'center', behavior: 'smooth' });
    }
  }

  function jumpMatch(delta) {
    if (state.matches.length === 0) return;
    state.activeMatch = (state.activeMatch + delta + state.matches.length) % state.matches.length;
    updateSearchCount();
  }

  function escapeRegExp(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }
  function escapeHtml(s) {
    return s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  // ============================================================ wiring
  els.input.addEventListener('change', () => { addFiles(els.input.files); els.input.value = ''; });
  els.go.addEventListener('click', start);
  els.cancel.addEventListener('click', cancel);
  els.zip.addEventListener('click', downloadZip);
  els.copy.addEventListener('click', copyText);
  els.download.addEventListener('click', downloadText);

  // switch reader into editable mode on focus; back to highlighted view on blur
  els.textRender.addEventListener('focus', () => {
    els.textRender.hidden = true;
    els.text.hidden = false;
    els.text.focus();
  });
  els.text.addEventListener('blur', () => {
    if (els.text.value !== currentItem()?.text) {
      const it = currentItem(); if (it) it.text = els.text.value;
    }
    renderTextView();
    els.text.hidden = true;
    els.textRender.hidden = false;
  });
  els.text.addEventListener('input', () => { const it = currentItem(); if (it) it.text = els.text.value; });

  // search
  let searchDebounce;
  els.search.addEventListener('input', () => {
    state.query = els.search.value;
    state.activeMatch = -1;
    clearTimeout(searchDebounce);
    searchDebounce = setTimeout(renderTextView, 120);
  });
  els.searchPrev.addEventListener('click', () => jumpMatch(-1));
  els.searchNext.addEventListener('click', () => jumpMatch(1));
  els.search.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') { e.preventDefault(); jumpMatch(e.shiftKey ? -1 : 1); }
    if (e.key === 'Escape') { els.search.value = ''; state.query = ''; renderTextView(); }
  });

  // drag-and-drop file ingestion
  let dragDepth = 0;
  window.addEventListener('dragenter', (e) => {
    if (![...e.dataTransfer.types].includes('Files')) return;
    e.preventDefault(); dragDepth++;
    els.sheet.classList.add('drag');
  });
  window.addEventListener('dragleave', () => {
    dragDepth = Math.max(0, dragDepth - 1);
    if (!dragDepth) els.sheet.classList.remove('drag');
  });
  window.addEventListener('dragover', (e) => {
    if ([...e.dataTransfer.types].includes('Files')) e.preventDefault();
  });
  window.addEventListener('drop', (e) => {
    if (!e.dataTransfer || !e.dataTransfer.files.length) return;
    e.preventDefault();
    dragDepth = 0;
    els.sheet.classList.remove('drag');
    addFiles(e.dataTransfer.files);
  });

  window.addEventListener('beforeunload', (e) => { if (state.running) { e.preventDefault(); e.returnValue = ''; } });

  // keyboard shortcuts
  window.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter' && !els.go.disabled) {
      e.preventDefault(); start();
    }
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
      e.preventDefault();
      els.search.focus();
      els.search.select();
    }
  });

  // boot
  fetch('/api/info').then((r) => r.json()).then((info) => {
    state.info = info;
    $('#limit-mb').textContent = info.max_upload_mb;
    renderLanguages(info);
    if (info.tesseract) {
      setStatus('ok', 'Tesseract ' + (info.version || 'ready'));
    } else {
      setStatus('warn', 'Tesseract not installed');
    }
    render();
  }).catch(() => {
    setStatus('bad', 'Unreachable');
    toast({ kind: 'error', title: 'Could not reach the app', message: 'Is it still running?' });
  });

  render();
})();
