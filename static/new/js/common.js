/* Shared UI behaviour: session state, logout and helpers. */
(function () {
  function api(path, options) {
    return fetch(path, Object.assign({ credentials: "same-origin" }, options || {}));
  }

  /* Lightweight Markdown renderer for AI-generated text. Content is escaped
     first, so model output can never inject HTML into the page. */
  function escapeHtml(text) {
    return text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function renderInline(text) {
    let t = escapeHtml(text);
    t = t.replace(/`([^`]+)`/g, "<code>$1</code>");
    t = t.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    t = t.replace(/(^|[^*])\*([^*]+)\*(?!\*)/g, "$1<em>$2</em>");
    t = t.replace(/~~([^~]+)~~/g, "<del>$1</del>");
    return t;
  }

  function markdown(text) {
    const lines = (text || "").replace(/\r/g, "").split("\n");
    const out = [];
    let listType = null;
    function closeList() {
      if (listType) {
        out.push(listType === "ul" ? "</ul>" : "</ol>");
        listType = null;
      }
    }
    lines.forEach(function (raw) {
      const line = raw.trim();
      if (!line) { closeList(); return; }
      let m;
      if ((m = line.match(/^(#{1,4})\s+(.*)$/))) {
        closeList();
        const level = m[1].length;
        out.push("<h" + level + ">" + renderInline(m[2]) + "</h" + level + ">");
      } else if ((m = line.match(/^[-*+]\s+(.*)$/))) {
        if (listType !== "ul") { closeList(); out.push("<ul>"); listType = "ul"; }
        out.push("<li>" + renderInline(m[1]) + "</li>");
      } else if ((m = line.match(/^\d+[.)]\s+(.*)$/))) {
        if (listType !== "ol") { closeList(); out.push("<ol>"); listType = "ol"; }
        out.push("<li>" + renderInline(m[1]) + "</li>");
      } else if ((m = line.match(/^>\s?(.*)$/))) {
        closeList();
        out.push("<blockquote>" + renderInline(m[1]) + "</blockquote>");
      } else if (/^(---+|\*\*\*+)$/.test(line)) {
        closeList();
        out.push("<hr>");
      } else {
        closeList();
        out.push("<p>" + renderInline(line) + "</p>");
      }
    });
    closeList();
    return out.join("");
  }

  async function refreshSession() {
    let user = null;
    try {
      const res = await api("/api/auth/me");
      if (res.ok) user = (await res.json()).user;
    } catch (e) { /* ignore */ }

    const loginNav = document.getElementById("loginNav");
    const registerNav = document.getElementById("registerNav");
    const logoutBtn = document.getElementById("logoutBtn");
    const adminNav = document.getElementById("adminNav");

    if (user) {
      if (loginNav) loginNav.classList.add("hidden");
      if (registerNav) registerNav.classList.add("hidden");
      if (logoutBtn) logoutBtn.classList.remove("hidden");
      if (adminNav) adminNav.classList.toggle("hidden", user.role !== "admin");
    } else {
      if (loginNav) loginNav.classList.remove("hidden");
      if (registerNav) registerNav.classList.remove("hidden");
      if (logoutBtn) logoutBtn.classList.add("hidden");
      if (adminNav) adminNav.classList.add("hidden");
    }
    return user;
  }

  function showStatus(el, message, kind) {
    if (!el) return;
    el.textContent = message || "";
    el.classList.remove("hidden", "error", "success");
    if (kind) el.classList.add(kind);
  }

  document.addEventListener("DOMContentLoaded", function () {
    refreshSession();
    const logoutBtn = document.getElementById("logoutBtn");
    if (logoutBtn) {
      logoutBtn.addEventListener("click", async function () {
        await api("/api/auth/logout", { method: "POST" });
        if (window.Sound) Sound.play("pop");
        location.href = "/";
      });
    }
  });

  window.Common = { api: api, refreshSession: refreshSession, showStatus: showStatus, markdown: markdown };
})();
