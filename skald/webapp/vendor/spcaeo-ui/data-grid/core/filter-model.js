/* spcaeo/ui (data-grid/core/filter-model.js), from github.com/spcaeo/ui at ad51155, vendored by Skald.
   Changes and the reason for each: VERSION.md beside this folder.

   MIT License. Copyright (c) 2026 spcaeo.
   Permission is hereby granted, free of charge, to any person obtaining a copy of this software
   and associated documentation files (the "Software"), to deal in the Software without
   restriction, including without limitation the rights to use, copy, modify, merge, publish,
   distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the
   Software is furnished to do so, subject to the following conditions:
   The above copyright notice and this permission notice shall be included in all copies or
   substantial portions of the Software.
   THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
   BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
   NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
   DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
   OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE. */
/**
 * A typed filter model that survives a round trip through a URL.
 *
 * Two things make this harder than it looks, and both are handled here rather
 * than in every grid that uses it:
 *
 *   1. The encoded value is UNTRUSTED. It arrives from a URL a person can edit,
 *      from a bookmark saved before a field was renamed, from a link pasted
 *      through software that mangles characters. It must never crash the grid.
 *   2. It must survive non-ASCII text. `btoa` throws on anything above U+00FF,
 *      so a filter for "Zürich" or "日本" breaks the moment someone shares it.
 *      TextEncoder/TextDecoder is used instead.
 */

/** @typedef {"text"|"enum"|"boolean"|"date"|"number"} FieldType */
/** @typedef {{ field: string, operator: string, values: string[] }} FilterCondition */
/** @typedef {{ conjunction: "and"|"or", conditions: FilterCondition[] }} FilterGroup */

/** Which operators make sense for which field type. Anything else is dropped. */
export const OPERATORS_BY_TYPE = {
  text: ["contains", "not_contains", "is", "is_not", "is_set", "is_not_set"],
  enum: ["in", "not_in", "is_set", "is_not_set"],
  boolean: ["is"],
  date: ["before", "after", "is", "is_set", "is_not_set"],
  number: ["is", "is_not", "gt", "gte", "lt", "lte"],
};

/** Operators that are complete on their own — a value would be meaningless. */
export const VALUELESS_OPERATORS = new Set(["is_set", "is_not_set"]);

export const EMPTY_FILTER = { conjunction: "and", conditions: [] };

export const isEmptyFilter = (filter) =>
  !filter || !filter.conditions || filter.conditions.length === 0;

/** Schema version, so an old encoded filter can be recognised and dropped. */
const VERSION = 1;

/** Refuse absurd input rather than trying to parse it — §30 size ceiling. */
const MAX_ENCODED_LENGTH = 2048;

const toBase64Url = (bytes) => {
  let binary = "";
  for (const b of bytes) binary += String.fromCharCode(b);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
};

const fromBase64Url = (text) => {
  const padded = text
    .replace(/-/g, "+")
    .replace(/_/g, "/")
    .padEnd(Math.ceil(text.length / 4) * 4, "=");
  const binary = atob(padded);
  return Uint8Array.from(binary, (c) => c.charCodeAt(0));
};

/**
 * Encode as `1.<base64url>`, a positional tuple array rather than objects:
 * `[["status","in",["active"]]]`. Shorter URLs are easier to read, share and
 * paste, and the version prefix is outside the payload so it can be checked
 * without decoding anything.
 */
export function encodeFilter(filter) {
  if (isEmptyFilter(filter)) return null;
  const tuples = filter.conditions.map((c) => [c.field, c.operator, c.values ?? []]);
  const payload = JSON.stringify([filter.conjunction === "or" ? "or" : "and", tuples]);
  return `${VERSION}.${toBase64Url(new TextEncoder().encode(payload))}`;
}

/**
 * Decode, validating every condition against the fields this grid actually has.
 *
 * Returns the surviving conditions AND the names that were dropped, so the grid
 * can tell the user "2 filters no longer apply" instead of silently showing a
 * different result set than the link promised. Silence here is the bug: the
 * person shared a filtered view and the recipient sees an unfiltered one with
 * no indication anything was lost.
 *
 * @param {string|null} raw
 * @param {Map<string, FieldType>=} fields  known field id -> type
 * @returns {{ filter: FilterGroup, dropped: string[] }}
 */
export function decodeFilter(raw, fields) {
  const empty = { filter: EMPTY_FILTER, dropped: [] };
  if (!raw || raw.length > MAX_ENCODED_LENGTH) return empty;

  const dot = raw.indexOf(".");
  if (dot < 1) return empty;
  if (Number(raw.slice(0, dot)) !== VERSION) return empty; // a future or ancient format

  let parsed;
  try {
    parsed = JSON.parse(new TextDecoder().decode(fromBase64Url(raw.slice(dot + 1))));
  } catch {
    return empty; // malformed base64, malformed JSON, truncated link
  }
  if (!Array.isArray(parsed) || parsed.length !== 2 || !Array.isArray(parsed[1])) return empty;

  const dropped = [];
  const conditions = [];
  for (const tuple of parsed[1]) {
    if (!Array.isArray(tuple) || tuple.length < 2) continue;
    const [field, operator, values] = tuple;
    if (typeof field !== "string" || typeof operator !== "string") continue;

    if (fields) {
      const type = fields.get(field);
      if (!type) {
        dropped.push(field);
        continue;
      } // field no longer exists
      if (!OPERATORS_BY_TYPE[type]?.includes(operator)) {
        dropped.push(field);
        continue;
      }
    }
    const list = Array.isArray(values) ? values.filter((v) => typeof v === "string") : [];
    if (!list.length && !VALUELESS_OPERATORS.has(operator)) {
      dropped.push(field);
      continue;
    }
    conditions.push({ field, operator, values: list });
  }

  return {
    filter: { conjunction: parsed[0] === "or" ? "or" : "and", conditions },
    dropped,
  };
}

/** Human-readable chip text. The grid shows one chip per active condition. */
export function describeCondition(condition, field) {
  const label = field?.label ?? condition.field;
  const verb =
    {
      contains: "contains",
      not_contains: "does not contain",
      is: "is",
      is_not: "is not",
      in: "is any of",
      not_in: "is none of",
      is_set: "is set",
      is_not_set: "is not set",
      before: "before",
      after: "after",
      gt: ">",
      gte: "≥",
      lt: "<",
      lte: "≤",
    }[condition.operator] ?? condition.operator;

  if (VALUELESS_OPERATORS.has(condition.operator)) return `${label} ${verb}`;
  const shown = condition.values.map((v) => field?.options?.find((o) => o.value === v)?.label ?? v);
  const text =
    shown.length > 2 ? `${shown.slice(0, 2).join(", ")} +${shown.length - 2}` : shown.join(", ");
  return `${label} ${verb} ${text}`;
}
