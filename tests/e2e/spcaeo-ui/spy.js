// Counts the listeners on window by type, and any Content-Security-Policy refusal,
// so the test can show that redraws do not pile listeners up and the CSP holds.
// A classic script, loaded before the modules.
(function () {
  "use strict";
  const live = new Map();
  const add = window.addEventListener.bind(window);
  const remove = window.removeEventListener.bind(window);
  window.addEventListener = function (type, fn, opts) {
    if (!live.has(type)) live.set(type, new Set());
    live.get(type).add(fn);
    return add(type, fn, opts);
  };
  window.removeEventListener = function (type, fn, opts) {
    live.get(type)?.delete(fn);
    return remove(type, fn, opts);
  };
  window.__listeners = (type) => (live.get(type) ? live.get(type).size : 0);
  window.__csp = [];
  document.addEventListener("securitypolicyviolation", (e) => window.__csp.push(`${e.violatedDirective} ${e.blockedURI}`));
})();
