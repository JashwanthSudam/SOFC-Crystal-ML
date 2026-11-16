/* Research-only notice on every page, plus an option to open each page in its own browser tab. */
(function () {
  var KEY = "kstar-newtab", on = true;
  try { on = localStorage.getItem(KEY) !== "0"; } catch (e) {}
  function ready(f) { document.readyState !== "loading" ? f() : document.addEventListener("DOMContentLoaded", f); }
  ready(function () {
    var bar = document.createElement("div");
    bar.className = "research-bar"; bar.setAttribute("role", "note");
    bar.innerHTML = "<strong>Research use only.</strong> This tool is for researchers. Predictions are model estimates and must be validated experimentally.";
    document.body.insertBefore(bar, document.body.firstChild);

    var ft = document.createElement("footer");
    ft.className = "research-foot";
    ft.textContent = "k* predictor · for researchers only · not for commercial, safety-critical or clinical use";
    document.body.appendChild(ft);

    var h1 = document.querySelector(".hero-art h1");
    if (h1) {
      var pill = document.createElement("span");
      pill.className = "research-pill"; pill.textContent = "For researchers only";
      h1.parentNode.insertBefore(pill, h1);
    }

    var role = document.querySelector("header.top .role");
    if (role) {
      var b = document.createElement("button");
      b.type = "button"; b.className = "tabtoggle";
      b.title = "Open each page in its own browser tab";
      function paint() { b.setAttribute("aria-pressed", on); b.textContent = on ? "Own tabs: on" : "Own tabs: off"; }
      b.addEventListener("click", function () {
        on = !on; try { localStorage.setItem(KEY, on ? "1" : "0"); } catch (e) {} paint();
      });
      paint(); role.insertBefore(b, role.firstChild);
    }

    document.addEventListener("click", function (e) {
      if (!on || e.defaultPrevented || e.button || e.ctrlKey || e.metaKey || e.shiftKey) return;
      var a = e.target.closest && e.target.closest("header.top .nav a");
      if (!a || a.origin !== location.origin || a.pathname === location.pathname) return;
      e.preventDefault(); window.open(a.href, "_blank");
    });
  });
})();
