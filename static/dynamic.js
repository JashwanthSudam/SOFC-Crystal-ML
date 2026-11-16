/* Motion: the predicted value counts up and the scale pin slides into place when a result appears. */
(function () {
  if (window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  function countUp(el) {
    if (el.dataset.anim) return; el.dataset.anim = "1";
    var txt = el.textContent, m = txt.replace("\u2212", "-").match(/-?\d+(\.\d+)?/);
    if (!m) return;
    var end = parseFloat(m[0]), dec = (m[1] || ".").length - 1, t0 = performance.now(), dur = 900;
    function frame(t) {
      var p = Math.min(1, (t - t0) / dur), v = end * (1 - Math.pow(1 - p, 3));
      el.textContent = txt.replace(m[0], (v < 0 ? "\u2212" : "") + Math.abs(v).toFixed(dec));
      if (p < 1) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }
  function slidePin(pin) {
    if (pin.dataset.anim) return; pin.dataset.anim = "1";
    var target = pin.style.left; pin.style.left = "0%";
    requestAnimationFrame(function () { requestAnimationFrame(function () { pin.style.left = target; }); });
  }
  function scan(root) {
    if (!root.querySelectorAll) return;
    root.querySelectorAll(".logbig").forEach(countUp);
    root.querySelectorAll(".scale .pin").forEach(slidePin);
  }
  new MutationObserver(function (list) {
    list.forEach(function (m) { m.addedNodes.forEach(function (n) { if (n.nodeType === 1) scan(n); }); });
  }).observe(document.documentElement, { childList: true, subtree: true });
  document.addEventListener("DOMContentLoaded", function () { scan(document); });
})();
