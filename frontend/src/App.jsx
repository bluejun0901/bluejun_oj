import { useEffect, useMemo, useState } from "react";

const API_BASE = "/api";
const FINAL_STATUSES = new Set(["AC", "WA", "TLE", "RE", "CE", "MLE"]);

function normalizeStatus(status) {
  return status === "JUDGING" ? "RUNNING" : status;
}

function parseRoute(pathname) {
  if (pathname === "/") {
    return { name: "home" };
  }

  const match = pathname.match(/^\/problems\/(\d+)(?:\/(submit|submissions))?\/?$/);
  if (!match) {
    return { name: "not-found" };
  }

  return {
    name: "problem",
    problemId: Number(match[1]),
    tab: match[2] ?? "statement",
  };
}

function navigate(pathname) {
  if (window.location.pathname === pathname) {
    return;
  }
  window.history.pushState({}, "", pathname);
  window.dispatchEvent(new PopStateEvent("popstate"));
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
      // Ignore non-JSON error bodies.
    }
    throw new Error(detail);
  }

  return response.json();
}

function formatTimestamp(value) {
  return new Date(value).toLocaleString();
}

function formatExecutionTime(value) {
  if (typeof value !== "number") {
    return "—";
  }
  return `${value} ms`;
}

function formatMemoryUsage(value) {
  if (typeof value !== "number") {
    return "—";
  }
  return `${value} KB`;
}

function TabLink({ active, children, href }) {
  return (
    <a
      className={`tab-link ${active ? "tab-link-active" : ""}`}
      href={href}
      onClick={(event) => {
        event.preventDefault();
        navigate(href);
      }}
    >
      {children}
    </a>
  );
}

function ProblemList({ problems, loading, error }) {
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Minimal OJ</p>
          <h1>Problems</h1>
        </div>
        <p className="muted">Pick a problem and move between statement, submit, and history.</p>
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
              navigate(`/problems/${problem.id}`);
            }}
          >
            <span className="list-id">#{problem.id}</span>
            <span className="list-main">
              <strong>{problem.title}</strong>
              <span className="muted">
                {problem.testcase_count} tests · {problem.time_limit_ms} ms
              </span>
            </span>
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
        <div>
          <p className="eyebrow">Latest Result</p>
          <h2>Submission #{submission.id}</h2>
        </div>
        <span className={`status status-${normalizeStatus(submission.status).toLowerCase()}`}>
          {normalizeStatus(submission.status)}
        </span>
      </div>
      <div className="submission-meta-grid">
        <p className="meta">Language: {submission.language}</p>
        <p className="meta">Execution: {formatExecutionTime(submission.execution_time_ms)}</p>
        <p className="meta">Memory: {formatMemoryUsage(submission.memory_usage_kb)}</p>
        <p className="meta">Submitted: {formatTimestamp(submission.created_at)}</p>
      </div>
      {submission.details ? <pre className="details">{submission.details}</pre> : null}
    </section>
  );
}

function StatementTab({ problem }) {
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Statement</p>
          <h2>{problem.title}</h2>
        </div>
        <p className="meta">{problem.time_limit_ms} ms time limit</p>
      </div>

      <div className="statement-grid">
        <section className="statement-section">
          <h3>Description</h3>
          <p>{problem.description || "No description provided."}</p>
        </section>
        <section className="statement-section">
          <h3>Input</h3>
          <p>{problem.input_spec || "No input specification provided."}</p>
        </section>
        <section className="statement-section">
          <h3>Output</h3>
          <p>{problem.output_spec || "No output specification provided."}</p>
        </section>
        <section className="statement-section">
          <h3>Example</h3>
          <div className="example-grid">
            <div className="example-box">
              <span className="example-label">Input</span>
              <pre>{problem.example_input || "—"}</pre>
            </div>
            <div className="example-box">
              <span className="example-label">Output</span>
              <pre>{problem.example_output || "—"}</pre>
            </div>
          </div>
        </section>
      </div>
    </section>
  );
}

function SubmitTab({ problemId, languages, latestSubmission, onSubmissionChange }) {
  const firstLanguage = languages[0]?.key ?? "";
  const [language, setLanguage] = useState(firstLanguage);
  const [drafts, setDrafts] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [submissionError, setSubmissionError] = useState("");

  useEffect(() => {
    const nextDrafts = Object.fromEntries(
      languages.map((entry) => [entry.key, entry.default_source]),
    );
    setLanguage(languages[0]?.key ?? "");
    setDrafts(nextDrafts);
    setSubmissionError("");
  }, [languages, problemId]);

  useEffect(() => {
    if (!latestSubmission || FINAL_STATUSES.has(latestSubmission.status)) {
      return undefined;
    }

    const timer = window.setInterval(async () => {
      try {
        const nextSubmission = await fetchJson(`/submissions/${latestSubmission.id}`);
        onSubmissionChange(nextSubmission);
      } catch (error) {
        onSubmissionChange((current) =>
          current
            ? {
                ...current,
                details: `Polling failed: ${error.message}`,
              }
            : current,
        );
      }
    }, 1000);

    return () => window.clearInterval(timer);
  }, [latestSubmission, onSubmissionChange]);

  async function handleSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setSubmissionError("");

    try {
      const created = await fetchJson("/submissions", {
        method: "POST",
        body: JSON.stringify({
          problem_id: problemId,
          language,
          source_code: drafts[language],
        }),
      });
      onSubmissionChange(created);
    } catch (error) {
      setSubmissionError(error.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <section className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Submit</p>
            <h2>Source Code</h2>
          </div>
          <p className="muted">Choose a language and send the solution to the judge.</p>
        </div>

        <form className="editor" onSubmit={handleSubmit}>
          <label className="field">
            <span className="field-label">Language</span>
            <select
              className="select"
              value={language}
              disabled={languages.length === 0}
              onChange={(event) => setLanguage(event.target.value)}
            >
              {languages.map((option) => (
                <option key={option.key} value={option.key}>
                  {option.display_name}
                </option>
              ))}
            </select>
          </label>

          <textarea
            value={drafts[language] ?? ""}
            onChange={(event) =>
              setDrafts((current) => ({
                ...current,
                [language]: event.target.value,
              }))
            }
            spellCheck="false"
            aria-label="Source code"
            data-language={language}
          />

          <div className="actions">
            <button
              className="primary-button"
              type="submit"
              disabled={submitting || !language}
            >
              {submitting ? "Submitting..." : "Submit"}
            </button>
            {submissionError ? <p className="error inline-error">{submissionError}</p> : null}
          </div>
        </form>
      </section>

      <SubmissionCard submission={latestSubmission} />
    </>
  );
}

function SubmissionHistoryTab({ problemId }) {
  const [submissions, setSubmissions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadSubmissions() {
      setLoading(true);
      setError("");
      try {
        const data = await fetchJson(`/problems/${problemId}/submissions`);
        if (!cancelled) {
          setSubmissions(data);
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

    loadSubmissions().catch(() => undefined);

    return () => {
      cancelled = true;
    };
  }, [problemId]);

  const hasPendingSubmission = useMemo(
    () => submissions.some((submission) => !FINAL_STATUSES.has(submission.status)),
    [submissions],
  );

  useEffect(() => {
    if (!hasPendingSubmission) {
      return undefined;
    }

    const timer = window.setInterval(async () => {
      try {
        const data = await fetchJson(`/problems/${problemId}/submissions`);
        setSubmissions(data);
      } catch {
        // Keep the current list while polling.
      }
    }, 1200);

    return () => window.clearInterval(timer);
  }, [hasPendingSubmission, problemId]);

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">History</p>
          <h2>Submission History</h2>
        </div>
        <p className="muted">Newest submissions appear first.</p>
      </div>

      {loading ? <p className="muted">Loading submissions...</p> : null}
      {error ? <p className="error">{error}</p> : null}
      {!loading && !error && submissions.length === 0 ? (
        <p className="muted">No submissions yet.</p>
      ) : null}

      <div className="history-list">
        {submissions.map((submission) => (
          <article key={submission.id} className="history-item">
            <div className="history-main">
              <div className="history-row">
                <strong>#{submission.id}</strong>
                <span className={`status status-${normalizeStatus(submission.status).toLowerCase()}`}>
                  {normalizeStatus(submission.status)}
                </span>
              </div>
              <div className="history-row history-row-muted">
                <span>{submission.language}</span>
                <span>{formatExecutionTime(submission.execution_time_ms)}</span>
                <span>{formatMemoryUsage(submission.memory_usage_kb)}</span>
                <span>{formatTimestamp(submission.created_at)}</span>
              </div>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function ProblemShell({ problemId, tab }) {
  const [problem, setProblem] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [latestSubmission, setLatestSubmission] = useState(null);
  const [languages, setLanguages] = useState([]);

  useEffect(() => {
    let cancelled = false;

    async function loadProblem() {
      setLoading(true);
      setError("");
      try {
        const data = await fetchJson(`/problems/${problemId}`);
        if (!cancelled) {
          setProblem(data);
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

    loadProblem().catch(() => undefined);

    return () => {
      cancelled = true;
    };
  }, [problemId]);

  useEffect(() => {
    let cancelled = false;

    async function loadLanguages() {
      try {
        const data = await fetchJson("/languages");
        if (!cancelled) {
          setLanguages(data);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError.message);
        }
      }
    }

    loadLanguages().catch(() => undefined);

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="page">
      <button className="back-link" onClick={() => navigate("/")} type="button">
        ← Back to problems
      </button>

      <section className="problem-hero">
        <div>
          <p className="eyebrow">Problem #{problemId}</p>
          <h1>{problem?.title ?? "Loading problem..."}</h1>
        </div>
        {problem ? <p className="muted">{problem.testcase_count} testcases</p> : null}
      </section>

      <nav className="tabs" aria-label="Problem navigation">
        <TabLink active={tab === "statement"} href={`/problems/${problemId}`}>
          statement
        </TabLink>
        <TabLink active={tab === "submit"} href={`/problems/${problemId}/submit`}>
          submit
        </TabLink>
        <TabLink active={tab === "submissions"} href={`/problems/${problemId}/submissions`}>
          submission history
        </TabLink>
      </nav>

      {loading ? <section className="panel"><p className="muted">Loading problem...</p></section> : null}
      {error ? <section className="panel"><p className="error">{error}</p></section> : null}

      {!loading && !error && problem && tab === "statement" ? <StatementTab problem={problem} /> : null}
      {!loading && !error && problem && tab === "submit" ? (
        <SubmitTab
          problemId={problemId}
          languages={languages}
          latestSubmission={latestSubmission}
          onSubmissionChange={setLatestSubmission}
        />
      ) : null}
      {!loading && !error && problem && tab === "submissions" ? (
        <SubmissionHistoryTab problemId={problemId} />
      ) : null}
    </div>
  );
}

function NotFound() {
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">404</p>
          <h1>Page not found</h1>
        </div>
      </div>
      <button className="primary-button" type="button" onClick={() => navigate("/")}>
        Go to problems
      </button>
    </section>
  );
}

export default function App() {
  const [route, setRoute] = useState(() => parseRoute(window.location.pathname));
  const [problems, setProblems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    function handleNavigation() {
      setRoute(parseRoute(window.location.pathname));
    }

    window.addEventListener("popstate", handleNavigation);
    return () => window.removeEventListener("popstate", handleNavigation);
  }, []);

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

  return (
    <main className="app-shell">
      {route.name === "home" ? (
        <ProblemList problems={problems} loading={loading} error={error} />
      ) : null}
      {route.name === "problem" ? (
        <ProblemShell problemId={route.problemId} tab={route.tab} />
      ) : null}
      {route.name === "not-found" ? <NotFound /> : null}
    </main>
  );
}
