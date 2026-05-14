import { useEffect, useState } from "react";
import { fetchJson } from "../utils/api";
import { AuthGate } from "../components/AuthGate";
import { DraftNav } from "../components/DraftNav";

export function DraftCheckerPage({ authUser, draftId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!authUser) {
      return undefined;
    }
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError("");
      try {
        const response = await fetchJson(`/drafts/${draftId}/checker`);
        if (!cancelled) {
          setData(response);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError.message);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }
    load().catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [authUser, draftId]);

  if (!authUser) {
    return <AuthGate />;
  }

  async function handleSave() {
    setSaving(true);
    setError("");
    try {
      const saved = await fetchJson(`/drafts/${draftId}/checker`, {
        method: "PUT",
        body: JSON.stringify({ checker_source: data.checker_source }),
      });
      setData(saved);
    } catch (saveError) {
      setError(saveError.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="page">
      <section className="problem-hero">
        <div>
          <p className="eyebrow">Draft Checker</p>
          <h1>{data?.summary.title || `Draft #${draftId}`}</h1>
        </div>
      </section>
      <DraftNav draftId={draftId} active="checker" />
      <section className="panel">
        {loading ? <p className="muted">Loading checker...</p> : null}
        {error ? <p className="error">{error}</p> : null}
        {!loading && data ? (
          <div className="problem-form">
            <p className="muted">Stored at {data.checker_source_path || "not written yet"}.</p>
            <label className="field field-full">
              <span className="field-label">checker.cpp</span>
              <textarea
                className="editor-code-textarea"
                value={data.checker_source}
                onChange={(event) => setData((current) => ({ ...current, checker_source: event.target.value }))}
              />
            </label>
            <div className="inline-actions">
              <button className="primary-button" type="button" disabled={saving} onClick={handleSave}>
                {saving ? "Saving..." : "Save checker"}
              </button>
            </div>
          </div>
        ) : null}
      </section>
    </div>
  );
}
