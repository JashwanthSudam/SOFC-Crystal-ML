/* Light / dark theme. Loaded in <head> so the right theme is set before the page paints. */
(function () {
  var KEY = "kstar-theme", root = document.documentElement;
  function stored() { try { return localStorage.getItem(KEY); } catch (e) { return null; } }
  function system() { return window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"; }
  function label(b, t) {
    var next = t === "dark" ? "light" : "dark";
    b.setAttribute("aria-label", "Switch to " + next + " mode");
    b.setAttribute("title", "Switch to " + next + " mode");
  }
  function apply(t) {
    root.setAttribute("data-theme", t);
    var b = document.querySelector(".themebtn");
    if (b) label(b, t);
  }
  apply(stored() || system());
  if (window.matchMedia) {
    var mq = matchMedia("(prefers-color-scheme: dark)"), follow = function (e) { if (!stored()) apply(e.matches ? "dark" : "light"); };
    if (mq.addEventListener) mq.addEventListener("change", follow); else if (mq.addListener) mq.addListener(follow);
  }
  document.addEventListener("DOMContentLoaded", function () {
    var b = document.createElement("button");
    b.type = "button"; b.className = "themebtn";
    b.innerHTML = '<svg class="moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>'
      + '<svg class="sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>';
    label(b, root.getAttribute("data-theme") || "light");
    b.addEventListener("click", function () {
      var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      try { localStorage.setItem(KEY, next); } catch (e) {}
      apply(next);
    });
    var host = document.querySelector("header.top .role");
    if (host) host.appendChild(b); else { b.className += " float"; document.body.appendChild(b); }
  });
})();
