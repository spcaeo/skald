// The one place that knows the file layout written by the data layer.
// Everything after this works on the app's own shape:
//
//   model = { site, tz, today, anchor, firstDay, views: [{slug, name}],
//             canRefresh, refreshUrl, credit: {text, url} | null,
//             byDay: Map(day -> Day), live: Live | null, journeys: [Journey] }
//   Day   = { day, state: ok|partial|withheld|missing, partial: "data from 14:05",
//             hits: {people, answer_engines, search_engines, bots, ours},
//             readers, visits, views, cited, tiers: {training, asked},
//             search, probes, nf, err,
//             by: {country, device, browser, os, source, referrer, campaign, landing, hour} | null,
//             pages, ai_pages, cited_by, engines: {training, asked}, search_engines, bot_agents,
//             statuses: {group: {class: n}} | null, not_found, server_errors, speeds, slow_pages,
//             posts: {group: {total, pages}}, visit: {pages, seconds, exits, steps, flags} | null,
//             ours_by: {label: n} }
//   Live  = { state, day, generated_at, from, problems, figures: Day-shaped, events: [...] }
//   Journey = { start, day, country, device, browser, os, source, via, trail: [{path, page, at?}],
//               pages, seconds, exit, flags: [] }

export async function adapt(get) {
  const raw = await get("app.json");
  if (!raw) throw new Error("no figures have been written beside this page yet");
  const byDay = new Map((raw.days || []).map((d) => [d.day, d]));
  return { ...raw, byDay, journeys: raw.journeys || [] };
}
