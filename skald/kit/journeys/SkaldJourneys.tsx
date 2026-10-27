"use client";
// Skald recorded journeys: the page side for a Next.js (App Router) site (README.md).
// Put <SkaldJourneys skald="https://skald.example.com" /> once in app/layout.tsx.
// Nothing is stored or sent until your consent banner calls setJourneyConsent(true).
import Script from "next/script";
import type { ReactNode } from "react";

type Journeys = {
  on?: number;
  q?: unknown[][];
  consent?: (granted: boolean) => void;
  withdraw?: () => Promise<boolean>;
  track?: (name: string, opts?: { label?: string; email?: string }) => boolean;
};

function journeys(): Journeys {
  const w = window as unknown as { skaldJourneys?: Journeys };
  w.skaldJourneys = w.skaldJourneys || { q: [] };
  return w.skaldJourneys;
}

// Calls made before the script has loaded wait in its queue.
function call(method: "consent" | "track", ...args: unknown[]): void {
  const j = journeys();
  if (j.on) (j[method] as (...a: unknown[]) => unknown)(...args);
  else (j.q = j.q || []).push([method, ...args]);
}

// From your consent banner: true when the visitor accepts analytics, false when not.
export function setJourneyConsent(granted: boolean): void {
  call("consent", granted);
}

// A fixed fact about this visit, e.g. trackJourney("cta_click", { label: "Pricing hero" })
// or trackJourney("form_sent", { label: "Contact", email }) after your form is saved.
export function trackJourney(name: string, opts?: { label?: string; email?: string }): void {
  call("track", name, opts);
}

type Props = {
  skald: string;            // your Skald's address, e.g. https://skald.example.com
  notice?: string;          // your privacy notice's version, e.g. "v1"
  consented?: boolean;      // true only when your banner already said yes on the server
  relay?: string;           // default /api/skald-journey
};

export default function SkaldJourneys({ skald, notice, consented, relay = "/api/skald-journey" }: Props) {
  return (
    <Script
      src={`${skald.replace(/\/+$/, "")}/traffic-js/journeys.js`}
      strategy="afterInteractive"
      data-relay={relay}
      data-notice={notice}
      data-consent={consented ? "granted" : undefined}
    />
  );
}

// For your privacy page: deletes what Skald kept about this visitor and stops recording.
export function WithdrawJourneysLink({ children = "Withdraw my analytics consent" }: { children?: ReactNode }) {
  return (
    <a
      href="#"
      onClick={async (e) => {
        e.preventDefault();
        const j = journeys();
        const done = j.withdraw ? await j.withdraw() : false;
        alert(done ? "Done: your recorded visits were deleted." : "That did not go through. Please try again.");
      }}
    >
      {children}
    </a>
  );
}
