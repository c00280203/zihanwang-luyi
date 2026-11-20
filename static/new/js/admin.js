/* Administration page: account CRUD and drag-and-drop courseware upload. */
(function () {
  const statusEl = document.getElementById("status");
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("uploadFile");
  const fileList = document.getElementById("fileList");
  let pickedFiles = [];

  function notify(message, kind) {
    Common.showStatus(statusEl, message, kind);
  }

  function refreshFileList() {
    fileList.innerHTML = "";
    pickedFiles.forEach(function (file) {
      const line = document.createElement("div");
      line.textContent = "· " + file.name;
      fileList.appendChild(line);
    });
  }

  async function loadAccounts() {
    const res = await Common.api("/api/admin/accounts");
    if (!res.ok) return;
    const users = await res.json();
    fillTable("adminTable", users.filter(function (u) { return u.role === "admin"; }));
    fillTable("studentTable", users.filter(function (u) { return u.role === "student"; }));
  }

  function fillTable(tableId, users) {
    const tbody = document.querySelector("#" + tableId + " tbody");
    tbody.innerHTML = "";
    users.forEach(function (u) {
      const tr = document.createElement("tr");
      const emailTd = document.createElement("td");
      emailTd.textContent = u.email;
      tr.appendChild(emailTd);
      const actionTd = document.createElement("td");
      const del = document.createElement("button");
      del.className = "btn danger small";
      del.textContent = I18n.t("delete");
      del.addEventListener("click", function () { deleteAccount(u.id); });
      actionTd.appendChild(del);
      tr.appendChild(actionTd);
      tbody.appendChild(tr);
    });
  }

  async function deleteAccount(id) {
    if (!confirm("Delete this account?")) return;
    if (window.Sound) Sound.play("click");
    const res = await Common.api("/api/admin/accounts/" + id, { method: "DELETE" });
    const data = await res.json();
    if (!res.ok) {
      notify(data.error, "error");
      if (window.Sound) Sound.play("error");
      return;
    }
    notify("Account deleted.", "success");
    if (window.Sound) Sound.play("success");
    loadAccounts();
  }

  async function loadCourses() {
    const res = await Common.api("/api/content/courses");
    if (!res.ok) return;
    const courses = await res.json();
    const select = document.getElementById("uploadCourse");
    select.innerHTML = "";
    courses.forEach(function (c) {
      const opt = document.createElement("option");
      opt.value = c.course_code;
      opt.textContent = c.course_code;
      select.appendChild(opt);
    });
  }

  async function loadResources() {
    const res = await Common.api("/api/content/resources");
    if (!res.ok) return;
    const items = await res.json();
    const tbody = document.querySelector("#resourceTable tbody");
    tbody.innerHTML = "";
    items.forEach(function (r) {
      const tr = document.createElement("tr");
      [r.title, r.course_code, r.file_type.toUpperCase()].forEach(function (v) {
        const td = document.createElement("td");
        td.textContent = v;
        tr.appendChild(td);
      });
      const td = document.createElement("td");
      const del = document.createElement("button");
      del.className = "btn danger small";
      del.textContent = I18n.t("delete");
      del.addEventListener("click", function () { deleteResource(r.resource_id); });
      td.appendChild(del);
      tr.appendChild(td);
      tbody.appendChild(tr);
    });
  }

  async function deleteResource(id) {
    if (!confirm("Delete this courseware?")) return;
    const res = await Common.api("/api/content/resources/" + id, { method: "DELETE" });
    const data = await res.json();
    if (!res.ok) { notify(data.error, "error"); return; }
    notify("Courseware deleted.", "success");
    if (window.Sound) Sound.play("success");
    loadResources();
  }

  async function uploadFiles(files) {
    const course = document.getElementById("uploadCourse").value;
    const customTitle = document.getElementById("uploadTitle").value.trim();
    let ok = 0;
    for (const file of files) {
      if (!/\.(pdf|pptx)$/i.test(file.name)) {
        notify("Unsupported file: " + file.name, "error");
        continue;
      }
      const form = new FormData();
      form.append("course_code", course);
      form.append("title", customTitle || file.name.replace(/\.[^.]+$/, ""));
      form.append("file", file);
      notify(I18n.t("uploading") + ": " + file.name, null);
      try {
        const res = await Common.api("/api/content/upload", { method: "POST", body: form });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Upload failed.");
        ok++;
      } catch (e) {
        notify(e.message, "error");
        if (window.Sound) Sound.play("error");
      }
    }
    if (ok) {
      notify(ok + " file(s) uploaded.", "success");
      if (window.Sound) Sound.play("success");
      document.getElementById("uploadTitle").value = "";
      pickedFiles = [];
      fileInput.value = "";
      refreshFileList();
      loadResources();
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    loadAccounts();
    loadCourses();
    loadResources();

    document.getElementById("addAccountBtn").addEventListener("click", async function () {
      const body = {
        email: document.getElementById("newEmail").value.trim(),
        password: document.getElementById("newPassword").value,
        role: document.getElementById("newRole").value
      };
      if (window.Sound) Sound.play("click");
      const res = await Common.api("/api/admin/accounts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
      const data = await res.json();
      if (!res.ok) {
        notify(data.error, "error");
        if (window.Sound) Sound.play("error");
        return;
      }
      notify("Account created.", "success");
      if (window.Sound) Sound.play("success");
      document.getElementById("newEmail").value = "";
      document.getElementById("newPassword").value = "";
      loadAccounts();
    });

    fileInput.addEventListener("change", function () {
      pickedFiles = Array.from(fileInput.files || []);
      refreshFileList();
    });

    dropzone.addEventListener("click", function () { fileInput.click(); });
    dropzone.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fileInput.click(); }
    });
    ["dragenter", "dragover"].forEach(function (event) {
      dropzone.addEventListener(event, function (e) {
        e.preventDefault();
        dropzone.classList.add("dragging");
      });
    });
    ["dragleave", "drop"].forEach(function (event) {
      dropzone.addEventListener(event, function (e) {
        e.preventDefault();
        dropzone.classList.remove("dragging");
      });
    });
    dropzone.addEventListener("drop", function (e) {
      pickedFiles = Array.from(e.dataTransfer.files || []);
      refreshFileList();
    });

    document.getElementById("uploadForm").addEventListener("submit", async function (e) {
      e.preventDefault();
      if (!pickedFiles.length) {
        notify("Please choose at least one file.", "error");
        return;
      }
      await uploadFiles(pickedFiles);
    });
  });
})();
