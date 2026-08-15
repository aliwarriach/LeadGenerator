// Fired the moment the mutation kicks off — this is a synchronous, awaited
// call the user watches complete (see AuditView's "Running…" pending state),
// not a background job, so the copy must not imply queued/async processing.
export const REANALYZE_TOAST = 'Running AI audit now — this can take up to 30 seconds'
export const AUDIT_COMPLETE_TOAST = 'Audit complete — results updated below'
