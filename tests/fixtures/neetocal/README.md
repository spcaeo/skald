Real NeetoCal webhook bodies (SKALD-54), from a test booking on 25 Nov 2026,
read from NeetoCal's own delivery log (Webhooks > Deliveries > Payload). Names,
emails, the workspace and the visitor ID are replaced; the shape is NeetoCal's.

- create.json             Booking created (method "create", status "confirmed")
- update-rescheduled.json Booking rescheduled (method "update" + reschedule_details;
                          the organisation ids are zeroed and the reschedule detail
                          trimmed to the keys Skald reads around)
- cancel.json             Booking cancelled (method "cancel": only id, sid, canceller)
