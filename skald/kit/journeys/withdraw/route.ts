// Skald recorded journeys: app/api/skald-journey/withdraw/route.ts (README.md).
// The page sends {visitor_id} when the visitor withdraws consent; this route asks
// Skald, signed, to delete everything kept for that visitor.
import { answer, forward, take } from "../sign.ts";

export const runtime = "nodejs";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

export async function POST(req: Request): Promise<Response> {
  const got = await take(req);
  if ("refused" in got) return got.refused;
  const visitorId = got.data.visitor_id;
  if (typeof visitorId !== "string" || !UUID.test(visitorId)) {
    return answer(400, { error: "visitor_id is not a lowercase UUID", field: "visitor_id" });
  }
  const body = JSON.stringify({
    schema_version: 1,
    visitor_id: visitorId,
    occurred_at: new Date().toISOString().slice(0, 19) + "Z",
    consent: { analytics: "withdrawn" },
  });
  const url = process.env.SKALD_JOURNEY_URL;
  return forward(url && url.replace(/\/+$/, "") + "/withdraw", process.env.SKALD_JOURNEY_SECRET, body);
}
