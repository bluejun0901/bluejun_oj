import { useEffect, useState } from "react";
import { fetchJson } from "../utils/api";
import { navigate } from "../utils/router";
import { AuthGate } from "../components/AuthGate";
import { DraftNav } from "../components/DraftNav";

export function DraftTestcaseDetailPage({ authUser, draftId, testcaseId }) {
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
        const response = await fetchJson(`/drafts/${draftId}/testcases/${testcaseId}`);
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
  }, [authUser, draftId, testcaseId]);

  if (!authUser) {
    return <AuthGate />;
  }

  async function handleSave() {
    setSaving(true);
    setError("");
    try {
      const saved = await fetchJson(`/drafts/${draftId}/testcases/${testcaseId}`, {
        method: "PUT",
        body: JSON.stringify({
          name: data.name,
          input: data.input,
          output: data.output,
        }),
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
          <p className="eyebrow">Draft Testcase Detail</p>
          <h1>{data?.name || `Testcase #${testcaseId}`}</h1>
        </div>
      </section>
      <DraftNav draftId={draftId} active="testcases" />
      <section className="panel">
        <div className="inline-actions">
          <button className="ghost-link ghost-button" type="button" onClick={() => navigate(`/drafts/${draftId}/testcases`)}>
            Back to testcase list
          </button>
        </div>
        {loading ? <p className="muted">Loading testcase...</p> : null}
        {error ? <p className="error">{error}</p> : null}
        {!loading && data ? (
          <div className="problem-form">
            <label className="field field-full">
              <span className="field-label">Name</span>
              <input className="text-input" value={data.name} onChange={(event) => setData((current) => ({ ...current, name: event.target.value }))} />
            </label>
            <div className="draft-meta">
              <span>Input path: {data.input_path}</span>
              <span>Output path: {data.output_path}</span>
            </div>
            <div className="split-grid">
              <label className="field field-full">
                <span className="field-label">Input</span>
                <textarea className="editor-code-textarea" value={data.input} onChange={(event) => setData((current) => ({ ...current, input: event.target.value }))} />
              </label>
              <label className="field field-full">
                <span className="field-label">Output</span>
                <textarea className="editor-code-textarea" value={data.output} onChange={(event) => setData((current) => ({ ...current, output: event.target.value }))} />
              </label>
            </div>
            <div className="inline-actions">
              <button className="primary-button" type="button" disabled={saving} onClick={handleSave}>
                {saving ? "Saving..." : "Save testcase"}
              </button>
            </div>
          </div>
        ) : null}
      </section>
    </div>
  );
}
