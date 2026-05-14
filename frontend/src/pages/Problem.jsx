import { useEffect, useMemo, useState } from "react";
import { fetchJson } from "../utils/api";
import { navigate } from "../utils/router";
import { formatExecutionTime, formatMemoryUsage, formatScore, formatTimestamp } from "../utils/formatters";
import { SubmissionCard } from "../components/SubmissionCard";
import { AuthGate } from "../components/AuthGate";
import { TabLink } from "../components/TabLink";
import { ProblemStatementView } from "../components/ProblemStatementView";
import { FINAL_STATUSES } from "../constants";

function StatementTab({ problem, authUser }) {
  const [creatingDraft, setCreatingDraft] = useState(false);
  const [error, setError] = useState("");

  const canCreateDraft = authUser && (authUser.role === "admin" || problem.author?.id === authUser.id);

  async function handleCreateEditDraft() {
    setCreatingDraft(true);
    setError("");
    try {
      const draft = await fetchJson(`/problems/${problem.id}/drafts`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      navigate(`/drafts/${draft.id}/statement`);
    } catch (createError) {
      setError(createError.message);
      setCreatingDraft(false);
    }
  }

  return (
    <>
      <ProblemStatementView
        problem={problem}
        action={
          canCreateDraft ? (
            <button className="ghost-link ghost-button" type="button" disabled={creatingDraft} onClick={handleCreateEditDraft}>
              {creatingDraft ? "Creating draft..." : "Create edit draft"}
            </button>
          ) : null
        }
      />
      {error ? (
        <section className="panel">
          <p className="error">{error}</p>
        </section>
      ) : null}
    </>
  );
}

function SubmitTab({ authUser, problemId, languages, latestSubmission, onSubmissionChange }) {
  const [language, setLanguage] = useState(languages[0]?.key ?? "");
  const [drafts, setDrafts] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [submissionError, setSubmissionError] = useState("");

  useEffect(() => {
    const nextDrafts = Object.fromEntries(languages.map((entry) => [entry.key, entry.default_source]));
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

  if (!authUser) {
    return <AuthGate />;
  }

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
      navigate(`/problems/${problemId}/submissions`);
    } catch (error) {
      if (error.status === 401) {
        navigate("/login");
        return;
      }
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
            <button className="primary-button" type="submit" disabled={submitting || !language}>
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
      {!loading && !error && submissions.length === 0 ? <p className="muted">No submissions yet.</p> : null}

      <div className="history-list">
        {submissions.map((submission) => (
          <article key={submission.id} className="history-item">
            <div className="history-main">
              <div className="history-row">
                <strong>#{submission.id}</strong>
                <span className="history-row-muted">
                  {submission.user ? `@${submission.user.username}` : "unknown"}
                  {submission.is_mine ? " · you" : ""}
                </span>
                <span className={`status status-${submission.status.toLowerCase()}`}>
                  {submission.status}
                </span>
              </div>
              <div className="history-row history-row-muted">
                <span>{submission.language}</span>
                <span>{formatScore(submission.score, submission.max_score) ?? "—"}</span>
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

export function ProblemPage({ authUser, problemId, tab }) {
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
      <section className="problem-hero">
        <div>
          <p className="eyebrow">Problem #{problemId}</p>
          <h1>{problem?.title ?? "Loading problem..."}</h1>
        </div>
        {problem ? (
          <div className="hero-meta">
            <p className="muted">
              {problem.testcase_count} testcases · {problem.time_limit_ms} ms · {problem.memory_limit} MB
            </p>
            {problem.author ? <p className="muted">Author: @{problem.author.username}</p> : null}
          </div>
        ) : null}
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

      {loading ? (
        <section className="panel">
          <p className="muted">Loading problem...</p>
        </section>
      ) : null}
      {error ? (
        <section className="panel">
          <p className="error">{error}</p>
        </section>
      ) : null}

      {!loading && !error && problem && tab === "statement" ? <StatementTab problem={problem} authUser={authUser} /> : null}
      {!loading && !error && problem && tab === "submit" ? (
        <SubmitTab
          authUser={authUser}
          problemId={problemId}
          languages={languages}
          latestSubmission={latestSubmission}
          onSubmissionChange={setLatestSubmission}
        />
      ) : null}
      {!loading && !error && problem && tab === "submissions" ? <SubmissionHistoryTab problemId={problemId} /> : null}
    </div>
  );
}
