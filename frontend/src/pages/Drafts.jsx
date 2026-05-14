import { useEffect, useState } from "react";
import { fetchJson } from "../utils/api";
import { navigate } from "../utils/router";
import { formatTimestamp } from "../utils/formatters";
import { AuthGate } from "../components/AuthGate";

export function DraftListPage({ authUser }) {
  const [drafts, setDrafts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function loadDrafts() {
      setLoading(true);
      setError("");
      try {
        const data = await fetchJson("/drafts");
        if (!cancelled) {
          setDrafts(data);
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

    if (authUser) {
      loadDrafts().catch(() => undefined);
    }

    return () => {
      cancelled = true;
    };
  }, [authUser]);

  if (!authUser) {
    return <AuthGate />;
  }

  async function handleCreateDraft() {
    setCreating(true);
    setError("");
    try {
      const created = await fetchJson("/drafts", { method: "POST", body: JSON.stringify({}) });
      navigate(`/drafts/${created.id}/statement`);
    } catch (createError) {
      setError(createError.message);
      setCreating(false);
    }
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Authoring</p>
          <h1>My Draft Stack</h1>
        </div>
        <div className="inline-actions">
          <button className="primary-button" type="button" disabled={creating} onClick={handleCreateDraft}>
            {creating ? "Creating..." : "New draft"}
          </button>
        </div>
      </div>

      {loading ? <p className="muted">Loading drafts...</p> : null}
      {error ? <p className="error">{error}</p> : null}
      {!loading && !error && drafts.length === 0 ? (
        <p className="muted">No drafts yet. Create one to start editing before publish.</p>
      ) : null}

      <div className="draft-list">
        {drafts.map((draft) => (
          <article className="draft-card" key={draft.id}>
            <div className="draft-card-main">
              <div className="history-row">
                <strong>{draft.title || `Untitled draft #${draft.id}`}</strong>
                <span className={`status status-${draft.status.toLowerCase()}`}>{draft.status}</span>
              </div>
              <div className="draft-meta">
                <span>slug: {draft.slug || "—"}</span>
                <span>{draft.testcase_count} tests</span>
                <span>{draft.use_subtask ? "subtasks enabled" : "standard judging"}</span>
                <span>{draft.source_problem_id ? `editing problem #${draft.source_problem_id}` : "new problem"}</span>
                <span>updated {formatTimestamp(draft.updated_at)}</span>
              </div>
            </div>
            <div className="inline-actions">
              <button className="ghost-link ghost-button" type="button" onClick={() => navigate(`/drafts/${draft.id}/statement`)}>
                Open
              </button>
              <button className="ghost-link ghost-button" type="button" onClick={() => navigate(`/drafts/${draft.id}/preview`)}>
                Preview
              </button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
