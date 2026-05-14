import { useEffect, useState } from "react";
import { fetchJson } from "../utils/api";
import { navigate } from "../utils/router";
import { AuthGate } from "../components/AuthGate";

export function DraftNewPage({ authUser }) {
  const [error, setError] = useState("");

  useEffect(() => {
    if (!authUser) {
      return undefined;
    }
    let cancelled = false;
    async function createDraft() {
      try {
        const draft = await fetchJson("/drafts", { method: "POST", body: JSON.stringify({}) });
        if (!cancelled) {
          navigate(`/drafts/${draft.id}/statement`);
        }
      } catch (createError) {
        if (!cancelled) {
          setError(createError.message);
        }
      }
    }
    createDraft().catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [authUser]);

  if (!authUser) {
    return <AuthGate />;
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Authoring</p>
          <h1>Create Draft</h1>
        </div>
      </div>
      {error ? <p className="error">{error}</p> : <p className="muted">Creating draft...</p>}
    </section>
  );
}
