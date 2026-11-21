(function () {
  'use strict';

  var COLS = ['A', 'B', 'C', 'D', 'E', 'F'];
  var ROWS = 8;
  var LAST_KEY = 'sheet_history.last';

  var $ = function (id) { return document.getElementById(id); };
  var els = {
    title: $('sheet-title'), save: $('save-btn'), neu: $('new-btn'), sample: $('load-sample-btn'),
    list: $('project-list'), status: $('status'), conflict: $('conflict'),
    conflictText: $('conflict-text'), reload: $('conflict-reload'), retry: $('conflict-retry'),
    empty: $('empty-state'), grid: $('grid')
  };

  var sheet = null;        // last server version
  var local = {};          // cell id -> text (local edits)
  var conflictSheet = null;
  var busy = false;
  var inputs = {};
  var outputs = {};
  var sheets = [];

  function cellId(c, r) { return COLS[c] + (r + 1); }

  function setStatus(text, kind) {
    els.status.textContent = text;
    els.status.className = kind || '';
  }

  function savedCells() { return (sheet && sheet.cells) || {}; }

  function isDirty() {
    if (!sheet) return false;
    if (els.title.value !== sheet.title) return true;
    var saved = savedCells();
    for (var c = 0; c < COLS.length; c++) {
      for (var r = 0; r < ROWS; r++) {
        var id = cellId(c, r);
        if ((local[id] || '') !== (saved[id] || '')) return true;
      }
    }
    return false;
  }

  function refreshCell(id) {
    var saved = savedCells();
    var same = (local[id] || '') === (saved[id] || '');
    var out = outputs[id];
    var comp = sheet && sheet.computed ? sheet.computed[id] : undefined;
    out.textContent = (same && comp !== undefined) ? comp : '';
    inputs[id].parentNode.classList.toggle('dirty', !same);
  }

  function refreshAll() {
    Object.keys(inputs).forEach(refreshCell);
    var open = !!sheet;
    els.save.disabled = !open || busy;
    els.sample.disabled = !open;
    els.title.disabled = !open;
    Object.keys(inputs).forEach(function (id) { inputs[id].disabled = !open; });
    els.neu.disabled = busy;
  }

  function markEdited() {
    refreshAll();
    if (isDirty()) setStatus('Unsaved changes', 'dirty');
    else setStatus('');
  }

  function applySheet(s) {
    sheet = s;
    local = {};
    Object.keys(s.cells || {}).forEach(function (k) { local[k] = s.cells[k]; });
    Object.keys(inputs).forEach(function (id) { inputs[id].value = local[id] || ''; });
    els.title.value = s.title;
    hideConflict();
    refreshAll();
    renderList();
    try { localStorage.setItem(LAST_KEY, String(s.id)); } catch (e) { /* ignore */ }
  }

  function showConflict(current) {
    conflictSheet = current;
    var changed = [];
    var base = (sheet && sheet.cells) || {};
    Object.keys(current.cells).concat(Object.keys(base)).forEach(function (id) {
      if ((current.cells[id] || '') !== (base[id] || '') && changed.indexOf(id) < 0) changed.push(id);
    });
    els.conflictText.textContent = 'This sheet changed elsewhere. The server is at revision ' +
      current.revision + '. Your edits are kept here and nothing was saved. ' +
      (changed.length
        ? 'Cells changed on the server: ' + changed.join(', ') + '. Keep my edits and retry will overwrite them.'
        : 'Only the title or revision changed on the server.');
    els.conflict.hidden = false;
    els.reload.focus();
  }

  function hideConflict() {
    conflictSheet = null;
    els.conflict.hidden = true;
    els.conflictText.textContent = '';
  }

  // ---- network ----
  function api(method, path, body) {
    var opts = { method: method, headers: {} };
    if (body !== undefined) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    }
    return fetch(path, opts).then(function (res) {
      return res.json().catch(function () { return {}; }).then(function (data) {
        return { status: res.status, ok: res.ok, data: data };
      });
    });
  }

  function errMsg(r) {
    return (r.data && r.data.error && r.data.error.message) || ('Request failed (' + r.status + ')');
  }

  var NET_MSG = 'Could not reach the server. Your edits are kept; try Save again.';

  function loadList() {
    return api('GET', '/api/v1/sheets').then(function (r) {
      if (!r.ok) { setStatus(errMsg(r), 'error'); return; }
      sheets = r.data.sheets || [];
      renderList();
    });
  }

  function renderList() {
    while (els.list.firstChild) els.list.removeChild(els.list.firstChild);
    sheets.forEach(function (s) {
      var li = document.createElement('li');
      var b = document.createElement('button');
      b.type = 'button';
      var shown = (sheet && sheet.id === s.id) ? sheet : s;
      b.textContent = shown.title + ' (rev ' + shown.revision + ')';
      if (sheet && sheet.id === s.id) b.setAttribute('aria-current', 'true');
      b.addEventListener('click', function () { openSheet(s.id); });
      li.appendChild(b);
      els.list.appendChild(li);
    });
    els.empty.hidden = sheets.length > 0;
  }

  function confirmDiscard() {
    return !isDirty() || window.confirm('Discard unsaved changes?');
  }

  function openSheet(id) {
    if (sheet && sheet.id === id) return Promise.resolve();
    if (!confirmDiscard()) return Promise.resolve();
    return api('GET', '/api/v1/sheets/' + encodeURIComponent(id)).then(function (r) {
      if (!r.ok) {
        setStatus(errMsg(r), 'error');
        if (r.status === 404) { try { localStorage.removeItem(LAST_KEY); } catch (e) { /* ignore */ } }
        return;
      }
      applySheet(r.data);
      setStatus('Opened "' + r.data.title + '" at revision ' + r.data.revision);
    }).catch(function () { setStatus(NET_MSG, 'error'); });
  }

  function upsertList(s) {
    var found = false;
    sheets = sheets.map(function (x) {
      if (x.id === s.id) { found = true; return { id: s.id, title: s.title, revision: s.revision, updated_at: s.updated_at }; }
      return x;
    });
    if (!found) sheets.push({ id: s.id, title: s.title, revision: s.revision, updated_at: s.updated_at });
  }

  function payload(base) {
    var cells = {};
    Object.keys(local).forEach(function (k) { if (local[k] !== '') cells[k] = local[k]; });
    return { base_revision: base, title: els.title.value, cells: cells };
  }

  function doSave(base) {
    if (!sheet || busy) return Promise.resolve();
    busy = true;
    refreshAll();
    setStatus('Saving...');
    return api('PUT', '/api/v1/sheets/' + encodeURIComponent(sheet.id), payload(base)).then(function (r) {
      busy = false;
      if (r.ok) {
        upsertList(r.data);
        applySheet(r.data);
        setStatus('Saved revision ' + r.data.revision);
      } else if (r.status === 409 && r.data && r.data.current) {
        refreshAll();
        setStatus('Not saved: conflict with a newer revision.', 'error');
        showConflict(r.data.current);
      } else {
        refreshAll();
        setStatus(errMsg(r), 'error');
      }
    }).catch(function () {
      busy = false;
      refreshAll();
      setStatus(NET_MSG, 'error');
    });
  }

  function save() {
    if (!sheet) return;
    if (conflictSheet) {
      setStatus('Resolve the conflict first: load the server version or keep your edits and retry.', 'error');
      return;
    }
    doSave(sheet.revision);
  }

  function newSheet() {
    if (!confirmDiscard()) return;
    busy = true; refreshAll();
    api('POST', '/api/v1/sheets', { title: 'Untitled sheet' }).then(function (r) {
      busy = false;
      if (!r.ok) { refreshAll(); setStatus(errMsg(r), 'error'); return; }
      upsertList(r.data);
      applySheet(r.data);
      setStatus('Created "' + r.data.title + '"');
      inputs.A1.focus();
    }).catch(function () { busy = false; refreshAll(); setStatus(NET_MSG, 'error'); });
  }

  function loadSample() {
    if (!sheet) return;
    local.A1 = '3'; local.B1 = '4'; local.C1 = '=A1+B1';
    ['A1', 'B1', 'C1'].forEach(function (id) { inputs[id].value = local[id]; });
    markEdited();
    inputs.A1.focus();
  }

  // ---- grid ----
  function buildGrid() {
    var thead = els.grid.tHead;
    var hr = thead.insertRow();
    var corner = document.createElement('th');
    corner.scope = 'col';
    corner.textContent = '#';
    hr.appendChild(corner);
    COLS.forEach(function (l) {
      var th = document.createElement('th');
      th.scope = 'col';
      th.textContent = l;
      hr.appendChild(th);
    });
    var body = els.grid.tBodies[0];
    for (var r = 0; r < ROWS; r++) {
      var tr = body.insertRow();
      var rh = document.createElement('th');
      rh.scope = 'row';
      rh.textContent = String(r + 1);
      tr.appendChild(rh);
      for (var c = 0; c < COLS.length; c++) {
        var id = cellId(c, r);
        var td = tr.insertCell();
        var inp = document.createElement('input');
        inp.type = 'text';
        inp.maxLength = 200;
        inp.autocomplete = 'off';
        inp.spellcheck = false;
        inp.id = 'cell-' + id;
        inp.setAttribute('data-cell', id);
        inp.setAttribute('aria-label', id);
        var out = document.createElement('output');
        out.id = 'out-' + id;
        out.setAttribute('aria-label', id + ' result');
        td.appendChild(inp);
        td.appendChild(out);
        inputs[id] = inp;
        outputs[id] = out;
        inp.addEventListener('input', onCellInput);
        inp.addEventListener('keydown', onCellKey);
      }
    }
  }

  function onCellInput(e) {
    var id = e.target.getAttribute('data-cell');
    local[id] = e.target.value;
    markEdited();
  }

  function focusCell(c, r) {
    if (c < 0 || c >= COLS.length || r < 0 || r >= ROWS) return;
    var inp = inputs[cellId(c, r)];
    inp.focus();
    inp.select();
  }

  function onCellKey(e) {
    var id = e.target.getAttribute('data-cell');
    var c = COLS.indexOf(id.charAt(0));
    var r = parseInt(id.slice(1), 10) - 1;
    var t = e.target;
    if (e.isComposing) return;
    if (e.key === 'ArrowDown' || e.key === 'Enter') { e.preventDefault(); focusCell(c, r + 1); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); focusCell(c, r - 1); }
    else if (e.key === 'ArrowLeft' && t.selectionStart === 0 && t.selectionEnd === 0 && c > 0) {
      e.preventDefault(); focusCell(c - 1, r);
    } else if (e.key === 'ArrowRight' && t.selectionStart === t.value.length &&
               t.selectionEnd === t.value.length && c < COLS.length - 1) {
      e.preventDefault(); focusCell(c + 1, r);
    }
  }

  // ---- wiring ----
  els.save.addEventListener('click', save);
  els.neu.addEventListener('click', newSheet);
  els.sample.addEventListener('click', loadSample);
  els.title.addEventListener('input', markEdited);
  els.reload.addEventListener('click', function () {
    if (!conflictSheet) return;
    var cur = conflictSheet;
    upsertList(cur);
    applySheet(cur);
    setStatus('Loaded server revision ' + cur.revision);
  });
  els.retry.addEventListener('click', function () {
    if (!conflictSheet) return;
    var base = conflictSheet.revision;
    hideConflict();
    doSave(base);
  });
  document.addEventListener('keydown', function (e) {
    if ((e.ctrlKey || e.metaKey) && !e.altKey && (e.key === 's' || e.key === 'S')) {
      e.preventDefault();
      save();
    }
  });
  window.addEventListener('beforeunload', function (e) {
    if (isDirty()) { e.preventDefault(); e.returnValue = ''; }
  });

  // ---- startup ----
  buildGrid();
  refreshAll();
  loadList().then(function () {
    if (!sheets.length) { setStatus('No sheets yet. Choose "New sheet" to start.'); return; }
    var last = null;
    try { last = parseInt(localStorage.getItem(LAST_KEY), 10); } catch (e) { /* ignore */ }
    var pick = sheets[0].id;
    sheets.forEach(function (s) { if (s.id === last) pick = last; });
    return openSheet(pick);
  }).catch(function () { setStatus(NET_MSG, 'error'); });
}());
