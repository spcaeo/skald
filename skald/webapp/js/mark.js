// The Skald mark for the sidebar: the master drawing from assets/brand/skald.svg
// (a quill crossing a carved stave), inline so the page loads nothing else.
// Colours follow the theme: the tile is the ink, the drawing the paper.
export const MARK = '<svg viewBox="0 0 64 64" aria-hidden="true"><rect width="64" height="64" rx="15" fill="var(--ink)"/>' +
  '<path d="M20 14.5 27 11v41l-7 3.5z" fill="var(--page)"/>' +
  '<g fill="var(--page)" stroke="var(--ink)" stroke-width="3" stroke-linejoin="round" paint-order="stroke">' +
  '<path d="M25 41C28 29 38 17 51 10c-2 9-6 16-11 21l-3.5-.5 1.5 3c-3 3.5-7 7-10.5 9.5z"/><path d="M24.6 39.2l3.6 3.2L11.5 56.5z"/></g>' +
  '<path d="M27.5 41.2 48.5 13.5" stroke="var(--ink)" stroke-width="1.6" stroke-linecap="round"/></svg>';
