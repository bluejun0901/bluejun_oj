import { useEffect, useState } from "react";
import { fetchJson } from "../utils/api";
import { navigate } from "../utils/router";
import { AuthGate } from "../components/AuthGate";
import { DraftNav } from "../components/DraftNav";
import { ProblemStatementView } from "../components/ProblemStatementView";

export function DraftPreviewPage({ authUser, draftId }) {
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [publishing, setPublishing] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!authUser) {
      return undefined;
    }

    let cancelled = false;

    async function loadPreview() {
      setLoading(true);
      setError("");
      try {
        const data = await fetchJson(`/drafts/${draftId}/preview`, { method: "POST" });
        if (!cancelled) {
          setPreview(data);
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

    loadPreview().catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [authUser, draftId]);

  if (!authUser) {
    return <AuthGate />;
  }

  async function handlePublish() {
    setPublishing(true);
    setError("");
    try {
      const published = await fetchJson(`/drafts/${draftId}/publish`, { method: "POST" });
      navigate(`/problems/${published.id}`);
    } catch (publishError) {
      setError(publishError.message);
      setPublishing(false);
    }
  }

  return (
    <div className="page">
      <section className="problem-hero">
        <div>
          <p className="eyebrow">Draft Preview</p>
          <h1>{preview?.draft.title || `Draft #${draftId}`}</h1>
        </div>
        <div className="hero-meta">
          <p className="muted">Preview mode uses the same statement renderer as published problems.</p>
        </div>
      </section>
      <DraftNav draftId={draftId} active="preview" />

      {loading ? (
        <section className="panel">
          <p className="muted">Building preview...</p>
        </section>
      ) : null}

      {error ? (
        <section className="panel">
          <p className="error">{error}</p>
        </section>
      ) : null}

      {!loading && !error && preview ? (
        <>
          <ProblemStatementView
            problem={preview.problem}
            eyebrow="Preview"
            banner={
              <div className="preview-banner">
                <span className={`status status-${preview.checker_compiles ? "ac" : "wa"}`}>
                  {preview.checker_compiles ? "checker compiles" : "checker compile failed"}
                </span>
                <p className="meta">This draft is not public yet. Submit is disabled until publish.</p>
              </div>
            }
            footer={
              <>
                <button className="primary-button" type="button" disabled={publishing} onClick={handlePublish}>
                  {publishing ? "Publishing..." : "Publish"}
                </button>
                <button className="ghost-link ghost-button" type="button" onClick={() => navigate(`/drafts/${draftId}/statement`)}>
                  Back to statement
                </button>
              </>
            }
          />

          <section className="panel">
            <div className="panel-header">
              <div>
                <p className="eyebrow">Validation</p>
                <h2>Publish Checks</h2>
              </div>
            </div>
            {preview.checker_error ? <pre className="details">{preview.checker_error}</pre> : null}
            <div className="validation-list">
              {preview.validations.length ? (
                preview.validations.map((item) => (
                  <article key={`${item.code}-${item.message}`} className={`validation-item validation-${item.level}`}>
                    <strong>{item.level.toUpperCase()}</strong>
                    <span>{item.message}</span>
                  </article>
                ))
              ) : (
                <p className="muted">No validation warnings. Draft is ready to publish.</p>
              )}
            </div>
          </section>
        </>
      ) : null}
    </div>
  );
}
