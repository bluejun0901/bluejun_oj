import { useEffect, useState } from "react";

const API_BASE = "http://localhost:8000";
const FINAL_STATUSES = new Set(["AC", "WA", "TLE", "RE", "CE"]);
const DEFAULT_CPP = `#include <iostream>
using namespace std;

int main() {
    long long a, b;
    if (!(cin >> a >> b)) return 0;
    cout << a + b << "\\n";
    return 0;
}
`;

function normalizeStatus(status) {
  return status === "JUDGING" ? "RUNNING" : status;
}

function getProblemIdFromHash() {
  const match = window.location.hash.match(/^#\/problems\/(\d+)$/);
  return match ? Number(match[1]) : null;
}

async function fetchJson(path, options) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
    },
    ...options,
  });

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;
    try {
      const data = await response.json();
      detail = data.detail || detail;
    } catch {
      // Keep the generic message when the body is not JSON.
    }
    throw new Error(detail);
  }

  return response.json();
}

function ProblemList({ problems, loading, error }) {
  return (
    <section className="panel">
      <div className="panel-header">
        <h1>Problems</h1>
        <p>Choose a problem and submit C++ code.</p>
      </div>

      {loading ? <p className="muted">Loading problems...</p> : null}
      {error ? <p className="error">{error}</p> : null}

      <div className="list">
        {problems.map((problem) => (
          <a key={problem.id} className="list-item" href={`#/problems/${problem.id}`}>
            <span className="list-id">#{problem.id}</span>
            <span>{problem.title}</span>
          </a>
        ))}
      </div>
    </section>
  );
}

function SubmissionCard({ submission }) {
  if (!submission) {
    return null;
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Submission</h2>
        <span className={`status status-${normalizeStatus(submission.status).toLowerCase()}`}>
          {normalizeStatus(submission.status)}
        </span>
      </div>
      <p className="meta">Submission #{submission.id}</p>
      {submission.details ? <pre className="details">{submission.details}</pre> : null}
    </section>
  );
}

function ProblemPage({ problemId, problems, refreshProblems, onBack }) {
  const [problem, setProblem] = useState(() =>
    problems.find((candidate) => candidate.id === problemId) ?? null,
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [sourceCode, setSourceCode] = useState(DEFAULT_CPP);
  const [submitting, setSubmitting] = useState(false);
  const [submissionError, setSubmissionError] = useState("");
  const [submission, setSubmission] = useState(null);

  useEffect(() => {
    let cancelled = false;

    setLoading(true);
    setError("");
    const existingProblem = problems.find((candidate) => candidate.id === problemId) ?? null;
    setProblem(existingProblem);

    if (existingProblem) {
      setLoading(false);
      return () => {
        cancelled = true;
      };
    }

    refreshProblems()
      .then((allProblems) => {
        if (cancelled) {
          return;
        }
        const matchedProblem = allProblems.find((candidate) => candidate.id === problemId) ?? null;
        setProblem(matchedProblem);
        if (!matchedProblem) {
          setError("Problem not found");
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err.message);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [problemId, problems, refreshProblems]);

  useEffect(() => {
    if (!submission || FINAL_STATUSES.has(submission.status)) {
      return undefined;
    }

    const timer = window.setInterval(async () => {
      try {
        const latest = await fetchJson(`/submissions/${submission.id}`);
        setSubmission(latest);
      } catch (err) {
        setSubmission((current) =>
          current
            ? {
                ...current,
                details: `Polling failed: ${err.message}`,
              }
            : current,
        );
      }
    }, 1000);

    return () => window.clearInterval(timer);
  }, [submission]);

  async function handleSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setSubmissionError("");

    try {
      const created = await fetchJson("/submissions", {
        method: "POST",
        body: JSON.stringify({
          problem_id: problemId,
          language: "cpp",
          source_code: sourceCode,
        }),
      });
      setSubmission(created);
    } catch (err) {
      setSubmissionError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="page">
      <button className="back-link" onClick={onBack} type="button">
        ← Back to problems
      </button>

      <section className="panel">
        {loading ? <p className="muted">Loading problem...</p> : null}
        {error ? <p className="error">{error}</p> : null}

        {problem ? (
          <>
            <div className="panel-header">
              <h1>{problem.title}</h1>
              <span className="meta">Problem #{problem.id}</span>
            </div>
            <p className="muted">Language: C++17</p>

            <form className="editor" onSubmit={handleSubmit}>
              <textarea
                value={sourceCode}
                onChange={(event) => setSourceCode(event.target.value)}
                spellCheck="false"
                aria-label="Source code"
              />
              <div className="actions">
                <button className="primary-button" type="submit" disabled={submitting}>
                  {submitting ? "Submitting..." : "Submit"}
                </button>
                {submissionError ? <p className="error inline-error">{submissionError}</p> : null}
              </div>
            </form>
          </>
        ) : null}
      </section>

      <SubmissionCard submission={submission} />
    </div>
  );
}

export default function App() {
  const [problemId, setProblemId] = useState(getProblemIdFromHash());
  const [problems, setProblems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    function handleHashChange() {
      setProblemId(getProblemIdFromHash());
    }

    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  async function loadProblems() {
    setLoading(true);
    setError("");
    try {
      const data = await fetchJson("/problems");
      setProblems(data);
      return data;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let cancelled = false;

    loadProblems().catch(() => {
      if (cancelled) {
        return;
      }
    });

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="app-shell">
      {problemId ? (
        <ProblemPage
          problemId={problemId}
          problems={problems}
          refreshProblems={loadProblems}
          onBack={() => {
            window.location.hash = "";
          }}
        />
      ) : (
        <ProblemList problems={problems} loading={loading} error={error} />
      )}
    </main>
  );
}
