// The sign-in pages (/traffic-auth/login, forgot, reset, invite): one module
// for all four; <body data-page> says which. Each form goes to the helper as
// JSON in a same-origin POST. A password is only ever in that POST's body:
// never in an address, never in storage. After signing in, the browser goes
// only to a path on this server under /traffic/, whatever `next` says.

const $ = (id) => document.getElementById(id);
const PAGE = document.body.dataset.page;
const params = new URLSearchParams(location.search);
const MIN_PASSWORD = 12;
const UNREACHABLE = "The server could not be reached. Check your connection and try again.";

// The theme the dashboard was left in (light, dark or the system's), read only.
try {
  const t = localStorage.getItem("ti-theme");
  if (t === "light" || t === "dark") document.documentElement.setAttribute("data-theme", t);
} catch { /* storage blocked: the system's theme */ }

// Where to go after signing in: a path on this server under /traffic/, else `fallback`.
export function safeNext(raw, fallback = "/traffic/") {
  if (typeof raw !== "string" || !raw.startsWith("/") || raw.startsWith("//") || /[\\\u0000-\u001f\u007f]/.test(raw)) return fallback;
  let u;
  try { u = new URL(raw, location.origin); } catch { return fallback; }
  if (u.origin !== location.origin || !u.pathname.startsWith("/traffic/")) return fallback;
  return u.pathname + u.search + u.hash;
}

// The page asked for before signing in. nginx sends `?next=$request_uri` as it is, not
// encoded, so a page with its own query (?range=7d&view=x) is the whole rest of the address.
function askedNext() {
  const m = /[?&]next=(.*)$/s.exec(location.search);
  if (!m) return "";
  try { return decodeURIComponent(m[1]); } catch { return m[1]; }
}

// A JSON POST to the helper: {status, data}; status 0 when the server could not be reached.
async function post(path, body) {
  let res;
  try {
    res = await fetch(path, { method: "POST", credentials: "same-origin", cache: "no-store", redirect: "manual",
      headers: { "Content-Type": "application/json", Accept: "application/json" }, body: JSON.stringify(body) });
  } catch {
    return { status: 0, data: {} };
  }
  let data = {};
  try { data = (await res.json()) || {}; } catch { /* not JSON: the status says enough */ }
  return { status: res.status, data };
}

async function get(path) {
  try {
    const res = await fetch(path, { credentials: "same-origin", cache: "no-store", headers: { Accept: "application/json" } });
    let data = {};
    try { data = (await res.json()) || {}; } catch { /* not JSON */ }
    return { status: res.status, data };
  } catch {
    return { status: 0, data: {} };
  }
}

const msg = $("msg");
function say(text, ok = false) {
  if (!msg) return;
  msg.textContent = text || "";
  msg.className = `msg${text ? (ok ? " ok" : " err") : ""}`;
}
function busy(on, words) {
  const b = $("submit");
  if (!b) return;
  if (on) { b.dataset.words = b.textContent; b.textContent = words; b.disabled = true; b.setAttribute("aria-busy", "true"); }
  else { b.textContent = b.dataset.words || b.textContent; b.disabled = false; b.removeAttribute("aria-busy"); }
}
const looksLikeEmail = (v) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v);
function passwordProblem(pw, again) {
  if (pw.length < MIN_PASSWORD) return `The password is too short: it needs at least ${MIN_PASSWORD} characters.`;
  if (pw !== again) return "The two passwords are not the same.";
  return "";
}
function refusal(status, data, fallback) {
  if (status === 0) return UNREACHABLE;
  if (status === 429) return data.error || "Too many tries. Wait 30 seconds, then try again.";
  return data.error || fallback;
}

// ------------------------------------------------------------- sign in
function login() {
  const form = $("form"), email = $("email"), password = $("password"), code = $("code");
  const next = safeNext(askedNext(), "");
  let needsCode = false, needsNew = false, needsSetup = false, done = null;
  // The organisation requires two-step sign-in and this account has none: set it up here.
  // A new password chosen just before stays in its fields (hidden) and is sent again
  // with the set-up code: the server sets both at once and answers with the codes.
  const toSetup = (data) => {
    needsSetup = true;
    $("step-password").hidden = true;
    $("step-code").hidden = true;
    $("step-new").hidden = true;
    $("step-setup").hidden = false;
    $("back").hidden = false;
    $("setup-secret").textContent = data.secret || "";
    $("setup-uri").href = /^otpauth:\/\//.test(data.uri || "") ? data.uri : "#";
    $("lede").textContent = data.message || "Set up two-step sign-in.";
    $("submit").textContent = "Turn on and sign in";
    say("");
    $("setup-code").value = "";
    $("setup-code").focus();
  };
  // The recovery codes, once, before the page goes on.
  const toCodes = (codes, nextUrl) => {
    done = nextUrl;
    $("step-setup").hidden = true;
    $("step-new").hidden = true;
    $("step-code").hidden = true;
    $("step-codes").hidden = false;
    $("back").hidden = true;
    $("codes").textContent = codes.join("\n");
    $("lede").textContent = "Two-step sign-in is on.";
    $("submit").textContent = "I have kept them; continue";
    say("");
  };

  const toCode = () => {
    needsCode = true;
    $("step-password").hidden = true;
    $("step-code").hidden = false;
    $("back").hidden = false;
    $("lede").textContent = "Two-step sign-in is on for this account.";
    $("submit").textContent = "Check the code";
    say("");
    code.value = "";
    code.focus();
  };
  // An account made from an invite link the admin passed on by hand: it must choose
  // its own password before it signs in (the server says must_change).
  const toNew = (text) => {
    needsNew = true;
    needsSetup = false;
    $("step-password").hidden = true;
    $("step-code").hidden = true;
    $("step-setup").hidden = true;
    $("step-new").hidden = false;
    $("back").hidden = false;
    $("lede").textContent = "Choose your own password.";
    $("submit").textContent = "Save and sign in";
    say(text || "");
    $("new-password").focus();
  };
  const toPassword = () => {
    needsCode = false;
    needsNew = false;
    needsSetup = false;
    $("step-setup").hidden = true;
    $("step-password").hidden = false;
    $("step-new").hidden = true;
    $("new-password").value = "";
    $("new-again").value = "";
    $("step-code").hidden = true;
    $("back").hidden = true;
    $("lede").textContent = "To see your sites' traffic.";
    $("submit").textContent = "Sign in";
    password.value = "";
    code.value = "";
    say("");
    email.focus();
  };
  $("back").addEventListener("click", toPassword);
  email.focus();

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (done) { location.replace(safeNext(done)); return; }
    const addr = email.value.trim();
    if (!looksLikeEmail(addr)) { toPasswordIfNeeded(); say("Type the whole email address you sign in with."); email.focus(); return; }
    if (!password.value) { toPasswordIfNeeded(); say("Type your password."); password.focus(); return; }
    const body = { email: addr, password: password.value, remember: $("remember").checked };
    if (needsCode) {
      const c = code.value.replace(/\s+/g, "");
      if (!/^\d{6}$/.test(c) && !/^[A-Za-z0-9-]{8,32}$/.test(c)) { say("Type the 6 digits from your app, or a recovery code."); code.focus(); return; }
      body.code = c;
    }
    if (needsNew) {
      const bad = passwordProblem($("new-password").value, $("new-again").value);
      if (bad) { say(bad); $("new-password").focus(); return; }
      body.new_password = $("new-password").value;
    }
    if (needsSetup) {
      const c = $("setup-code").value.replace(/\s+/g, "");
      if (!/^\d{6}$/.test(c)) { say("Type the 6 digits the app shows now."); $("setup-code").focus(); return; }
      body.setup_code = c;
    }
    if (next) body.next = next;
    busy(true, "Signing in...");
    const { status, data } = await post("/traffic-auth/login", body);
    busy(false);
    if (status === 200 && data.needs_code) { toCode(); return; }
    if (status === 200 && data.needs_setup) { toSetup(data); return; }
    if (status === 400 && data.needs_setup) { say(data.error || "That code is not right."); $("setup-code").value = ""; $("setup-code").focus(); return; }
    if (status === 200 && data.must_change) { toNew(data.message); return; }
    if (status === 400 && data.must_change) { toNew(data.error); return; }
    if (status === 200 && data.ok !== false && Array.isArray(data.recovery_codes) && data.recovery_codes.length) {
      toCodes(data.recovery_codes, safeNext(data.next, next || "/traffic/"));
      return;
    }
    if (status === 200 && data.ok !== false) {
      say("Signed in.", true);
      location.replace(safeNext(data.next, next || "/traffic/"));
      return;
    }
    if (status === 401) {
      if (needsCode) { say(data.error || "That code is not right. Codes change every 30 seconds; try the one the app shows now."); code.value = ""; code.focus(); }
      else { say(data.error || "That email and password do not match."); password.value = ""; password.focus(); }
      return;
    }
    say(refusal(status, data, `Signing in did not work (${status}). Try again in a moment.`));
  });
  function toPasswordIfNeeded() { if (needsCode) toPassword(); }
}

// ------------------------------------------------------- forgot password
function forgot() {
  const form = $("form"), email = $("email");
  email.focus();
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const addr = email.value.trim();
    if (!looksLikeEmail(addr)) { say("Type the whole email address you sign in with."); email.focus(); return; }
    busy(true, "Sending...");
    const { status } = await post("/traffic-auth/forgot", { email: addr });
    busy(false);
    if (status === 0) { say(UNREACHABLE); return; }
    // The same words whatever the server found: this page never says whether an address has an account.
    form.hidden = true;
    $("done").hidden = false;
  });
}

// ------------------------------------------------------ reset password
function reset() {
  const token = params.get("t") || "";
  const form = $("form"), password = $("password"), again = $("again");
  const broken = (text) => { form.hidden = true; $("broken-text").textContent = text; $("broken").hidden = false; };
  if (!/^[A-Za-z0-9_.~-]{16,256}$/.test(token)) { broken("This link is not complete. Copy the whole link from the mail, or ask for a new one."); return; }
  password.focus();
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const bad = passwordProblem(password.value, again.value);
    if (bad) { say(bad); password.focus(); return; }
    busy(true, "Saving...");
    const { status, data } = await post("/traffic-auth/reset", { token, password: password.value });
    busy(false);
    if (status === 200 && data.ok !== false) {
      password.value = ""; again.value = "";
      form.hidden = true;
      $("done").hidden = false;
      setTimeout(() => location.replace(safeNext(data.next, "/traffic-auth/login")), 1500);
      return;
    }
    if (status === 400 && /expired|used|unknown|invalid|not valid/i.test(data.error || "")) { broken(data.error); return; }
    say(refusal(status, data, `The password was not saved (${status}).`));
  });
}

// -------------------------------------------------------------- invite
async function invite() {
  const token = params.get("t") || "";
  const form = $("form");
  const broken = (text) => { form.hidden = true; $("lede").hidden = true; $("broken-text").textContent = text; $("broken").hidden = false; };
  if (!/^[A-Za-z0-9_.~-]{16,256}$/.test(token)) { broken("This invite link is not complete. Copy the whole link from the mail."); return; }
  const { status, data } = await get(`/traffic-auth/invite-info?t=${encodeURIComponent(token)}`);
  if (status !== 200 || data.ok === false || !data.org) {
    broken(status === 0 ? UNREACHABLE : data.error || "This invite has expired, was used already, or was cancelled.");
    return;
  }
  const role = { owner: "an owner", admin: "an admin", viewer: "a viewer" }[data.role] || data.role || "a member";
  $("title").textContent = `Join ${data.org}`;
  const lede = $("lede");
  lede.replaceChildren(`You are invited to ${data.org}'s traffic pages as ${role}`, data.email ? ", with the address " : ".");
  if (data.email) { const b = document.createElement("b"); b.textContent = data.email; lede.append(b, "."); }
  form.hidden = false;
  const fresh = !data.has_account;
  $("step-new").hidden = !fresh;
  if (fresh) { $("submit").textContent = "Create account and join"; $("name").focus(); }
  else {
    const p = $("existing");
    p.textContent = "You already have an account with this address: joining adds this organisation to it.";
    p.hidden = false;
    $("submit").textContent = `Join ${data.org}`;
    $("submit").focus();
  }
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const body = { token };
    if (fresh) {
      const name = $("name").value.trim(), pw = $("password").value;
      if (!name) { say("Type your name, as your team should see it."); $("name").focus(); return; }
      const bad = passwordProblem(pw, $("again").value);
      if (bad) { say(bad); $("password").focus(); return; }
      body.name = name; body.password = pw;
    }
    busy(true, "Joining...");
    const r = await post("/traffic-auth/invite", body);
    busy(false);
    if (r.status === 200 && r.data.ok !== false) {
      if (fresh) { $("password").value = ""; $("again").value = ""; }
      // Not signed in by the link (an existing account, or a link passed on by hand):
      // the traffic pages send the browser to sign in, and there a hand-passed link's
      // account chooses its own password.
      say(r.data.signed_in === false ? "Done. Now sign in." : "Done. Opening the traffic pages...", true);
      location.replace(safeNext(r.data.next, "/traffic/"));
      return;
    }
    say(refusal(r.status, r.data, `Joining did not work (${r.status}).`));
  });
}

// --------------------------------------------- sign up (saas, docs/SAAS.md)
// The same words whatever the address: the page never says whether it has an account.
function signup() {
  const form = $("form"), email = $("email");
  email.focus();
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const addr = email.value.trim();
    if (!looksLikeEmail(addr)) { say("Type the whole email address, like name@example.com."); email.focus(); return; }
    busy(true, "Sending...");
    const { status, data } = await post("/traffic-auth/signup", { email: addr });
    busy(false);
    if (status === 200 && data.ok !== false) { form.hidden = true; $("done").hidden = false; return; }
    if (status === 429) { say(data.error || "Too many sign-ups from here. Try again in an hour."); return; }
    say(refusal(status, data, `The link was not sent (${status}). Try again in a moment.`));
  });
}

async function signupFinish() {
  const token = params.get("t") || "";
  const form = $("form");
  const broken = (text) => { form.hidden = true; $("lede").hidden = true; $("broken-text").textContent = text; $("broken").hidden = false; };
  if (!/^[A-Za-z0-9_.~-]{16,256}$/.test(token)) { broken("This link is not complete. Copy the whole link from the mail, or ask for a new one."); return; }
  const { status, data } = await get(`/traffic-auth/signup-info?t=${encodeURIComponent(token)}`);
  if (status !== 200 || data.ok === false || !data.email) {
    broken(status === 0 ? UNREACHABLE : data.error || "This sign-up link has expired or was used already.");
    return;
  }
  const lede = $("lede");
  const b = document.createElement("b");
  b.textContent = data.email;
  lede.replaceChildren("Your account is for ", b, ". Choose a password, name your organisation and add your first site.");
  form.hidden = false;
  $("name").focus();
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = $("name").value.trim(), pw = $("password").value, org = $("org").value.trim(), host = $("host").value.trim();
    if (!name) { say("Type your name, as your team should see it."); $("name").focus(); return; }
    const bad = passwordProblem(pw, $("again").value);
    if (bad) { say(bad); $("password").focus(); return; }
    if (!org) { say("Give the organisation a name."); $("org").focus(); return; }
    if (!/^[A-Za-z0-9.:/-]+\.[A-Za-z0-9./:-]+$/.test(host)) { say("The site is a host name, like www.example.com."); $("host").focus(); return; }
    busy(true, "Creating...");
    const r = await post("/traffic-auth/signup-finish", { token, name, password: pw, org, host });
    busy(false);
    if (r.status === 200 && r.data.ok !== false) {
      $("password").value = ""; $("again").value = "";
      say("Done. Opening your traffic pages...", true);
      location.replace(safeNext(r.data.next, "/traffic/"));
      return;
    }
    if (r.status === 400 && /expired|already used|not valid/i.test(r.data.error || "")) { broken(r.data.error); return; }
    say(refusal(r.status, r.data, `The account was not made (${r.status}).`));
  });
}

// A Show / Hide button on every password field: the password is shown as text
// only while asked, and hidden again before the form is sent.
function showButtons() {
  for (const field of document.querySelectorAll('input[type="password"]')) {
    const wrap = document.createElement("span");
    wrap.className = "pw";
    field.replaceWith(wrap);
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "pw-toggle";
    btn.textContent = "Show";
    btn.setAttribute("aria-pressed", "false");
    if (!field.id) field.id = `pw-${Math.random().toString(36).slice(2, 8)}`;
    btn.setAttribute("aria-controls", field.id);
    // The button sits inside the label: name the field by the label's own words
    // only, or it would read "Password Show".
    const label = field.closest("label"), words = label?.firstChild;
    if (words && words.nodeType === Node.TEXT_NODE && words.textContent.trim()) {
      const name = document.createElement("span");
      name.id = `${field.id}-name`;
      name.textContent = words.textContent;
      words.replaceWith(name);
      field.setAttribute("aria-labelledby", name.id);
    }
    btn.setAttribute("aria-label", "Show password");
    btn.addEventListener("click", () => {
      const shown = field.type === "password";
      field.type = shown ? "text" : "password";
      btn.textContent = shown ? "Hide" : "Show";
      btn.setAttribute("aria-pressed", String(shown));
      btn.setAttribute("aria-label", shown ? "Hide password" : "Show password");
      field.focus();
    });
    wrap.append(field, btn);
    field.form?.addEventListener("submit", () => {
      field.type = "password"; btn.textContent = "Show";
      btn.setAttribute("aria-pressed", "false"); btn.setAttribute("aria-label", "Show password");
    }, true);
  }
}
showButtons();

({ login, forgot, reset, invite, signup, "signup-finish": signupFinish })[PAGE]?.();
