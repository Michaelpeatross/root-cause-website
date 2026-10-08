/* Meal item math shared by the web page and (later) the mobile app.
   Mirrors meal_items.py: item_fraction / compute_totals. Pure functions, no DOM. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.RCMealLogic = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';
  var NUTRIENTS = ['calories', 'protein', 'carbs', 'fat', 'sugar', 'fiber', 'sodium_mg'];
  var SHARE_PRESETS = [
    { key: 'all', label: 'All', value: 1 },
    { key: '1/2', label: '\u00bd', value: 0.5 },
    { key: '1/3', label: '\u2153', value: 1 / 3 },
    { key: '1/4', label: '\u00bc', value: 0.25 }
  ];
  var BANDS = [
    [85, 'Whole food - excellent', '#0f6b3a'],
    [70, 'Good choice', '#1b7f4e'],
    [40, 'Okay in moderation', '#c9a227'],
    [20, 'Ultra-processed - limit', '#d35400'],
    [0, 'Better to skip', '#b03a2e']
  ];
  function num(v, d) {
    if (v === null || v === undefined || v === '') return d;
    var n = Number(v);
    return isFinite(n) ? n : d;
  }
  function clamp(v, lo, hi) { return Math.min(hi, Math.max(lo, v)); }
  /* Share that applies to this item: its own override, else the meal split. */
  function effectiveShare(item, mealSplit) {
    var split = Math.round(num(mealSplit, 1)) || 1;
    var share;
    if (item && item.share_override) share = num(item.share, 1);
    else share = split > 1 ? 1 / split : num(item && item.share, 1);
    return clamp(share, 0, 1);
  }
  function itemFraction(item, mealSplit) {
    if (!item || item.eaten === false) return 0;
    var size = num(item.size, 1) || 1;
    return size * effectiveShare(item, mealSplit);
  }
  function itemNutrition(item, mealSplit) {
    var f = itemFraction(item, mealSplit);
    var base = (item && item.base) || {};
    var out = {};
    NUTRIENTS.forEach(function (k) { out[k] = num(base[k], 0) * f; });
    return out;
  }
  function round1(v) { return Math.round(v * 10) / 10; }
  function computeTotals(items, mealSplit) {
    var t = {}; NUTRIENTS.forEach(function (k) { t[k] = 0; });
    var weighted = 0, weight = 0, eaten = 0;
    (items || []).forEach(function (item) {
      var f = itemFraction(item, mealSplit);
      if (f <= 0) return;
      eaten += 1;
      var base = item.base || {};
      NUTRIENTS.forEach(function (k) { t[k] += num(base[k], 0) * f; });
      var s = num(item.score, null);
      if (s !== null) {
        var w = (num(base.calories, 0) * f) || 1;
        weighted += s * w; weight += w;
      }
    });
    var out = {};
    NUTRIENTS.forEach(function (k) {
      out[k] = (k === 'calories' || k === 'sodium_mg') ? Math.round(t[k]) : round1(t[k]);
    });
    out.items_eaten = eaten;
    out.score = weight ? Math.round(weighted / weight) : null;
    return out;
  }
  function band(score) {
    if (score === null || score === undefined) return { label: '', color: '#5c6b66' };
    for (var i = 0; i < BANDS.length; i++) {
      if (score >= BANDS[i][0]) return { label: BANDS[i][1], color: BANDS[i][2] };
    }
    return { label: BANDS[BANDS.length - 1][1], color: BANDS[BANDS.length - 1][2] };
  }
  /* "50" or "50%" -> 0.5 ; clamps to 5..100 % */
  function parsePercent(text) {
    var n = parseFloat(String(text == null ? '' : text).replace('%', ''));
    if (!isFinite(n) || n <= 0) return null;
    return clamp(n, 5, 100) / 100;
  }
  function shareKey(item, mealSplit) {
    var s = effectiveShare(item, mealSplit);
    for (var i = 0; i < SHARE_PRESETS.length; i++) {
      if (Math.abs(SHARE_PRESETS[i].value - s) < 0.002) return SHARE_PRESETS[i].key;
    }
    return 'custom';
  }
  function setShare(item, value) {
    item.share = clamp(num(value, 1), 0.05, 1);
    item.share_override = true;
    return item;
  }
  function applyMealSplit(items, split) {
    (items || []).forEach(function (item) { item.share_override = false; item.share = 1; });
    return Math.max(1, Math.round(num(split, 1)));
  }
  function stepSize(item, dir) {
    var steps = [0.25, 0.5, 0.75, 1, 1.25, 1.5, 2, 2.5, 3, 4];
    var cur = num(item.size, 1);
    var idx = 0, best = Infinity;
    steps.forEach(function (s, i) { var d = Math.abs(s - cur); if (d < best) { best = d; idx = i; } });
    idx = clamp(idx + (dir > 0 ? 1 : -1), 0, steps.length - 1);
    item.size = steps[idx];
    return item.size;
  }
  function mealName(items) {
    var names = (items || []).filter(function (i) { return i.eaten !== false && i.name; }).map(function (i) { return i.name; });
    if (!names.length) return 'Meal';
    if (names.length <= 3) return names.join(', ').slice(0, 80);
    return (names.slice(0, 2).join(', ') + ' +' + (names.length - 2) + ' more').slice(0, 80);
  }
  return {
    NUTRIENTS: NUTRIENTS, SHARE_PRESETS: SHARE_PRESETS,
    effectiveShare: effectiveShare, itemFraction: itemFraction, itemNutrition: itemNutrition,
    computeTotals: computeTotals, band: band, parsePercent: parsePercent, shareKey: shareKey,
    setShare: setShare, applyMealSplit: applyMealSplit, stepSize: stepSize, mealName: mealName
  };
});
