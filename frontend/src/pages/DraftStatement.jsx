import { useEffect, useState } from "react";
import { fetchJson } from "../utils/api";
import { blankExample } from "../utils/problem";
import { AuthGate } from "../components/AuthGate";
import { DraftNav } from "../components/DraftNav";

export function DraftStatementPage({ authUser, draftId }) {
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
        const response = await fetchJson(`/drafts/${draftId}/statement`);
        if (!cancelled) {
          setData({
            ...response,
            examples: response.examples?.length ? response.examples : [blankExample()],
          });
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

  function updateField(field, value) {
    setData((current) => ({ ...current, [field]: value }));
  }

  async function handleSave() {
    setSaving(true);
    setError("");
    try {
      const saved = await fetchJson(`/drafts/${draftId}/statement`, {
        method: "PUT",
        body: JSON.stringify({
          title: data.title,
          slug: data.slug,
          time_limit_ms: Number(data.time_limit_ms),
          memory_limit: Number(data.memory_limit),
          description: data.description,
          input_spec: data.input_spec,
          output_spec: data.output_spec,
          examples: data.examples,
        }),
      });
      setData({ ...saved, examples: saved.examples?.length ? saved.examples : [blankExample()] });
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
          <p className="eyebrow">Draft Statement</p>
          <h1>{data?.summary.title || `Draft #${draftId}`}</h1>
        </div>
      </section>
      <DraftNav draftId={draftId} active="statement" />
      <section className="panel">
        {loading ? <p className="muted">Loading statement...</p> : null}
        {error ? <p className="error">{error}</p> : null}
        {!loading && data ? (
          <div className="problem-form">
            <div className="problem-form-grid">
              <label className="field">
                <span className="field-label">Title</span>
                <input className="text-input" value={data.title} onChange={(event) => updateField("title", event.target.value)} />
              </label>
              <label className="field">
                <span className="field-label">Slug</span>
                <input className="text-input" value={data.slug} onChange={(event) => updateField("slug", event.target.value)} />
              </label>
              <label className="field">
                <span className="field-label">Time limit (ms)</span>
                <input
                  className="text-input"
                  type="number"
                  value={data.time_limit_ms}
                  onChange={(event) => updateField("time_limit_ms", event.target.value)}
                />
              </label>
              <label className="field">
                <span className="field-label">Memory limit (MB)</span>
                <input
                  className="text-input"
                  type="number"
                  value={data.memory_limit}
                  onChange={(event) => updateField("memory_limit", event.target.value)}
                />
              </label>
            </div>
            <label className="field field-full">
              <span className="field-label">Description</span>
              <textarea className="large-textarea" value={data.description} onChange={(event) => updateField("description", event.target.value)} />
            </label>
            <label className="field field-full">
              <span className="field-label">Input spec</span>
              <textarea className="large-textarea" value={data.input_spec} onChange={(event) => updateField("input_spec", event.target.value)} />
            </label>
            <label className="field field-full">
              <span className="field-label">Output spec</span>
              <textarea className="large-textarea" value={data.output_spec} onChange={(event) => updateField("output_spec", event.target.value)} />
            </label>
            <div className="editor-section">
              <div className="panel-header compact-panel-header">
                <div><h2>Examples</h2></div>
                <button
                  className="ghost-link ghost-button"
                  type="button"
                  onClick={() => updateField("examples", [...data.examples, blankExample()])}
                >
                  Add example
                </button>
              </div>
              <div className="array-stack">
                {data.examples.map((example, index) => (
                  <div className="array-row" key={`example-${index + 1}`}>
                    <div className="array-row-header">
                      <strong>{`Example ${index + 1}`}</strong>
                      <button
                        className="ghost-link ghost-button"
                        type="button"
                        onClick={() => updateField("examples", data.examples.filter((_, itemIndex) => itemIndex !== index))}
                      >
                        Remove
                      </button>
                    </div>
                    <div className="split-grid">
                      <label className="field field-full">
                        <span className="field-label">Input</span>
                        <textarea
                          className="code-textarea"
                          value={example.input}
                          onChange={(event) =>
                            updateField(
                              "examples",
                              data.examples.map((item, itemIndex) => (itemIndex === index ? { ...item, input: event.target.value } : item)),
                            )
                          }
                        />
                      </label>
                      <label className="field field-full">
                        <span className="field-label">Output</span>
                        <textarea
                          className="code-textarea"
                          value={example.output}
                          onChange={(event) =>
                            updateField(
                              "examples",
                              data.examples.map((item, itemIndex) => (itemIndex === index ? { ...item, output: event.target.value } : item)),
                            )
                          }
                        />
                      </label>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            <div className="inline-actions">
              <button className="primary-button" type="button" disabled={saving} onClick={handleSave}>
                {saving ? "Saving..." : "Save statement"}
              </button>
            </div>
          </div>
        ) : null}
      </section>
    </div>
  );
}
