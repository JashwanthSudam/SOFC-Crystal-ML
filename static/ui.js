window.toast = (msg, kind) => {
  let box = document.getElementById("toasts");
  if (!box) { box = document.createElement("div"); box.id = "toasts"; box.setAttribute("aria-live", "polite"); document.body.appendChild(box); }
  const t = document.createElement("div"); t.className = "toast " + (kind || "info"); t.textContent = msg; box.appendChild(t);
  setTimeout(() => t.remove(), 5000);
};
const keepTheme = fn => { let t = null; try { t = localStorage.getItem("kstar-theme"); } catch {} fn(); if (t) { try { localStorage.setItem("kstar-theme", t); } catch {} } };
const store = { get: k => { try { return localStorage.getItem(k); } catch { return null; } } };
window.api = async (path, opts = {}) => {
  const t = store.get("kstar-token");
  opts = { ...opts, headers: { ...(opts.headers || {}), ...(t ? { Authorization: "Bearer " + t } : {}) } };
  const r = await fetch((window.API_BASE || "") + path, opts);
  if (r.status === 401 && t && !path.startsWith("/api/auth/")) { try { keepTheme(() => localStorage.clear()); } catch {} location.replace("index.html"); }
  return r;
};
document.addEventListener("click", e => {
  if (e.target.id === "signout") { e.preventDefault(); try { keepTheme(() => localStorage.clear()); sessionStorage.clear(); } catch {} location.href = "index.html"; }
});
const who = document.getElementById("who"); if (who) who.textContent = store.get("kstar-email") || "";
