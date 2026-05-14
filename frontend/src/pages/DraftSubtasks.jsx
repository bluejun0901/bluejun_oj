import { useEffect, useState } from "react";
import { fetchJson } from "../utils/api";
import { blankSubtask, formatSubtaskCases, parseSubtaskCases, sortedSubtasks } from "../utils/problem";
import { AuthGate } from "../components/AuthGate";
import { DraftNav } from "../components/DraftNav";

function toFormData(response) {
  return {
    ...response,
    subtasks: sortedSubtasks(response.subtask_info).map(([id, subtask]) => ({
      id,
      desc: subtask.desc ?? "",
      score: subtask.score ?? 0,
      cases: formatSubtaskCases(subtask.cases),
    })),
  };
}

export function DraftSubtasksPage({ authUser, draftId }) {
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
        const response = await fetchJson(`/drafts/${draftId}/subtasks`);
        if (!cancelled) {
          setData(toFormData(response));
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
      const subtaskInfo = Object.fromEntries(
        data.use_subtask
          ? data.subtasks.filter((item) => item.id.trim()).map((item) => [
              item.id.trim(),
              { desc: item.desc, score: Number(item.score), cases: parseSubtaskCases(item.cases) },
            ])
          : [],
      );
      const saved = await fetchJson(`/drafts/${draftId}/subtasks`, {
        method: "PUT",
        body: JSON.stringify({ use_subtask: data.use_subtask, subtask_info: subtaskInfo }),
      });
      setData(toFormData(saved));
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
          <p className="eyebrow">Draft Subtasks</p>
          <h1>{data?.summary.title || `Draft #${draftId}`}</h1>
        </div>
      </section>
      <DraftNav draftId={draftId} active="subtasks" />
      <section className="panel">
        {loading ? <p className="muted">Loading subtasks...</p> : null}
        {error ? <p className="error">{error}</p> : null}
        {!loading && data ? (
          <div className="problem-form">
            <label className="checkbox-field">
              <input
                type="checkbox"
                checked={data.use_subtask}
                onChange={(event) => setData((current) => ({ ...current, use_subtask: event.target.checked }))}
              />
              <span>Enable subtask judging</span>
            </label>
            {data.use_subtask ? (
              <>
                <div className="inline-actions">
                  <button
                    className="ghost-link ghost-button"
                    type="button"
                    onClick={() => setData((current) => ({ ...current, subtasks: [...current.subtasks, blankSubtask()] }))}
                  >
                    Add subtask
                  </button>
                </div>
                <div className="array-stack">
                  {data.subtasks.map((subtask, index) => (
                    <div className="array-row" key={`subtask-${index + 1}`}>
                      <div className="array-row-header">
                        <strong>{`Subtask ${index + 1}`}</strong>
                        <button
                          className="ghost-link ghost-button"
                          type="button"
                          onClick={() => setData((current) => ({ ...current, subtasks: current.subtasks.filter((_, itemIndex) => itemIndex !== index) }))}
                        >
                          Remove
                        </button>
                      </div>
                      <div className="problem-form-grid">
                        <label className="field">
                          <span className="field-label">ID</span>
                          <input
                            className="text-input"
                            value={subtask.id}
                            onChange={(event) =>
                              setData((current) => ({
                                ...current,
                                subtasks: current.subtasks.map((item, itemIndex) => (itemIndex === index ? { ...item, id: event.target.value } : item)),
                              }))
                            }
                          />
                        </label>
                        <label className="field">
                          <span className="field-label">Score</span>
                          <input
                            className="text-input"
                            type="number"
                            value={subtask.score}
                            onChange={(event) =>
                              setData((current) => ({
                                ...current,
                                subtasks: current.subtasks.map((item, itemIndex) => (itemIndex === index ? { ...item, score: event.target.value } : item)),
                              }))
                            }
                          />
                        </label>
                      </div>
                      <label className="field field-full">
                        <span className="field-label">Description</span>
                        <textarea
                          className="large-textarea"
                          value={subtask.desc}
                          onChange={(event) =>
                            setData((current) => ({
                              ...current,
                              subtasks: current.subtasks.map((item, itemIndex) => (itemIndex === index ? { ...item, desc: event.target.value } : item)),
                            }))
                          }
                        />
                      </label>
                      <label className="field field-full">
                        <span className="field-label">Cases</span>
                        <input
                          className="text-input"
                          value={subtask.cases}
                          onChange={(event) =>
                            setData((current) => ({
                              ...current,
                              subtasks: current.subtasks.map((item, itemIndex) => (itemIndex === index ? { ...item, cases: event.target.value } : item)),
                            }))
                          }
                        />
                      </label>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <p className="muted">Subtask judging is disabled for this draft.</p>
            )}
            <div className="inline-actions">
              <button className="primary-button" type="button" disabled={saving} onClick={handleSave}>
                {saving ? "Saving..." : "Save subtasks"}
              </button>
            </div>
          </div>
        ) : null}
      </section>
    </div>
  );
}
