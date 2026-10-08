/* Editable meal item list for photo results.
   RCMealEditor.mount(container, data, opts)
     data: API result from /api/food-scan/meal ({items, people, photo_key, ...})
           or a saved diary entry ({items, meal_split, save_id, id})
     opts: { loggedIn, onSaved(resp, meal), track(name, params) }
   Depends on RCMealLogic (meal_logic.js). Mobile-first, no framework. */
(function () {
  'use strict';
  var L = window.RCMealLogic;

  function esc(t) {
    return String(t == null ? '' : t).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  function r0(v) { var n = Number(v); return isFinite(n) ? Math.round(n) : 0; }
  function g(v) { var n = Number(v); if (!isFinite(n)) return '0'; return n >= 10 ? String(Math.round(n)) : String(Math.round(n * 10) / 10); }
  function sizeLabel(s) {
    var map = { 0.25: '\u00bc\u00d7', 0.5: '\u00bd\u00d7', 0.75: '\u00be\u00d7', 1.5: '1\u00bd\u00d7', 2.5: '2\u00bd\u00d7' };
    return map[s] || (g(s) + '\u00d7');
  }
  function newId() { return 'n' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6); }
  function postJSON(url, body, timeoutMs) {
    var opts = { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), credentials: 'same-origin' };
    var timer;
    if (timeoutMs && typeof AbortController === 'function') {
      var ctrl = new AbortController(); opts.signal = ctrl.signal;
      timer = setTimeout(function () { ctrl.abort(); }, timeoutMs);
    }
    return fetch(url, opts).then(function (res) {
      if (timer) clearTimeout(timer);
      return res.json().catch(function () { return { ok: false, error: 'No result returned.' }; });
    }).catch(function () {
      if (timer) clearTimeout(timer);
      return { ok: false, error: 'The request did not finish. Check your connection and try again.' };
    });
  }
  var GUEST_KEY = 'rc_guest_meals';
  function guestMeals() {
    try { var v = JSON.parse(window.localStorage.getItem(GUEST_KEY) || '[]'); return Array.isArray(v) ? v : []; } catch (e) { return []; }
  }
  function saveGuestMeal(meal) {
    var rows = guestMeals();
    var replaced = false;
    var today = new Date().toISOString().slice(0, 10);
    rows = rows.filter(function (r) {
      var same = (meal.save_id && r.save_id === meal.save_id) || (meal.photo_key && r.photo_key === meal.photo_key && r.day === today);
      if (same) { replaced = true; meal.id = r.id; meal.eaten_at = r.eaten_at; }
      return !same;
    });
    meal.id = meal.id || newId();
    meal.day = today;
    meal.eaten_at = meal.eaten_at || new Date().toLocaleString();
    rows.unshift(meal);
    try { window.localStorage.setItem(GUEST_KEY, JSON.stringify(rows.slice(0, 60))); } catch (e) {}
    return replaced;
  }

  function mount(container, data, opts) {
    opts = opts || {};
    var track = opts.track || function () {};
    var state = {
      items: ((data && data.items) || []).map(function (it) {
        var c = JSON.parse(JSON.stringify(it));
        c.id = c.id || newId();
        if (c.size == null) c.size = 1;
        if (c.share == null) c.share = 1;
        if (c.eaten == null) c.eaten = true;
        return c;
      }),
      split: Number((data && data.meal_split) || 1) || 1,
      people: Number((data && data.people) || 1) || 1,
      sharedTable: !!(data && data.shared_table),
      photoKey: (data && data.photo_key) || '',
      saveId: (data && data.save_id) || ('m' + Date.now().toString(36) + Math.random().toString(36).slice(2, 8)),
      entryId: (data && data.entry_id) || '',
      saving: false,
      saved: !!(data && data.entry_id),
      dirty: false,
      notes: (data && data.macros && data.macros.notes) || ''
    };
    var lastTrack = {};
    function t(name, params) {
      var k = name + ':' + (params && params.action);
      var now = Date.now();
      if (lastTrack[k] && now - lastTrack[k] < 1500) return;
      lastTrack[k] = now;
      track(name, params || {});
    }
    function find(id) { for (var i = 0; i < state.items.length; i++) if (state.items[i].id === id) return state.items[i]; return null; }

    function shareControls(item) {
      var key = L.shareKey(item, state.split);
      var btns = L.SHARE_PRESETS.map(function (p) {
        return '<button type="button" data-act="share" data-v="' + p.value + '" aria-pressed="' + (key === p.key) + '" aria-label="' + (p.key === 'all' ? 'I had all of it' : 'I had ' + p.key) + '">' + p.label + '</button>';
      }).join('');
      btns += '<button type="button" data-act="custom" aria-pressed="' + (key === 'custom') + '" aria-label="Custom percent">' + (key === 'custom' ? Math.round(L.effectiveShare(item, state.split) * 100) + '%' : '%') + '</button>';
      return '<div class="mi-seg" role="group" aria-label="How much of ' + esc(item.name) + ' I had">' + btns + '</div>' +
        (item._custom ? '<div class="mi-custom"><label>My share in percent <input type="number" inputmode="numeric" min="5" max="100" step="5" data-act="pct" value="' + Math.round(L.effectiveShare(item, state.split) * 100) + '"></label> <button type="button" class="btn btn-outline" data-act="pct-ok">OK</button></div>' : '');
    }
    function editPanel(item) {
      return '<div class="mi-edit">' +
        '<label class="mi-lbl" for="q-' + esc(item.id) + '">What is it?</label>' +
        '<input type="search" id="q-' + esc(item.id) + '" class="mi-q" data-act="q" autocomplete="off" autocorrect="off" enterkeyhint="search" placeholder="e.g. salsa, baked potato" value="' + esc(item._new ? '' : item.name) + '">' +
        '<div class="mi-sugg" role="listbox" aria-label="Suggestions"></div>' +
        '<label class="mi-lbl" for="k-' + esc(item.id) + '">Calories for this portion <span class="hint">(optional)</span></label>' +
        '<input type="number" inputmode="numeric" min="0" id="k-' + esc(item.id) + '" class="mi-kcal" data-act="kcal" placeholder="' + (item.base && item.base.calories != null ? r0(item.base.calories) : '') + '">' +
        '<div class="mi-edit-actions">' +
          '<button type="button" class="btn btn-primary" data-act="apply">' + (item._new ? 'Add' : 'Update') + '</button>' +
          '<button type="button" class="btn btn-outline" data-act="cancel">Cancel</button>' +
          (item._new ? '' : '<button type="button" class="btn btn-outline mi-del" data-act="remove">Delete item</button>') +
        '</div><p class="mi-edit-msg hint" aria-live="polite"></p></div>';
    }
    function rowHtml(item) {
      var n = L.itemNutrition(item, state.split);
      var off = item.eaten === false;
      var tags = [];
      if (item.portion) tags.push(esc(item.portion));
      if (item.shared_dish) tags.push('shared dish');
      if (item.partly_eaten) tags.push('partly eaten');
      var score = item.score != null ? '<span class="mi-score" style="background:' + esc(item.color || '#5c6b66') + '" title="' + esc(item.label || '') + '" aria-label="Score ' + esc(item.score) + ', ' + esc(item.label || '') + '">' + esc(item.score) + '</span>' : '';
      if (item._new) {
        return '<div class="mi-row mi-new" data-id="' + esc(item.id) + '"><p class="mi-new-title"><strong>Add a food</strong></p>' + editPanel(item) + '</div>';
      }
      return '<div class="mi-row' + (off ? ' off' : '') + '" data-id="' + esc(item.id) + '">' +
        '<div class="mi-top">' +
          '<label class="mi-check"><input type="checkbox" data-act="eat"' + (off ? '' : ' checked') + ' aria-label="I ate ' + esc(item.name) + '"><span aria-hidden="true">Ate</span></label>' +
          '<button type="button" class="mi-name" data-act="edit" aria-expanded="' + (!!item._editing) + '" aria-label="Fix or rename ' + esc(item.name) + '">' + esc(item.name) + ' <span class="mi-pen" aria-hidden="true">\u270e</span></button>' +
          score +
        '</div>' +
        (tags.length ? '<div class="mi-sub">' + tags.join(' \u00b7 ') + '</div>' : '') +
        (off ? '<div class="mi-sub">Not counted</div>' :
          '<div class="mi-ctrls">' + shareControls(item) +
          '<div class="mi-size" role="group" aria-label="Portion size of ' + esc(item.name) + '">' +
            '<button type="button" data-act="size" data-d="-1" aria-label="Smaller portion">\u2212</button>' +
            '<span aria-live="polite">' + sizeLabel(Number(item.size) || 1) + ' size</span>' +
            '<button type="button" data-act="size" data-d="1" aria-label="Bigger portion">+</button></div></div>' +
          '<div class="mi-macros"><strong>' + r0(n.calories) + ' kcal</strong> \u00b7 P ' + g(n.protein) + ' g \u00b7 C ' + g(n.carbs) + ' g \u00b7 F ' + g(n.fat) + ' g</div>') +
        (item._editing ? editPanel(item) : '') +
      '</div>';
    }
    function splitHtml() {
      var opts2 = [1, 2, 3, 4];
      var btns = opts2.map(function (n) {
        return '<button type="button" data-act="split" data-n="' + n + '" aria-pressed="' + (state.split === n) + '">' + (n === 1 ? 'Just me' : n) + '</button>';
      }).join('');
      var more = state.split > 4;
      btns += '<button type="button" data-act="split-more" aria-pressed="' + more + '">' + (more ? state.split : '5+') + '</button>';
      return '<div class="mi-split"><span class="mi-lbl" id="split-lbl">Shared meal? Split everything with</span>' +
        '<div class="mi-seg" role="group" aria-labelledby="split-lbl">' + btns + '</div></div>';
    }
    function totalsHtml() {
      var tt = L.computeTotals(state.items, state.split);
      var b = L.band(tt.score);
      var btnText = state.saving ? 'Saving\u2026' : (state.saved && !state.dirty ? 'Saved \u2713' : (state.saved ? 'Update meal' : 'Save meal'));
      var total = state.items.filter(function (i) { return !i._new; }).length;
      return '<div class="mi-tot" aria-live="polite">' +
          '<div class="mi-tot-main"><strong>' + tt.calories + ' kcal</strong>' +
          (tt.score != null ? '<span class="mi-score" style="background:' + b.color + '" title="' + esc(b.label) + '" aria-label="Meal score ' + tt.score + ', ' + esc(b.label) + '">' + tt.score + '</span>' : '') +
          '<span class="hint">' + tt.items_eaten + ' of ' + total + ' foods</span></div>' +
          '<div class="mi-tot-mac">P ' + g(tt.protein) + ' g \u00b7 C ' + g(tt.carbs) + ' g \u00b7 F ' + g(tt.fat) + ' g \u00b7 Fiber ' + g(tt.fiber) + ' g</div>' +
        '</div>' +
        '<button type="button" class="btn btn-primary mi-save" data-act="save"' + ((state.saving || (state.saved && !state.dirty) || !tt.items_eaten) ? ' disabled' : '') + '>' + btnText + '</button>';
    }
    function render() {
      var intro = state.entryId ? 'Editing a saved meal. Changes update the same log entry.' :
        'Uncheck anything you didn\u2019t eat. Tap a name to fix it.';
      var banner = '';
      if (state.people > 1 && !state.entryId && !state.splitTouched) {
        banner = '<div class="mi-banner">Looks like a shared table for about ' + state.people + '. Shared dishes start at your ' +
          (state.people === 2 ? 'half' : '1/' + state.people) + '. <button type="button" class="mi-link" data-act="split" data-n="' + state.people + '">Split everything ' + state.people + ' ways</button></div>';
      }
      container.innerHTML = '<div class="card mi-card">' +
        '<h2 class="mi-h">' + (state.entryId ? 'Edit meal' : 'We found ' + state.items.filter(function (i) { return !i._new; }).length + ' foods') + '</h2>' +
        '<p class="hint">' + intro + '</p>' + banner + splitHtml() +
        '<div class="mi-list">' + state.items.map(rowHtml).join('') + '</div>' +
        '<p><button type="button" class="btn btn-outline mi-add" data-act="add">+ Add item</button></p>' +
        (state.notes ? '<p class="hint">' + esc(state.notes) + '</p>' : '') +
        '<p class="hint">Photo estimates are rough, educational guides. Portions are often uncertain. Not medical advice.</p>' +
        '<div class="mi-foot">' + totalsHtml() + '</div>' +
        '<p class="mi-msg" aria-live="polite"></p>' +
        '</div>';
    }
    function rerenderRow(id) {
      var el = container.querySelector('.mi-row[data-id="' + cssId(id) + '"]');
      var item = find(id);
      if (!el || !item) { render(); return; }
      var tmp = document.createElement('div');
      tmp.innerHTML = rowHtml(item);
      el.parentNode.replaceChild(tmp.firstChild, el);
      refreshTotals();
    }
    function cssId(id) { return String(id).replace(/["\\]/g, ''); }
    function refreshTotals() {
      var foot = container.querySelector('.mi-foot');
      if (foot) foot.innerHTML = totalsHtml();
      var h = container.querySelector('.mi-h');
      if (h && !state.entryId) h.textContent = 'We found ' + state.items.filter(function (i) { return !i._new; }).length + ' foods';
    }
    function changed() { state.dirty = true; }
    function msg(text, isErr) {
      var el = container.querySelector('.mi-msg');
      if (el) { el.textContent = text || ''; el.className = 'mi-msg' + (isErr ? ' err' : ''); }
    }
    function rowMsg(id, text) {
      var el = container.querySelector('.mi-row[data-id="' + cssId(id) + '"] .mi-edit-msg');
      if (el) el.textContent = text || '';
    }

    var suggTimer = null;
    function suggest(input) {
      var row = input.closest('.mi-row');
      var box = row && row.querySelector('.mi-sugg');
      if (!box) return;
      var q = input.value.trim();
      clearTimeout(suggTimer);
      if (q.length < 2) { box.innerHTML = ''; return; }
      suggTimer = setTimeout(function () {
        fetch('/api/food-scan/foods?q=' + encodeURIComponent(q), { credentials: 'same-origin' }).then(function (r) { return r.json(); }).then(function (d) {
          if (input.value.trim() !== q) return;
          var items = (d && d.items) || [];
          box.innerHTML = items.slice(0, 6).map(function (s) {
            return '<button type="button" role="option" class="mi-sug" data-act="pick" data-name="' + esc(s.name) + '">' + esc(s.name) +
              (s.calories != null ? ' <span class="hint">' + esc(s.portion) + ' \u00b7 ' + esc(s.calories) + ' kcal</span>' : '') + '</button>';
          }).join('');
        }).catch(function () { box.innerHTML = ''; });
      }, 180);
    }
    function scaleToKcal(item, kcal) {
      var k = Number(kcal);
      if (!isFinite(k) || k < 0) return;
      var base = item.base || (item.base = {});
      var cur = Number(base.calories);
      if (isFinite(cur) && cur > 0) {
        var f = k / cur;
        L.NUTRIENTS.forEach(function (n) { if (base[n] != null) base[n] = Math.round(Number(base[n]) * f * 10) / 10; });
      }
      base.calories = k;
      item.source = 'manual';
    }
    function applyEdit(id, nameOverride) {
      var item = find(id);
      if (!item) return;
      var row = container.querySelector('.mi-row[data-id="' + cssId(id) + '"]');
      var q = nameOverride || ((row && row.querySelector('.mi-q')) ? row.querySelector('.mi-q').value.trim() : '');
      var kcal = row && row.querySelector('.mi-kcal') ? row.querySelector('.mi-kcal').value.trim() : '';
      if (!q && item._new) { rowMsg(id, 'Type a food name.'); return; }
      var renamed = q && q.toLowerCase() !== String(item.name || '').toLowerCase();
      function finish(action) {
        item._editing = false; item._new = false;
        if (kcal !== '') scaleToKcal(item, kcal);
        changed();
        t('meal_item_edit', { action: action });
        rerenderRow(id);
      }
      if (!renamed) {
        if (kcal === '') { item._editing = false; rerenderRow(id); return; }
        finish('calories');
        return;
      }
      rowMsg(id, 'Looking up ' + q + '\u2026');
      var btn = row && row.querySelector('[data-act="apply"]');
      if (btn) btn.disabled = true;
      postJSON('/api/food-scan/meal/item', {
        name: q, id: item.id, eaten: true, size: 1,
        share: item.share, share_override: item.share_override
      }, 25000).then(function (res) {
        if (btn) btn.disabled = false;
        if (res && res.ok && res.item) {
          var keep = { id: item.id, eaten: true, share: item.share, share_override: item.share_override };
          var wasNew = item._new;
          Object.keys(item).forEach(function (k) { delete item[k]; });
          Object.assign(item, res.item, keep);
          finish(wasNew ? 'add' : 'rename');
          return;
        }
        if (item._new && kcal === '') {
          rowMsg(id, (res && res.error) || 'Not found. Type the calories to add it anyway.');
          return;
        }
        item.name = q.slice(0, 60);
        item.source = 'manual';
        if (item._new) { item.base = {}; item.processing = 'processed'; item.score = null; item.size = 1; }
        finish(item._new ? 'add' : 'rename');
        msg('Renamed. No nutrition match for "' + q + '", so the numbers were kept' + (kcal !== '' ? ' (with your calories).' : '.'));
      });
    }

    container.addEventListener('click', function (e) {
      var el = e.target.closest ? e.target.closest('[data-act]') : null;
      if (!el || !container.contains(el)) return;
      var act = el.getAttribute('data-act');
      var rowEl = el.closest('.mi-row');
      var id = rowEl && rowEl.getAttribute('data-id');
      var item = id ? find(id) : null;
      if (act === 'eat') return; // handled on change
      if (act === 'share' && item) {
        L.setShare(item, Number(el.getAttribute('data-v'))); item._custom = false; changed();
        t('meal_item_edit', { action: 'share' }); rerenderRow(id);
      } else if (act === 'custom' && item) {
        item._custom = !item._custom; rerenderRow(id);
        var inp = container.querySelector('.mi-row[data-id="' + cssId(id) + '"] [data-act="pct"]');
        if (inp) inp.focus();
      } else if (act === 'pct-ok' && item) {
        var p = L.parsePercent((rowEl.querySelector('[data-act="pct"]') || {}).value);
        if (p) { L.setShare(item, p); changed(); t('meal_item_edit', { action: 'share' }); }
        item._custom = false; rerenderRow(id);
      } else if (act === 'size' && item) {
        L.stepSize(item, Number(el.getAttribute('data-d'))); changed();
        t('meal_item_edit', { action: 'size' }); rerenderRow(id);
      } else if (act === 'edit' && item) {
        item._editing = !item._editing; rerenderRow(id);
        if (item._editing) { var q = container.querySelector('.mi-row[data-id="' + cssId(id) + '"] .mi-q'); if (q) { q.focus(); q.select && q.select(); } }
      } else if (act === 'cancel' && item) {
        if (item._new) { state.items = state.items.filter(function (x) { return x.id !== id; }); render(); return; }
        item._editing = false; rerenderRow(id);
      } else if (act === 'remove' && item) {
        state.items = state.items.filter(function (x) { return x.id !== id; }); changed();
        t('meal_item_edit', { action: 'remove' }); render();
      } else if (act === 'pick' && item) {
        var nm = el.getAttribute('data-name');
        var qi = rowEl.querySelector('.mi-q'); if (qi) qi.value = nm;
        applyEdit(id, nm);
      } else if (act === 'apply' && item) {
        applyEdit(id);
      } else if (act === 'add') {
        if (state.items.some(function (x) { return x._new; })) return;
        var it = { id: newId(), name: '', base: {}, size: 1, share: 1, share_override: false, eaten: true, _new: true, _editing: true };
        state.items.push(it); render();
        var nq = container.querySelector('.mi-row[data-id="' + cssId(it.id) + '"] .mi-q'); if (nq) nq.focus();
      } else if (act === 'split') {
        state.split = L.applyMealSplit(state.items, Number(el.getAttribute('data-n'))); changed(); state.splitTouched = true;
        t('meal_item_edit', { action: 'meal_split' }); render();
      } else if (act === 'split-more') {
        var v = window.prompt('Split the meal with how many people?', String(Math.max(5, state.split)));
        var n = parseInt(v, 10);
        if (n > 0 && n <= 20) { state.split = L.applyMealSplit(state.items, n); changed(); state.splitTouched = true; render(); }
      } else if (act === 'save') {
        save();
      }
    });
    container.addEventListener('change', function (e) {
      var el = e.target;
      if (!el || el.getAttribute('data-act') !== 'eat') return;
      var id = el.closest('.mi-row').getAttribute('data-id');
      var item = find(id);
      if (!item) return;
      item.eaten = !!el.checked; changed();
      t('meal_item_edit', { action: el.checked ? 'check' : 'uncheck' });
      rerenderRow(id);
    });
    container.addEventListener('input', function (e) {
      if (e.target && e.target.getAttribute('data-act') === 'q') suggest(e.target);
    });
    container.addEventListener('keydown', function (e) {
      var a = e.target && e.target.getAttribute && e.target.getAttribute('data-act');
      if (e.key !== 'Enter') return;
      var rowEl = e.target.closest('.mi-row');
      if (!rowEl) return;
      if (a === 'q' || a === 'kcal') { e.preventDefault(); applyEdit(rowEl.getAttribute('data-id')); }
      if (a === 'pct') { e.preventDefault(); var b = rowEl.querySelector('[data-act="pct-ok"]'); if (b) b.click(); }
    });

    function payloadItems() {
      return state.items.filter(function (i) { return !i._new; }).map(function (i) {
        var o = {};
        Object.keys(i).forEach(function (k) { if (k.charAt(0) !== '_') o[k] = i[k]; });
        return o;
      });
    }
    function save() {
      if (state.saving) return; // double-tap guard
      var items = payloadItems();
      var tt = L.computeTotals(items, state.split);
      if (!tt.items_eaten) { msg('Check at least one food you ate.', true); return; }
      state.saving = true; refreshTotals(); msg('');
      postJSON('/api/food-scan/meal/save', {
        items: items, meal_split: state.split, save_id: state.saveId, photo_key: state.photoKey,
        entry_id: state.entryId, name: L.mealName(items)
      }, 30000).then(function (res) {
        state.saving = false;
        if (!res || !res.ok) { refreshTotals(); msg((res && res.error) || 'Could not save that meal.', true); return; }
        var replaced = !!res.replaced;
        if (res.guest) {
          var m = res.meal || {};
          m.save_id = state.saveId; m.photo_key = state.photoKey;
          replaced = saveGuestMeal(m);
        } else if (res.meal && res.meal.id) {
          state.entryId = res.meal.id;
        }
        state.saved = true; state.dirty = false;
        refreshTotals();
        var text;
        if (res.guest) {
          text = replaced ? 'Updated on this device (no duplicate added).' : 'Saved on this device.';
          var el = container.querySelector('.mi-msg');
          if (el) {
            el.className = 'mi-msg ok';
            el.innerHTML = esc(text) + ' <a href="/login">Log in</a> or <a href="/register">create a free account</a> to keep your history across devices.';
          }
        } else {
          text = replaced ? 'Updated in today\u2019s intake (no duplicate added).' : 'Saved to today\u2019s intake.';
          msg(text);
          var el2 = container.querySelector('.mi-msg'); if (el2) el2.className = 'mi-msg ok';
        }
        t('meal_save', { action: replaced ? 'update' : 'new', items: tt.items_eaten, kcal: tt.calories, guest: !!res.guest, meal_split: state.split });
        if (opts.onSaved) opts.onSaved(res);
      });
    }
    container.addEventListener('focusin', function (e) {
      if (e.target && /^(INPUT)$/.test(e.target.tagName) && e.target.type !== 'checkbox') {
        var card = container.querySelector('.mi-card'); if (card) card.classList.add('mi-typing');
      }
    });
    container.addEventListener('focusout', function () {
      setTimeout(function () {
        var a = document.activeElement;
        if (a && container.contains(a) && a.tagName === 'INPUT' && a.type !== 'checkbox') return;
        var card = container.querySelector('.mi-card'); if (card) card.classList.remove('mi-typing');
      }, 50);
    });
    try { document.body.classList.add('mi-open'); } catch (e) {}
    render();
    t('meal_photo_items', { action: 'shown', items: state.items.length });
    return { state: state, render: render, save: save };
  }
  window.RCMealEditor = { mount: mount, guestMeals: guestMeals, GUEST_KEY: GUEST_KEY };
})();
