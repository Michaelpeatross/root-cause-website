(function () {
  'use strict';

  var config = window.GROK_ASSISTANT || {};
  var reportId = config.reportId;
  var terms = (config.terms || []).slice().sort(function (a, b) {
    return b.length - a.length;
  });

  if (!reportId) {
    return;
  }

  var SKIP_SELECTORS = 'a, button, input, textarea, select, script, style, .grok-assistant, .lab-links, .affiliate-note, .grok-term';
  var skipTags = { A: 1, BUTTON: 1, SCRIPT: 1, STYLE: 1, INPUT: 1, TEXTAREA: 1, SELECT: 1 };

  function escapeHtml(text) {
    return text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function shouldSkipNode(node) {
    if (!node || !node.parentElement) {
      return true;
    }
    var parent = node.parentElement;
    if (skipTags[parent.tagName]) {
      return true;
    }
    if (parent.classList && parent.classList.contains('grok-term')) {
      return true;
    }
    return !!parent.closest(SKIP_SELECTORS);
  }

  function mergeRanges(ranges) {
    if (!ranges.length) {
      return [];
    }
    ranges.sort(function (a, b) {
      return a.start - b.start || b.end - a.end;
    });
    var merged = [ranges[0]];
    for (var i = 1; i < ranges.length; i += 1) {
      var prev = merged[merged.length - 1];
      var cur = ranges[i];
      if (cur.start < prev.end) {
        if (cur.end > prev.end) {
          prev.end = cur.end;
        }
        if (cur.term.length > prev.term.length) {
          prev.term = cur.term;
        }
      } else {
        merged.push(cur);
      }
    }
    return merged;
  }

  function findTermRanges(text) {
    var lower = text.toLowerCase();
    var ranges = [];
    terms.forEach(function (term) {
      var tLower = term.toLowerCase();
      var idx = 0;
      while (idx < lower.length) {
        var found = lower.indexOf(tLower, idx);
        if (found === -1) {
          break;
        }
        ranges.push({
          start: found,
          end: found + term.length,
          term: text.slice(found, found + term.length),
        });
        idx = found + term.length;
      }
    });
    return mergeRanges(ranges);
  }

  function wrapTextNode(textNode) {
    if (shouldSkipNode(textNode)) {
      return;
    }
    var text = textNode.textContent;
    if (!text || !text.trim()) {
      return;
    }
    var ranges = findTermRanges(text);
    if (!ranges.length) {
      return;
    }

    var frag = document.createDocumentFragment();
    var cursor = 0;
    ranges.forEach(function (range) {
      if (range.start > cursor) {
        frag.appendChild(document.createTextNode(text.slice(cursor, range.start)));
      }
      var link = document.createElement('a');
      link.href = '#';
      link.className = 'grok-term';
      link.setAttribute('data-term', range.term);
      link.setAttribute('title', 'Ask Grok to explain');
      link.textContent = text.slice(range.start, range.end);
      frag.appendChild(link);
      cursor = range.end;
    });
    if (cursor < text.length) {
      frag.appendChild(document.createTextNode(text.slice(cursor)));
    }
    textNode.parentNode.replaceChild(frag, textNode);
  }

  function walkNode(node) {
    if (!node) {
      return;
    }
    if (node.nodeType === Node.TEXT_NODE) {
      wrapTextNode(node);
      return;
    }
    if (node.nodeType !== Node.ELEMENT_NODE) {
      return;
    }
    if (skipTags[node.tagName] || node.classList.contains('grok-assistant')) {
      return;
    }
    var children = Array.prototype.slice.call(node.childNodes);
    children.forEach(walkNode);
  }

  function linkTermsIn(root) {
    if (!root || !terms.length) {
      return;
    }
    walkNode(root);
    root.querySelectorAll('strong').forEach(function (el) {
      if (el.closest('a.grok-term') || el.closest(SKIP_SELECTORS)) {
        return;
      }
      var text = (el.textContent || '').trim();
      if (text.length < 3) {
        return;
      }
      var link = document.createElement('a');
      link.href = '#';
      link.className = 'grok-term grok-term-strong';
      link.setAttribute('data-term', text);
      link.setAttribute('title', 'Ask Grok to explain');
      link.textContent = text;
      el.textContent = '';
      el.appendChild(link);
    });
  }

  function setLoading(panel, loading) {
    panel.classList.toggle('is-loading', loading);
  }

  function showAnswer(panel, html, label) {
    // For controlled/loading strings we own (safe, already escaped where needed)
    panel.hidden = false;
    panel.innerHTML =
      '<div class="grok-response-label">' + escapeHtml(label || 'Grok') + '</div>' +
      '<div class="grok-response-body">' + html + '</div>';
    panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function renderSafeParagraphs(container, text) {
    container.innerHTML = '';
    var paras = (text || '').split(/\n{2,}/);
    paras.forEach(function (ptext) {
      var t = ptext.trim();
      if (!t) return;
      var p = document.createElement('p');
      p.textContent = t;
      container.appendChild(p);
    });
  }

  function showAnswerFromText(panel, text, label) {
    // Safe path: model/Grok content is *never* put through innerHTML
    panel.hidden = false;
    panel.innerHTML =
      '<div class="grok-response-label">' + escapeHtml(label || 'Grok') + '</div>';
    var body = document.createElement('div');
    body.className = 'grok-response-body';
    renderSafeParagraphs(body, text);
    panel.appendChild(body);

    // "Ask another" affordance (clears panel + focuses input for follow-ups)
    var clear = document.createElement('a');
    clear.href = '#';
    clear.className = 'grok-clear-link';
    clear.textContent = 'Ask another question';
    clear.style.cssText = 'display:inline-block;margin-top:0.5rem;font-size:0.8rem;color:#1a5276;text-decoration:underline;cursor:pointer;';
    clear.addEventListener('click', function (e) {
      e.preventDefault();
      panel.hidden = true;
      panel.innerHTML = '';
      // Robust focus the input belonging to this assistant
      var root = panel.closest ? panel.closest('.grok-assistant') : null;
      var formInput = root ? root.querySelector('.grok-ask-input') : null;
      if (formInput && formInput.focus) formInput.focus();
    });
    panel.appendChild(clear);

    panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function postGrok(payload) {
    return fetch('/api/grok/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(Object.assign({ report_id: reportId }, payload)),
    }).then(function (res) {
      return res.json().then(function (data) {
        if (!res.ok) {
          throw new Error((data && data.error) || 'Request failed');
        }
        return data;
      });
    });
  }

  function initAssistant(root) {
    var form = root.querySelector('.grok-ask-form');
    var input = root.querySelector('.grok-ask-input');
    var panel = root.querySelector('.grok-response-panel');
    if (!form || !input || !panel) {
      return;
    }

    form.addEventListener('submit', function (event) {
      event.preventDefault();
      var question = (input.value || '').trim();
      if (!question) {
        return;
      }
      setLoading(panel, true);
      showAnswer(panel, '<p class="grok-loading">Thinking…</p>', 'Grok');
      postGrok({ question: question })
        .then(function (data) {
          showAnswerFromText(panel, data.answer || data.answer_text || 'No response.', 'Grok');
        })
        .catch(function (err) {
          showAnswer(
            panel,
            '<p>' + escapeHtml(err.message || 'Could not reach Grok.') + '</p>',
            'Grok'
          );
        })
        .finally(function () {
          setLoading(panel, false);
        });
    });

    // Scoped to this assistant root (prevents accumulating global listeners if multiple inits)
    root.addEventListener('click', function (event) {
      var termLink = event.target.closest('.grok-term');
      if (!termLink) {
        return;
      }
      event.preventDefault();
      var term = termLink.getAttribute('data-term') || termLink.textContent.trim();
      if (!term) {
        return;
      }
      input.value = 'What does "' + term + '" mean in my analysis?';
      setLoading(panel, true);
      showAnswer(panel, '<p class="grok-loading">Explaining <strong>' + escapeHtml(term) + '</strong>…</p>', 'Grok');
      postGrok({ term: term })
        .then(function (data) {
          showAnswerFromText(panel, data.answer || data.answer_text || 'No response.', 'About: ' + term);
        })
        .catch(function (err) {
          showAnswer(
            panel,
            '<p>' + escapeHtml(err.message || 'Could not reach Grok.') + '</p>',
            'About: ' + term
          );
        })
        .finally(function () {
          setLoading(panel, false);
        });
    });
  }

  function runHighlightAndInit() {
    document.querySelectorAll('.grok-analysis-content').forEach(linkTermsIn);
    document.querySelectorAll('.grok-assistant').forEach(initAssistant);
  }

  // Non-blocking to avoid jank on long report pages
  if (typeof requestIdleCallback === 'function') {
    requestIdleCallback(runHighlightAndInit, { timeout: 1200 });
  } else {
    setTimeout(runHighlightAndInit, 16);
  }
})();