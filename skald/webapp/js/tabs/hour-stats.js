// Traffic > Time: three plain figures above the charts (SKALD-66), to pick a time for a
// release or a change: the busiest hours, the quietest hours, the busiest day of the week.
//
// Worked out from the same per-day hour counts the two charts draw (verified days only),
// which the day's own audit already recounts; nothing new is counted or stored.
// Hours are site hours in the report's time zone; a window may run past midnight.

export const WINDOW = 3;            // hours in the busiest and quietest stretch
export const WEEK_MIN = 2;          // each weekday seen at least this often to compare them
const ONE_DAY = 0.5;                // the busiest hour "mostly from one day" above this share

/* days: [{day, weekday, cells: [24 counts]}] (verified days only). */
export function hourStats(days) {
  const n = days.length;
  const hours = Array.from({ length: 24 }, (_, i) => days.reduce((a, d) => a + (d.cells[i] || 0), 0));
  const total = hours.reduce((a, v) => a + v, 0);
  if (!n || !total) return { days: n, total };
  const win = (i) => Array.from({ length: WINDOW }, (_, j) => hours[(i + j) % 24]).reduce((a, v) => a + v, 0);
  const idx = [...hours.keys()];
  // Ties go to the earliest hour, so the figure never moves between two equal draws.
  const top = idx.reduce((b, i) => (hours[i] > hours[b] ? i : b), 0);
  const busy = idx.reduce((b, i) => (win(i) > win(b) ? i : b), 0);
  const calm = idx.reduce((b, i) => (win(i) < win(b) ? i : b), 0);
  const peakDay = days.reduce((b, d) => ((d.cells[top] || 0) > (b.cells[top] || 0) ? d : b), days[0]);
  const out = {
    days: n, total,
    top: { hour: top, value: hours[top], share: hours[top] / total },
    busy: { from: busy, value: win(busy), share: win(busy) / total },
    calm: { from: calm, value: win(calm), share: win(calm) / total },
    oneDay: n >= 3 && (peakDay.cells[top] || 0) / hours[top] > ONE_DAY ? { day: peakDay.day, value: peakDay.cells[top] || 0 } : null,
  };
  const per = new Map();
  for (const d of days) {
    const w = per.get(d.weekday) || { days: 0, sum: 0, top: null };
    const all = d.cells.reduce((a, v) => a + (v || 0), 0);
    w.days += 1; w.sum += all;
    if (!w.top || all > w.top.value) w.top = { day: d.day, value: all };
    per.set(d.weekday, w);
  }
  const avg = [...per].map(([weekday, w]) => ({ weekday, days: w.days, avg: w.sum / w.days, sum: w.sum, top: w.top }));
  out.week = per.size === 7 && avg.every((w) => w.days >= WEEK_MIN)
    ? { busiest: avg.reduce((b, w) => (w.avg > b.avg ? w : b)), quietest: avg.reduce((b, w) => (w.avg < b.avg ? w : b)), all: avg }
    : null;
  // The busiest weekday "mostly from one day": one of its days had more than twice the
  // average of its other days (with two days, one is always at least half, so not "half").
  if (out.week) {
    const b = out.week.busiest, rest = (b.sum - b.top.value) / (b.days - 1);
    out.week.oneDay = b.top.value > 2 * rest ? b.top : null;
  }
  return out;
}
