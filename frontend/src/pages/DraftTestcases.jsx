import { useEffect, useState } from "react";
import { fetchJson } from "../utils/api";
import { navigate } from "../utils/router";
import { AuthGate } from "../components/AuthGate";
import { DraftNav } from "../components/DraftNav";

export function DraftTestcasesPage({ authUser, draftId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
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
        const response = await fetchJson(`/drafts/${draftId}/testcases`);
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

  async function handleUpload(event) {
    const files = Array.from(event.target.files ?? []);
    if (files.length === 0) {
      return;
    }
    setUploading(true);
    setError("");
    try {
      const formData = new FormData();
      files.forEach((file) => formData.append("files", file));
      const response = await fetchJson(`/drafts/${draftId}/testcases/import`, {
        method: "POST",
        body: formData,
      });
      setData(response);
      event.target.value = "";
    } catch (uploadError) {
      setError(uploadError.message);
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="page">
      <section className="problem-hero">
        <div>
          <p className="eyebrow">Draft Testcases</p>
          <h1>{data?.summary.title || `Draft #${draftId}`}</h1>
        </div>
      </section>
      <DraftNav draftId={draftId} active="testcases" />
      <section className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Testcase Inventory</p>
            <h2>Testcases</h2>
          </div>
          <label className="ghost-link ghost-button upload-button">
            {uploading ? "Uploading..." : "Upload files"}
            <input type="file" multiple className="hidden-file-input" onChange={handleUpload} />
          </label>
        </div>
        <p className="muted">Upload paired files like `sample.in` + `sample.out` or `1` + `1.a`.</p>
        {loading ? <p className="muted">Loading testcases...</p> : null}
        {error ? <p className="error">{error}</p> : null}
        {!loading && data && data.items.length === 0 ? <p className="muted">No testcases uploaded yet.</p> : null}
        <div className="draft-list">
          {data?.items.map((testcase) => (
            <article className="draft-card" key={testcase.id}>
              <div className="draft-card-main">
                <strong>{testcase.name || `Testcase ${testcase.order_index}`}</strong>
                <div className="draft-meta">
                  <span>order {testcase.order_index}</span>
                </div>
              </div>
              <div className="inline-actions">
                <button
                  className="ghost-link ghost-button"
                  type="button"
                  onClick={() => navigate(`/drafts/${draftId}/testcases/${testcase.id}`)}
                >
                  Open
                </button>
              </div>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
