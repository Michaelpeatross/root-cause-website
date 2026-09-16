(function () {
  const CATEGORY_LABELS = {
    wearable: "Wearable exports",
    labs: "Lab PDFs / blood work",
    clinical: "Clinical visit summaries",
    imaging: "Imaging report PDFs",
    meds: "Medication / supplement lists",
  };
  const ACCEPT = {
    wearable: [".zip", ".xml", ".csv", ".json", ".txt"],
    labs: [".pdf", ".txt"],
    clinical: [".pdf", ".txt", ".doc", ".docx", ".png", ".jpg", ".jpeg", ".webp"],
    imaging: [".pdf"],
    meds: [".pdf", ".txt", ".csv", ".doc", ".docx", ".png", ".jpg", ".jpeg", ".webp"],
  };
  const MAX = {
    wearable: 200 * 1024 * 1024,
    labs: 25 * 1024 * 1024,
    clinical: 25 * 1024 * 1024,
    imaging: 40 * 1024 * 1024,
    meds: 15 * 1024 * 1024,
  };
  const BLOCKED = [".exe", ".html", ".htm", ".js", ".php", ".sh", ".bat", ".cmd", ".dmg", ".app"];

  function fmtSize(n) {
    if (n < 1024) return n + " B";
    if (n < 1024 * 1024) return (n / 1024).toFixed(1) + " KB";
    return (n / (1024 * 1024)).toFixed(1) + " MB";
  }

  function extOf(name) {
    const i = name.lastIndexOf(".");
    return i >= 0 ? name.slice(i).toLowerCase() : "";
  }

  function validate(file, category) {
    const ext = extOf(file.name || "");
    if (BLOCKED.indexOf(ext) >= 0) return "This file type is not allowed.";
    const allowed = ACCEPT[category] || [];
    if (allowed.indexOf(ext) < 0) {
      return "Use " + allowed.join(", ") + " for " + (CATEGORY_LABELS[category] || category) + ".";
    }
    if (file.size <= 0) return "File is empty.";
    if (file.size > (MAX[category] || MAX.labs)) {
      return "File is too large for this category.";
    }
    return "";
  }

  const queue = [];
  let seq = 0;

  function listEl() {
    return document.getElementById("hr-file-list");
  }
  function emptyEl() {
    return document.getElementById("hr-file-empty");
  }

  function render() {
    const ul = listEl();
    if (!ul) return;
    ul.innerHTML = "";
    if (!queue.length) {
      if (emptyEl()) emptyEl().hidden = false;
      return;
    }
    if (emptyEl()) emptyEl().hidden = true;
    queue.forEach(function (item) {
      const li = document.createElement("li");
      li.className = "hr-file hr-file--" + item.status;
      li.setAttribute("data-id", String(item.id));
      const statusLabel =
        item.status === "ok"
          ? "Uploaded"
          : item.status === "error"
            ? "Error"
            : item.status === "uploading"
              ? "Uploading"
              : "Ready";
      li.innerHTML =
        '<div class="hr-file-main">' +
        '<span class="hr-chip">' +
        escapeHtml(CATEGORY_LABELS[item.category] || item.category) +
        "</span>" +
        '<span class="hr-name">' +
        escapeHtml(item.file.name) +
        "</span>" +
        '<span class="hr-size">' +
        fmtSize(item.file.size) +
        "</span>" +
        '<span class="hr-state" aria-live="polite">' +
        escapeHtml(item.error || statusLabel) +
        "</span></div>" +
        (item.status === "uploading"
          ? ""
          : '<button type="button" class="hr-remove" data-remove="' +
            item.id +
            '" aria-label="Remove ' +
            escapeHtml(item.file.name) +
            '">Remove</button>');
      ul.appendChild(li);
    });
  }

  function escapeHtml(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function addFiles(fileList, category) {
    Array.prototype.forEach.call(fileList || [], function (file) {
      const err = validate(file, category);
      queue.push({
        id: ++seq,
        category: category,
        file: file,
        status: err ? "error" : "ready",
        error: err,
      });
    });
    render();
  }

  function bindZone(zone) {
    const category = zone.getAttribute("data-category");
    const input = zone.querySelector('input[type="file"]');
    zone.addEventListener("dragover", function (e) {
      e.preventDefault();
      zone.classList.add("is-drag");
    });
    zone.addEventListener("dragleave", function () {
      zone.classList.remove("is-drag");
    });
    zone.addEventListener("drop", function (e) {
      e.preventDefault();
      zone.classList.remove("is-drag");
      addFiles(e.dataTransfer.files, category);
    });
    if (input) {
      input.addEventListener("change", function () {
        addFiles(input.files, category);
        input.value = "";
      });
    }
  }

  document.addEventListener("click", function (e) {
    const btn = e.target.closest("[data-remove]");
    if (!btn) return;
    const id = Number(btn.getAttribute("data-remove"));
    const idx = queue.findIndex(function (q) {
      return q.id === id;
    });
    if (idx >= 0) queue.splice(idx, 1);
    render();
  });

  async function uploadAll() {
    const status = document.getElementById("hr-status");
    const btn = document.getElementById("hr-submit");
    const ready = queue.filter(function (q) {
      return q.status === "ready";
    });
    if (!ready.length) {
      if (status) {
        status.hidden = false;
        status.textContent = "Add at least one valid file first.";
      }
      return;
    }
    if (btn) btn.disabled = true;
    let okCount = 0;
    for (let i = 0; i < ready.length; i++) {
      const item = ready[i];
      item.status = "uploading";
      render();
      const fd = new FormData();
      fd.append("category", item.category);
      fd.append("files", item.file, item.file.name);
      const dateEl = document.getElementById("hr-test-date");
      if (dateEl && dateEl.value) fd.append("test_date", dateEl.value);
      try {
        const res = await fetch("/api/client/upload_records", {
          method: "POST",
          body: fd,
          credentials: "same-origin",
        });
        const data = await res.json().catch(function () {
          return {};
        });
        if (res.status === 401) {
          item.status = "error";
          item.error = "Please log in.";
          if (data.login) window.location.href = "/login";
        } else if (res.ok && data.success) {
          item.status = "ok";
          item.error = "";
          okCount += 1;
        } else {
          item.status = "error";
          item.error = data.error || "Upload failed";
        }
      } catch (err) {
        item.status = "error";
        item.error = err.message || "Network error";
      }
      render();
    }
    if (status) {
      status.hidden = false;
      status.textContent = okCount
        ? "Saved " +
          okCount +
          " file(s) for wellness analysis. Open your dashboard and choose Request Updated Grok Analysis when you want them included with your scan."
        : "No files uploaded. Fix the errors in the list and try again.";
    }
    if (btn) btn.disabled = false;
  }

  function init() {
    document.querySelectorAll("[data-hr-zone]").forEach(bindZone);
    const form = document.getElementById("hr-upload-form");
    if (form) {
      form.addEventListener("submit", function (e) {
        e.preventDefault();
        uploadAll();
      });
    }
    render();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
