/* Login and registration page behaviour. */
(function () {
  document.addEventListener("DOMContentLoaded", function () {
    const loginForm = document.getElementById("loginForm");
    const registerForm = document.getElementById("registerForm");
    const statusEl = document.getElementById("status");

    if (loginForm) {
      loginForm.addEventListener("submit", async function (e) {
        e.preventDefault();
        if (window.Sound) Sound.play("click");
        const body = {
          email: document.getElementById("email").value.trim(),
          password: document.getElementById("password").value
        };
        try {
          const res = await Common.api("/api/auth/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body)
          });
          const data = await res.json();
          if (!res.ok) throw new Error(data.error || "Login failed.");
          Common.showStatus(statusEl, "OK", "success");
          if (window.Sound) Sound.play("success");
          location.href = "/";
        } catch (err) {
          Common.showStatus(statusEl, err.message, "error");
          if (window.Sound) Sound.play("error");
        }
      });
    }

    if (registerForm) {
      registerForm.addEventListener("submit", async function (e) {
        e.preventDefault();
        const password = document.getElementById("password").value;
        const confirm = document.getElementById("confirm").value;
        if (password !== confirm) {
          Common.showStatus(statusEl, "Passwords do not match.", "error");
          if (window.Sound) Sound.play("error");
          return;
        }
        if (window.Sound) Sound.play("click");
        const body = { email: document.getElementById("email").value.trim(), password: password };
        try {
          const res = await Common.api("/api/auth/register", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body)
          });
          const data = await res.json();
          if (!res.ok) throw new Error(data.error || "Registration failed.");
          if (window.Sound) Sound.play("success");
          location.href = "/";
        } catch (err) {
          Common.showStatus(statusEl, err.message, "error");
          if (window.Sound) Sound.play("error");
        }
      });
    }
  });
})();
