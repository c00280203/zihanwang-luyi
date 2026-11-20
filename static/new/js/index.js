/* Student home page: course selection, keyword/coarse search, AI semantic search and summaries. */
(function () {
  const courseSelect = document.getElementById("course");
  const keywordInput = document.getElementById("keyword");
  const resultsArea = document.getElementById("results");
  const statusEl = document.getElementById("status");
  const thinkingEl = document.getElementById("thinking");
  const aiAnswerPanel = document.getElementById("aiAnswer");
  const aiAnswerText = document.getElementById("aiAnswerText");
  const aiBadge = aiAnswerPanel ? aiAnswerPanel.querySelector(".badge.ai") : null;
  const summaryPanel = document.getElementById("summaryPanel");
  const libraryEl = document.getElementById("library");
  const libraryCount = document.getElementById("libraryCount");

  let courses = [];
  let requestId = 0;

  function spinner(text, subKey) {
    const wrap = document.createElement("div");
    wrap.className = "thinking-flow";

    const card = document.createElement("div");
    card.className = "thinking-flow-card";

    const spark = document.createElement("span");
    spark.className = "flow-spark";
    spark.setAttribute("aria-hidden", "true");
    spark.innerHTML = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2.5l1.6 6.1 6.1 1.6-6.1 1.6-1.6 6.1-1.6-6.1-6.1-1.6 6.1-1.6z"/><path d="M19 15l.8 2.8 2.8.8-2.8.8-.8 2.8-.8-2.8-2.8-.8 2.8-.8z"/></svg>';
    card.appendChild(spark);

    const body = document.createElement("div");
    body.className = "flow-copy";
    const title = document.createElement("span");
    title.className = "flow-title";
    title.textContent = I18n.t("thinkingStage");
    const sub = document.createElement("span");
    sub.className = "flow-sub";
    sub.textContent = I18n.t(subKey || "thinkingSub");
    body.appendChild(title);
    body.appendChild(sub);
    card.appendChild(body);

    const prompt = document.createElement("span");
    prompt.className = "flow-prompt";
    prompt.textContent = text;
    card.appendChild(prompt);

    wrap.appendChild(card);
    return wrap;
  }

  function courseLabel(code) {
    const found = courses.find(function (c) { return c.course_code === code; });
    return found ? found.title || found.course_code : code;
  }

  function resetOutput() {
    resultsArea.innerHTML = "";
    if (aiAnswerPanel) aiAnswerPanel.classList.add("hidden");
    if (thinkingEl) {
      thinkingEl.innerHTML = "";
      thinkingEl.classList.add("hidden");
    }
    statusEl.classList.add("hidden");
    summaryPanel.classList.add("hidden");
  }

  function showThinking(text, subKey) {
    if (!thinkingEl) return;
    thinkingEl.innerHTML = "";
    thinkingEl.appendChild(spinner(text, subKey));
    thinkingEl.classList.remove("hidden");
  }

  async function loadCourses() {
    try {
      const res = await Common.api("/api/content/courses");
      if (!res.ok) throw new Error("Cannot load courses.");
      courses = await res.json();
      const allOpt = document.createElement("option");
      allOpt.value = "all";
      allOpt.textContent = I18n.t("allCoursesShort");
      courseSelect.appendChild(allOpt);
      courses.forEach(function (c) {
        const opt = document.createElement("option");
        opt.value = c.course_code;
        opt.textContent = c.course_code.split("-")[0] + " · " + (c.title || "");
        courseSelect.appendChild(opt);
      });
      // All courses is the default so a term from another course is never hidden.
      courseSelect.value = "all";
      await Promise.all([search(), loadLibrary()]);
    } catch (e) {
      Common.showStatus(statusEl, e.message, "error");
    }
  }

  function queryParams() {
    return new URLSearchParams({
      course: courseSelect.value || "all",
      q: keywordInput.value.trim()
    });
  }

  async function search() {
    const id = ++requestId;
    resetOutput();
    Common.showStatus(statusEl, I18n.t("search") + "…", null);
    if (window.Sound) Sound.play("click");

    const params = queryParams();
    try {
      const res = await Common.api("/api/search/?" + params);
      const data = await res.json();
      if (id !== requestId) return;
      if (!res.ok) throw new Error(data.error || "Search failed.");

      if (!data.count) {
        Common.showStatus(statusEl, I18n.t("noResults"), null);
        return;
      }
      statusEl.classList.add("hidden");
      data.results.forEach(function (point) { renderPoint(point, false); });
      if (window.Sound) Sound.play("pop");
    } catch (e) {
      if (id !== requestId) return;
      Common.showStatus(statusEl, e.message, "error");
      if (window.Sound) Sound.play("error");
    }
  }

  async function aiSearch() {
    const question = keywordInput.value.trim();
    if (!question) {
      Common.showStatus(statusEl, I18n.t("askFirst"), null);
      keywordInput.focus();
      return;
    }

    const id = ++requestId;
    resetOutput();
    showThinking(question, "aiThinkingSub");
    if (window.Sound) Sound.play("click");

    const params = queryParams();
    params.set("lang", I18n.currentLang());
    try {
      const res = await Common.api("/api/search/ai?" + params);
      const data = await res.json();
      if (id !== requestId) return;
      if (!res.ok) throw new Error(data.error || "AI search failed.");

      thinkingEl.classList.add("hidden");
      aiAnswerPanel.classList.remove("hidden");
      if (data.mode === "keyword") {
        aiAnswerText.textContent = I18n.t("aiNotice");
        if (aiBadge) aiBadge.textContent = I18n.t("keywordFallback");
      } else {
        const answer = data.answer || (data.count ? "" : I18n.t("aiEmpty"));
        aiAnswerText.innerHTML = Common.markdown(answer);
        if (aiBadge) aiBadge.textContent = I18n.t("aiBadge");
      }
      if (!aiAnswerText.textContent) aiAnswerPanel.classList.add("hidden");

      if (!data.count) {
        Common.showStatus(statusEl, I18n.t("noResults"), null);
        return;
      }
      statusEl.classList.add("hidden");
      data.results.forEach(function (point) { renderPoint(point, true); });
      if (window.Sound) Sound.play("pop");
    } catch (e) {
      if (id !== requestId) return;
      thinkingEl.classList.add("hidden");
      Common.showStatus(statusEl, e.message, "error");
      if (window.Sound) Sound.play("error");
    }
  }

  function courseName(code) {
    const found = courses.find(function (c) { return c.course_code === code; });
    if (!found) return code;
    // Drop the semester prefix so the readable course name stays short.
    return (found.title || found.course_code).split(" - ").pop().trim();
  }

  async function loadLibrary() {
    const scope = courseSelect.value || "all";
    const params = new URLSearchParams();
    if (scope !== "all") params.set("course", scope);
    try {
      const res = await Common.api("/api/content/resources?" + params);
      if (!res.ok) throw new Error("Cannot load courseware.");
      const items = await res.json();
      libraryEl.innerHTML = "";
      items.forEach(renderResource);
      libraryCount.textContent = I18n.t("filesFound") + ": " + items.length;
      if (!items.length) {
        const empty = document.createElement("p");
        empty.className = "muted";
        empty.textContent = I18n.t("noLibrary");
        libraryEl.appendChild(empty);
      }
    } catch (e) {
      libraryCount.textContent = e.message;
    }
  }

  function renderResource(r) {
    const card = document.createElement("article");
    card.className = "resource-card fade-up";

    const head = document.createElement("div");
    head.className = "resource-head";
    const type = document.createElement("span");
    type.className = "file-type " + (r.file_type === "pdf" ? "pdf" : "ppt");
    type.textContent = r.file_type === "pdf" ? "PDF" : "PPT";
    head.appendChild(type);
    // When a single course is selected, every card belongs to it, so the
    // course badge is redundant. Show it only in the all-courses view.
    if (courseSelect.value === "all") {
      const course = document.createElement("span");
      course.className = "badge course-pill";
      course.textContent = (r.course_code || "").split("-")[0];
      course.title = r.course_code;
      head.appendChild(course);
    }
    card.appendChild(head);

    const title = document.createElement("h3");
    title.className = "resource-title";
    title.textContent = r.title;
    title.title = r.title;
    card.appendChild(title);

    const meta = document.createElement("p");
    meta.className = "muted resource-meta";
    const singleCourse = courseSelect.value !== "all";
    meta.textContent = (singleCourse ? "" : courseName(r.course_code) + " · ") +
      r.total_pages + " " + I18n.t(r.file_type === "pdf" ? "pages" : "slides");
    if (!singleCourse) meta.title = r.course_code;
    card.appendChild(meta);

    const actions = document.createElement("div");
    actions.className = "row resource-actions";
    const open = document.createElement("a");
    open.className = "btn small";
    open.href = r.file_url + (r.file_type === "pdf" ? "#page=1" : "");
    open.target = "_blank";
    open.rel = "noopener noreferrer";
    open.textContent = r.file_type === "pdf" ? I18n.t("openPdf") : I18n.t("openPpt");
    open.addEventListener("click", function () { if (window.Sound) Sound.play("click"); });
    actions.appendChild(open);

    const aiBtn = document.createElement("button");
    aiBtn.className = "btn ghost small";
    aiBtn.type = "button";
    aiBtn.textContent = I18n.t("summarize");
    aiBtn.addEventListener("click", function () { summarize(r.resource_id, r.title); });
    actions.appendChild(aiBtn);
    card.appendChild(actions);
    libraryEl.appendChild(card);
  }

  function renderPoint(point, aiMode) {
    const card = document.createElement("article");
    card.className = "card fade-up";

    const head = document.createElement("div");
    head.className = "result-head";
    const title = document.createElement("h3");
    title.textContent = point.name;
    head.appendChild(title);

    const courseBadge = document.createElement("span");
    courseBadge.className = "badge course-pill";
    courseBadge.textContent = (point.course_code || "").split("-")[0];
    courseBadge.title = point.course_code || courseLabel(point.course_code);
    head.appendChild(courseBadge);

    if (aiMode && point.score) {
      const score = document.createElement("span");
      score.className = "badge ai";
      score.textContent = Math.round(point.score * 100) + "%";
      head.appendChild(score);
    }
    if (point.fuzzy) {
      const fuzzy = document.createElement("span");
      fuzzy.className = "badge fuzzy";
      fuzzy.textContent = I18n.t("fuzzyHint");
      head.appendChild(fuzzy);
    }
    card.appendChild(head);

    if (aiMode && point.reason) {
      const reason = document.createElement("div");
      reason.className = "result-reason";
      const label = document.createElement("strong");
      label.textContent = I18n.t("aiReason") + (I18n.currentLang() === "zh" ? "：" : ": ");
      reason.appendChild(label);
      reason.appendChild(document.createTextNode(point.reason));
      card.appendChild(reason);
    }

    if (point.description) {
      const p = document.createElement("p");
      p.className = "muted";
      p.textContent = point.description;
      card.appendChild(p);
    }

    if (!point.locations.length) {
      const p = document.createElement("p");
      p.className = "muted";
      p.textContent = I18n.t("noLocation");
      card.appendChild(p);
    }

    point.locations.forEach(function (loc) {
      const row = document.createElement("div");
      row.className = "location";

      const label = document.createElement("div");
      const pageWord = I18n.t("page");
      label.textContent = loc.resource_title + " — " +
        (I18n.currentLang() === "zh" ? pageWord + loc.page_number + " 页" : pageWord + " " + loc.page_number);
      row.appendChild(label);

      if (loc.note) {
        const note = document.createElement("div");
        note.className = "muted";
        note.textContent = loc.note;
        row.appendChild(note);
      }

      const actions = document.createElement("div");
      actions.className = "row";
      actions.style.marginTop = "8px";

      const openBtn = document.createElement("a");
      openBtn.className = "btn small";
      openBtn.href = loc.file_url + (loc.file_type === "pdf" ? "#page=" + loc.page_number : "");
      openBtn.target = "_blank";
      openBtn.rel = "noopener noreferrer";
      openBtn.textContent = loc.file_type === "pdf" ? I18n.t("openPdf") : I18n.t("openPpt");
      openBtn.addEventListener("click", function () { if (window.Sound) Sound.play("click"); });
      actions.appendChild(openBtn);

      const aiBtn = document.createElement("button");
      aiBtn.className = "btn ghost small";
      aiBtn.type = "button";
      aiBtn.textContent = I18n.t("summarize");
      aiBtn.addEventListener("click", function () {
        summarize(loc.resource_id, loc.resource_title);
      });
      actions.appendChild(aiBtn);

      row.appendChild(actions);
      card.appendChild(row);
    });

    resultsArea.appendChild(card);
  }

  async function summarize(resourceId, title) {
    summaryPanel.classList.remove("hidden");
    summaryPanel.innerHTML = "";
    const heading = document.createElement("h3");
    heading.className = "summary-heading";
    heading.textContent = I18n.t("summaryTitle") + " — " + title;
    summaryPanel.appendChild(heading);
    const body = document.createElement("div");
    body.className = "summary-box";
    body.appendChild(spinner(I18n.t("summarizing")));
    summaryPanel.appendChild(body);
    summaryPanel.scrollIntoView({ behavior: "smooth", block: "nearest" });
    if (window.Sound) Sound.play("click");

    try {
      const res = await Common.api("/api/ai/summary/" + resourceId, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ language: I18n.currentLang() })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "AI summary failed.");
      body.innerHTML = Common.markdown(data.summary);
      if (window.Sound) Sound.play("success");
    } catch (e) {
      body.textContent = e.message;
      if (window.Sound) Sound.play("error");
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    loadCourses();
    const aiBtn = document.getElementById("aiSearchBtn");
    if (aiBtn) aiBtn.addEventListener("click", aiSearch);
    document.getElementById("searchBtn").addEventListener("click", search);
    document.getElementById("browseBtn").addEventListener("click", function () {
      keywordInput.value = "";
      search();
    });
    keywordInput.addEventListener("keydown", function (e) {
      if (e.key === "Enter") { e.preventDefault(); aiSearch(); }
    });
    courseSelect.addEventListener("change", function () {
      search();
      loadLibrary();
    });
    window.addEventListener("languagechange", function () {
      const allOpt = courseSelect.querySelector('option[value="all"]');
      if (allOpt) allOpt.textContent = I18n.t("allCoursesShort");
      if (keywordInput.value.trim() === "") search();
      loadLibrary();
    });
  });
})();
