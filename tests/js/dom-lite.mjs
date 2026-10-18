// A very small DOM, enough for the web app's table and list builders to run in
// node (tests/js/rows.mjs): elements with attributes, classes, children, events,
// text and a handful of selectors ("tag", ".class", "tag.class", "[attr]",
// "tag:not([attr])", descendant lists with ","). Not a browser: no layout, no CSS.

class Ev {
  constructor(type, init = {}) { Object.assign(this, { type, bubbles: true, key: init.key, target: null, defaultPrevented: false, stopped: false }); }
  preventDefault() { this.defaultPrevented = true; }
  stopPropagation() { this.stopped = true; }
}

class Node {
  constructor() { this.parentNode = null; this.childNodes = []; }
  get isConnected() { let n = this; while (n.parentNode) n = n.parentNode; return n === globalThis.document?.body || n === globalThis.document; }
  get textContent() { return this.childNodes.map((c) => c.textContent).join(""); }
  set textContent(v) { this.childNodes = []; if (v !== "" && v != null) this.append(String(v)); }
  append(...kids) {
    for (const k of kids.flat()) {
      const node = k instanceof Node ? k : new Text(String(k));
      if (node instanceof Fragment) { for (const c of [...node.childNodes]) this.append(c); continue; }
      node.parentNode?.removeChild?.(node);
      node.parentNode = this;
      this.childNodes.push(node);
    }
  }
  appendChild(k) { this.append(k); return k; }
  prepend(...kids) { const old = this.childNodes; this.childNodes = []; this.append(...kids); for (const c of old) { this.childNodes.push(c); } }
  insertBefore(k, ref) {
    if (!ref) return this.appendChild(k);
    k.parentNode?.removeChild?.(k);
    const i = this.childNodes.indexOf(ref);
    k.parentNode = this;
    this.childNodes.splice(i < 0 ? this.childNodes.length : i, 0, k);
    return k;
  }
  contains(k) { for (let n = k; n; n = n.parentNode) if (n === this) return true; return false; }
  removeChild(k) { this.childNodes = this.childNodes.filter((c) => c !== k); k.parentNode = null; return k; }
  replaceChildren(...kids) { for (const c of this.childNodes) c.parentNode = null; this.childNodes = []; this.append(...kids); }
  remove() { this.parentNode?.removeChild(this); }
}
class Text extends Node { constructor(t) { super(); this.data = t; } get textContent() { return this.data; } set textContent(v) { this.data = String(v); } }
class Fragment extends Node {}

function matches(el, sel) {
  return sel.split(",").some((one) => {
    const parts = one.trim().split(/\s+/);
    const simple = (e, s) => {
      const not = /:not\(\[([\w-]+)\]\)$/.exec(s);
      if (not) { if (e.hasAttribute(not[1])) return false; s = s.slice(0, not.index); }
      const attr = /\[([\w-]+)(?:="([^"]*)")?\]$/.exec(s);
      if (attr) { if (!e.hasAttribute(attr[1]) || (attr[2] != null && e.getAttribute(attr[1]) !== attr[2])) return false; s = s.slice(0, attr.index); }
      const [tag, ...cls] = s.split(".");
      if (tag && tag !== "*" && e.tagName !== tag.toUpperCase()) return false;
      return cls.every((c) => e.classList.contains(c));
    };
    if (!simple(el, parts[parts.length - 1])) return false;
    let up = el.parentNode;
    for (let i = parts.length - 2; i >= 0; i--) {
      while (up && !(up instanceof Element && simple(up, parts[i]))) up = up.parentNode;
      if (!up) return false;
      up = up.parentNode;
    }
    return true;
  });
}

class Element extends Node {
  constructor(tag) {
    super();
    this.tagName = tag.toUpperCase(); this.attrs = new Map(); this.listeners = {}; this.style = { setProperty() {} }; this.dataset = {};
    const el = this;
    this.classList = {
      add: (...c) => el._cls(new Set([...el._clsList(), ...c])), remove: (...c) => el._cls(new Set(el._clsList().filter((x) => !c.includes(x)))),
      contains: (c) => el._clsList().includes(c), toggle: (c, on = !el.classList.contains(c)) => (on ? el.classList.add(c) : el.classList.remove(c), on),
    };
  }
  _clsList() { return (this.attrs.get("class") || "").split(/\s+/).filter(Boolean); }
  _cls(set) { this.attrs.set("class", [...set].join(" ")); }
  get className() { return this.attrs.get("class") || ""; } set className(v) { this.attrs.set("class", String(v)); }
  get children() { return this.childNodes.filter((c) => c instanceof Element); }
  get firstChild() { return this.childNodes[0] || null; } get lastChild() { return this.childNodes[this.childNodes.length - 1] || null; }
  get parentElement() { return this.parentNode instanceof Element ? this.parentNode : null; }
  get id() { return this.attrs.get("id") || ""; } set id(v) { this.attrs.set("id", String(v)); }
  get tabIndex() { return Number(this.attrs.get("tabindex") ?? -1); } set tabIndex(v) { this.attrs.set("tabindex", String(v)); }
  get hidden() { return this.attrs.has("hidden"); } set hidden(v) { if (v) this.attrs.set("hidden", ""); else this.attrs.delete("hidden"); }
  get title() { return this.attrs.get("title") || ""; } set title(v) { this.attrs.set("title", String(v)); }
  set innerHTML(v) { this.childNodes = []; this._html = String(v); }
  get innerHTML() { return this._html || ""; }
  setAttribute(k, v) { this.attrs.set(k, String(v)); if (k.startsWith("data-")) this.dataset[k.slice(5).replace(/-(\w)/g, (_, c) => c.toUpperCase())] = String(v); }
  getAttribute(k) { if (k.startsWith("data-")) { const v = this.dataset[k.slice(5).replace(/-(\w)/g, (_, c) => c.toUpperCase())]; return v ?? null; } return this.attrs.has(k) ? this.attrs.get(k) : null; }
  hasAttribute(k) { return this.getAttribute(k) != null; }
  removeAttribute(k) { this.attrs.delete(k); }
  addEventListener(t, fn) { (this.listeners[t] ||= []).push(fn); }
  removeEventListener(t, fn) { this.listeners[t] = (this.listeners[t] || []).filter((f) => f !== fn); }
  dispatchEvent(e) {
    e.target ||= this;
    for (let n = this; n && !e.stopped; n = n.parentNode) { e.currentTarget = n; for (const fn of n.listeners?.[e.type] || []) fn(e); if (!e.bubbles) break; }
    return !e.defaultPrevented;
  }
  click() { this.dispatchEvent(new Ev("click")); }
  matches(sel) { return matches(this, sel); }
  closest(sel) { for (let n = this; n instanceof Element; n = n.parentNode) if (matches(n, sel)) return n; return null; }
  querySelectorAll(sel) { const out = []; const walk = (n) => { for (const c of n.children) { if (matches(c, sel)) out.push(c); walk(c); } }; walk(this); return out; }
  querySelector(sel) { return this.querySelectorAll(sel)[0] || null; }
  getBoundingClientRect() { return { top: 0, left: 0, right: 0, bottom: 0, width: 0, height: 0 }; }
  animate() { return { cancel() {} }; }
  scrollIntoView() {}
  focus() { globalThis.document.activeElement = this; }
  getClientRects() { return []; }
}

const hashOf = (h) => { const s = String(h); const i = s.indexOf("#"); return i >= 0 ? s.slice(i) : s; };

export function install() {
  const ids = new Map();
  const doc = {
    createElement: (t) => new Element(t), createElementNS: (_, t) => new Element(t), createTextNode: (t) => new Text(t),
    createDocumentFragment: () => new Fragment(),
    getElementById: (id) => { if (!ids.has(id)) ids.set(id, new Element("div")); return ids.get(id); },
    querySelector: () => null, querySelectorAll: () => [], addEventListener() {}, removeEventListener() {},
    documentElement: new Element("html"), activeElement: null, hidden: false,
  };
  doc.body = new Element("body");
  const store = new Map();
  Object.assign(globalThis, {
    document: doc, Node, Element, HTMLElement: Element, Event: Ev, KeyboardEvent: Ev, MouseEvent: Ev,
    location: { hash: "", pathname: "/traffic/example.com/", search: "", href: "http://example.com/traffic/example.com/" },
    // A whole address ("/path/#tab?q") keeps only its hash, as a browser's location.hash would.
    history: { state: null, pushState(s, _, h) { this.state = s; globalThis.location.hash = hashOf(h); }, replaceState(s, _, h) { this.state = s; globalThis.location.hash = hashOf(h); }, back() {}, go() {} },
    localStorage: { getItem: (k) => (store.has(k) ? store.get(k) : null), setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k) },
    matchMedia: () => ({ matches: false, addEventListener() {}, addListener() {} }),
    addEventListener() {}, removeEventListener() {}, getComputedStyle: () => ({ getPropertyValue: () => "" }),
    requestAnimationFrame: (fn) => setTimeout(fn, 0), cancelAnimationFrame: () => {}, getSelection: () => ({ toString: () => "" }),
    innerWidth: 1440, innerHeight: 900, devicePixelRatio: 1,
    ResizeObserver: class { observe() {} unobserve() {} disconnect() {} }, MutationObserver: class { observe() {} disconnect() {} },
    IntersectionObserver: class { observe() {} disconnect() {} },
  });
  globalThis.window = globalThis;
  if (!globalThis.navigator) globalThis.navigator = { userAgent: "node" };
  return doc;
}
export { Ev };
