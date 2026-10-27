// The open alerts in groups (2.41, docs/UI-RULES.md rules 13 and 14): one group per kind,
// the most urgent first, and one count of "what needs you" that the Site badge, the bell
// and Site › Alerts all show. Pure: no page, no fetch (tests/js/si-alerts.mjs).
//
//   groupsOf(open)   -> [{cause, severity, alerts, needs}]   urgent, then worth a look, then the rest
//   needsYou(file)   -> the number of groups that are urgent or worth a look (0 without a file)
//   pagesOf(alerts)  -> the distinct pages the AI alerts name (their subject "Assistant: /path")

export const RANK = ["high", "medium", "low"];
const rank = (sev) => (RANK.includes(sev) ? RANK.indexOf(sev) : RANK.length);
export const NEEDS = new Set(["high", "medium"]);

export function groupsOf(open = []) {
  const by = new Map();
  for (const a of open || []) {
    if (!a || !a.cause) continue;
    if (!by.has(a.cause)) by.set(a.cause, []);
    by.get(a.cause).push(a);
  }
  const groups = [...by].map(([cause, alerts]) => {
    alerts.sort((a, b) => rank(a.severity) - rank(b.severity) || String(b.opened_at || "").localeCompare(String(a.opened_at || "")));
    const severity = alerts[0].severity || "low";
    return { cause, severity, alerts, needs: NEEDS.has(severity) };
  });
  // The most urgent first; then the most alerts; then the newest.
  return groups.sort((a, b) => rank(a.severity) - rank(b.severity) || b.alerts.length - a.alerts.length
    || String(b.alerts[0].opened_at || "").localeCompare(String(a.alerts[0].opened_at || "")));
}

export const needsYou = (f) => (f ? groupsOf(f.open).filter((g) => g.needs).length : 0);

export function pagesOf(alerts) {
  const out = new Set();
  for (const a of alerts) {
    const sub = String(a.subject || "");
    const at = sub.indexOf(": /");
    out.add(at >= 0 ? sub.slice(at + 2) : sub);
  }
  return [...out];
}
