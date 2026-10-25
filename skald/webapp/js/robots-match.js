// robots.txt as a crawler reads it (RFC 9309), for any page the reader opens: the same
// rule as skald/robots_match.py, which ai_ready.json's rules come from
// (robots.crawlers[token].rules: [[kind, pattern], ...], already the token's group).
//
//   decide(rules, "/blog/post/")  -> { allowed, rule: [kind, pattern] | null }
//
// The longest matching pattern wins, an Allow on a tie; none matching allows. "*" in a
// pattern stands for any characters, a "$" at its end for the end of the path. Paths and
// patterns are compared after one clean-up: a %xx of a letter, digit or - . _ ~ written
// out, any other %xx in capitals, characters outside printable ASCII as the %xx of their
// UTF-8 bytes. tests/test_ai_ready_js.py holds this file and the Python one to the same
// answers. Pure: no DOM.

const UNRESERVED = /^[A-Za-z0-9\-._~]$/;
const HEX = /^[0-9A-Fa-f]{2}$/;

export function clean(text) {
  const s = String(text ?? "");
  let out = "";
  for (let i = 0; i < s.length;) {
    const c = s[i];
    const two = s.slice(i + 1, i + 3);
    if (c === "%" && HEX.test(two)) {
      const ch = String.fromCharCode(parseInt(two, 16));
      out += UNRESERVED.test(ch) ? ch : `%${two.toUpperCase()}`;
      i += 3;
      continue;
    }
    const code = s.codePointAt(i);
    const width = code > 0xffff ? 2 : 1;
    if (code > 0x20 && code <= 0x7e) out += c;
    else for (const b of new TextEncoder().encode(String.fromCodePoint(code))) out += `%${b.toString(16).toUpperCase().padStart(2, "0")}`;
    i += width;
  }
  return out;
}

export function matches(pattern, path) {
  let p = pattern;
  const end = p.endsWith("$");
  if (end) p = p.slice(0, -1);
  const parts = p.split("*");
  if (!path.startsWith(parts[0])) return false;
  let at = parts[0].length;
  if (parts.length === 1) return end ? at === path.length : true;
  for (const part of parts.slice(1, -1)) {
    const found = path.indexOf(part, at);
    if (found < 0) return false;
    at = found + part.length;
  }
  const last = parts[parts.length - 1];
  if (end) return path.length - last.length >= at && path.endsWith(last);
  return path.indexOf(last, at) >= 0;
}

export function decide(rules, path) {
  const target = clean(path || "/");
  let best = null, size = -1;
  for (const [kind, pattern] of rules || []) {
    const p = clean(pattern);
    if (!p || !matches(p, target)) continue;
    if (p.length > size || (p.length === size && kind === "allow" && best[0] === "disallow")) { best = [kind, pattern]; size = p.length; }
  }
  return { allowed: best === null || best[0] === "allow", rule: best };
}
