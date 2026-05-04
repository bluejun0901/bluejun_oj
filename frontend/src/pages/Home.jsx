import { useEffect, useState } from "react";
import { fetchJson } from "../utils/api";

export function ProblemList({ problems, loading, error }) {
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Minimal OJ</p>
          <h1>Problems</h1>
        </div>
        <p className="muted">How should I explain</p>
      </div>

      {loading ? <p className="muted">Loading problems...</p> : null}
      {error ? <p className="error">{error}</p> : null}

      <div className="list">
        {problems.map((problem) => (
          <a
            key={problem.id}
            className="list-item"
            href={`/problems/${problem.id}`}
            onClick={(event) => {
              event.preventDefault();
              window.history.pushState({}, "", `/problems/${problem.id}`);
              window.dispatchEvent(new PopStateEvent("popstate"));
            }}
          >
            <span className="list-id">#{problem.id}</span>
            <span className="list-main">
              <strong>{problem.title}</strong>
              <span className="muted">
                {problem.author ? `by @${problem.author.username} · ` : ""}
                {problem.testcase_count} tests · {problem.time_limit_ms} ms
              </span>
            </span>
          </a>
        ))}
      </div>
    </section>
  );
}

export function HomePage() {
  const [problems, setProblems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadProblems() {
      setLoading(true);
      setError("");
      try {
        const data = await fetchJson("/problems");
        if (!cancelled) {
          setProblems(data);
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

    loadProblems().catch(() => undefined);

    return () => {
      cancelled = true;
    };
  }, []);

  return <ProblemList problems={problems} loading={loading} error={error} />;
}
