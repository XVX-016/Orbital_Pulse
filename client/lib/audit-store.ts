/**
 * Audit trace hand-off between /analyze and /audit.
 *
 * PS-26167 requires the Auditable Execution Trace to remain available, but it
 * no longer belongs in the Analyze results panel.  The trace therefore lives on
 * its own /audit route, and the two pages hand records over through
 * sessionStorage rather than a shared provider — a full page reload of /audit
 * (or opening it in a new tab) still shows the run the operator just executed.
 *
 * sessionStorage is per-tab and cleared when the tab closes, which matches the
 * lifetime of an analysis session.  Every read and write is guarded: Safari in
 * private mode throws on access rather than returning null.
 */

export interface AuditRecord {
  /** Millisecond epoch — also the record's identity in the list. */
  timestamp: number;
  query: string;
  task: string;
  specialistUsed: string;
  parameters: Record<string, unknown>;
  dataSource?: string;
  dataWarnings?: string[];
  answer?: string;
  narrative?: string;
}

const STORAGE_KEY = "satquery.auditTrail";
const MAX_RECORDS = 25;

/** Notifies listeners in the same tab; the native `storage` event does not fire on self. */
const CHANGE_EVENT = "satquery:audit-updated";

function safeRead(): AuditRecord[] {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as AuditRecord[]) : [];
  } catch {
    // Private mode, disabled storage, or corrupt JSON — an empty trail is a
    // correct render, so never let this throw into the component tree.
    return [];
  }
}

function safeWrite(records: AuditRecord[]): void {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(records));
  } catch {
    /* Quota or private mode — the in-page trail simply will not persist. */
  }
}

export function getAuditTrail(): AuditRecord[] {
  return safeRead();
}

export function getLatestAudit(): AuditRecord | null {
  return safeRead()[0] ?? null;
}

/** Prepend a record, keeping the trail bounded. */
export function recordAudit(record: AuditRecord): void {
  const next = [record, ...safeRead()].slice(0, MAX_RECORDS);
  safeWrite(next);
  try {
    window.dispatchEvent(new CustomEvent(CHANGE_EVENT));
  } catch {
    /* Non-browser context (SSR, tests) — nothing is listening anyway. */
  }
}

export function clearAuditTrail(): void {
  try {
    sessionStorage.removeItem(STORAGE_KEY);
    window.dispatchEvent(new CustomEvent(CHANGE_EVENT));
  } catch {
    /* no-op */
  }
}

/** Subscribe to trail changes from this tab. Returns an unsubscribe function. */
export function onAuditChange(handler: () => void): () => void {
  window.addEventListener(CHANGE_EVENT, handler);
  return () => window.removeEventListener(CHANGE_EVENT, handler);
}
