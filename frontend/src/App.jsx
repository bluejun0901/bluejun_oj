import { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkMath from "remark-math";
import "katex/dist/katex.min.css";

const API_BASE = "/api";
const FINAL_STATUSES = new Set(["AC", "PAC", "WA", "TLE", "RE", "CE", "MLE"]);
const DEFAULT_PROBLEM_FORM = {
  title: "",
  slug: "",
  time_limit_ms: 1000,
  memory_limit: 256,
  description: "",
  input_spec: "",
  output_spec: "",
  examples: JSON.stringify([{ input: "", output: "" }], null, 2),
  use_subtask: false,
  subtask_info: JSON.stringify({}, null, 2),
  checker_source_path: "",
  testcases: JSON.stringify([{ input: "", output: "" }], null, 2),
};

function parseRoute(pathname) {
  if (pathname === "/") {
    return { name: "home" };
  }
  if (pathname === "/login") {
    return { name: "login" };
  }
  if (pathname === "/register") {
    return { name: "register" };
  }
  if (pathname === "/problems/new") {
    return { name: "problem-editor", mode: "create" };
  }

  const editorMatch = pathname.match(/^\/problems\/(\d+)\/edit\/?$/);
  if (editorMatch) {
    return { name: "problem-editor", mode: "edit", problemId: Number(editorMatch[1]) };
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

function readCookie(name) {
  const prefix = `${name}=`;
  return document.cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(prefix))
    ?.slice(prefix.length) ?? "";
}

async function fetchJson(path, options = {}) {
  const method = options.method ?? "GET";
  const headers = new Headers(options.headers ?? {});

  if (!headers.has("Content-Type") && method !== "GET" && method !== "HEAD") {
    headers.set("Content-Type", "application/json");
  }

  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const csrfToken = readCookie("oj_csrf");
    if (csrfToken) {
      headers.set("X-CSRF-Token", csrfToken);
    }
  }

  const response = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    ...options,
    headers,
  });

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;
    try {
      const data = await response.json();
      detail = data.detail || detail;
    } catch {
      // Ignore non-JSON responses.
    }
    const error = new Error(detail);
    error.status = response.status;
    throw error;
  }

  if (response.status === 204) {
    return null;
  }
  return response.json();
}

function formatTimestamp(value) {
  return new Date(value).toLocaleString();
}

function formatExecutionTime(value) {
  return typeof value === "number" ? `${value} ms` : "—";
}

function formatMemoryUsage(value) {
  return typeof value === "number" ? `${value} KB` : "—";
}

function formatScore(score, maxScore) {
  if (typeof score !== "number" || typeof maxScore !== "number") {
    return null;
  }
  return `${score}/${maxScore}`;
}

function sortedSubtasks(subtaskInfo) {
  return Object.entries(subtaskInfo ?? {}).sort(([left], [right]) => {
    const leftNumber = Number(left);
    const rightNumber = Number(right);
    if (Number.isFinite(leftNumber) && Number.isFinite(rightNumber)) {
      return leftNumber - rightNumber;
    }
    return left.localeCompare(right);
  });
}

function toProblemForm(problem) {
  return {
    title: problem.title,
    slug: problem.slug,
    time_limit_ms: problem.time_limit_ms,
    memory_limit: problem.memory_limit,
    description: problem.description ?? "",
    input_spec: problem.input_spec ?? "",
    output_spec: problem.output_spec ?? "",
    examples: JSON.stringify(problem.examples ?? [], null, 2),
    use_subtask: Boolean(problem.use_subtask),
    subtask_info: JSON.stringify(problem.subtask_info ?? {}, null, 2),
    checker_source_path: problem.checker_source_path ?? "",
    testcases: JSON.stringify(problem.testcases ?? [], null, 2),
  };
}

function parseStructuredField(label, value, fallback) {
  if (!value.trim()) {
    return fallback;
  }
  try {
    return JSON.parse(value);
  } catch {
    throw new Error(`${label} must be valid JSON`);
  }
}

function buildProblemPayload(form) {
  return {
    title: form.title.trim(),
    slug: form.slug.trim(),
    time_limit_ms: Number(form.time_limit_ms),
    memory_limit: Number(form.memory_limit),
    description: form.description,
    input_spec: form.input_spec,
    output_spec: form.output_spec,
    examples: parseStructuredField("Examples", form.examples, []),
    use_subtask: form.use_subtask,
    subtask_info: parseStructuredField("Subtask info", form.subtask_info, {}),
    checker_source_path: form.checker_source_path.trim() || null,
    testcases: parseStructuredField("Testcases", form.testcases, []),
  };
}

function canEditProblem(problem, authUser) {
  if (!problem || !authUser) {
    return false;
  }
  return authUser.role === "admin" || problem.author?.id === authUser.id;
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

function HeaderLink({ href, children, primary = false }) {
  return (
    <a
      className={primary ? "primary-button compact-button" : "ghost-link"}
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

function SiteHeader({ authUser, authLoading, onLogout }) {
  return (
    <header className="site-header">
      <button className="brand-lockup" type="button" onClick={() => navigate("/")}>
        <span className="brand-mark">OJ</span>
        <span>
          <strong>Minimal Judge</strong>
          <span className="muted">session-backed</span>
        </span>
      </button>

      <div className="site-actions">
        {authLoading ? <span className="muted">Checking session...</span> : null}
        {!authLoading && authUser ? (
          <>
            <span className="user-chip">
              {authUser.display_name || authUser.username}
              <span className="user-chip-secondary">@{authUser.username}</span>
            </span>
            <HeaderLink href="/problems/new" primary>
              New problem
            </HeaderLink>
            <button className="ghost-link ghost-button" type="button" onClick={onLogout}>
              Logout
            </button>
          </>
        ) : null}
        {!authLoading && !authUser ? (
          <>
            <HeaderLink href="/login">Login</HeaderLink>
            <HeaderLink href="/register" primary>
              Register
            </HeaderLink>
          </>
        ) : null}
      </div>
    </header>
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
        <p className="muted">Public statements and public submission history stay open. Submitting requires login.</p>
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

function SubmissionCard({ submission }) {
  if (!submission) {
    return null;
  }

  const scoreText = formatScore(submission.score, submission.max_score);

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Latest Result</p>
          <h2>Submission #{submission.id}</h2>
        </div>
        <span className={`status status-${submission.status.toLowerCase()}`}>
          {submission.status}
        </span>
      </div>
      <div className="submission-meta-grid">
        <p className="meta">Author: {submission.user ? `@${submission.user.username}` : "unknown"}</p>
        <p className="meta">Language: {submission.language}</p>
        {scoreText ? <p className="meta">Score: {scoreText}</p> : null}
        <p className="meta">Execution: {formatExecutionTime(submission.execution_time_ms)}</p>
        <p className="meta">Memory: {formatMemoryUsage(submission.memory_usage_kb)}</p>
        <p className="meta">Submitted: {formatTimestamp(submission.created_at)}</p>
      </div>
      {submission.details ? <pre className="details">{submission.details}</pre> : null}
    </section>
  );
}

function MarkdownBlock({ children, fallback }) {
  return (
    <div className="markdown-content">
      <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]} skipHtml>
        {children || fallback}
      </ReactMarkdown>
    </div>
  );
}

function StatementTab({ problem, authUser }) {
  const subtasks = sortedSubtasks(problem.subtask_info);

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Statement</p>
          <h2>{problem.title}</h2>
        </div>
        <div className="panel-actions">
          <p className="meta">
            {problem.time_limit_ms} ms time limit · {problem.memory_limit} MB memory limit
          </p>
          {canEditProblem(problem, authUser) ? (
            <button
              className="ghost-link ghost-button"
              type="button"
              onClick={() => navigate(`/problems/${problem.id}/edit`)}
            >
              Edit problem
            </button>
          ) : null}
        </div>
      </div>

      <div className="statement-grid">
        <section className="statement-section">
          <h3>Description</h3>
          <MarkdownBlock fallback="No description provided.">{problem.description}</MarkdownBlock>
        </section>
        <section className="statement-section">
          <h3>Input</h3>
          <MarkdownBlock fallback="No input specification provided.">{problem.input_spec}</MarkdownBlock>
        </section>
        <section className="statement-section">
          <h3>Output</h3>
          <MarkdownBlock fallback="No output specification provided.">{problem.output_spec}</MarkdownBlock>
        </section>
        <section className="statement-section">
          <h3>Metadata</h3>
          <div className="meta-stack">
            <p className="meta">Author: {problem.author ? `@${problem.author.username}` : "unknown"}</p>
            <p className="meta">Slug: {problem.slug}</p>
            <p className="meta">Testcases: {problem.testcase_count}</p>
          </div>
        </section>
        <section className="statement-section">
          <h3>Examples</h3>
          <div className="examples-stack">
            {problem.examples?.length ? (
              problem.examples.map((example, index) => (
                <div className="example-pair" key={`example-${index + 1}`}>
                  <p className="example-title">Example {index + 1}</p>
                  <div className="example-grid">
                    <div className="example-box">
                      <span className="example-label">Input</span>
                      <pre>{example.input || "—"}</pre>
                    </div>
                    <div className="example-box">
                      <span className="example-label">Output</span>
                      <pre>{example.output || "—"}</pre>
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <div className="example-grid">
                <div className="example-box">
                  <span className="example-label">Input</span>
                  <pre>—</pre>
                </div>
                <div className="example-box">
                  <span className="example-label">Output</span>
                  <pre>—</pre>
                </div>
              </div>
            )}
          </div>
        </section>
        {problem.use_subtask ? (
          <section className="statement-section">
            <h3>Subtasks</h3>
            <div className="subtask-table-wrapper">
              <table className="subtask-table">
                <thead>
                  <tr>
                    <th>subtask</th>
                    <th>score</th>
                    <th>description</th>
                  </tr>
                </thead>
                <tbody>
                  {subtasks.map(([subtaskId, subtask]) => (
                    <tr key={subtaskId}>
                      <td>{`subtask ${subtaskId}`}</td>
                      <td>{subtask.score}</td>
                      <td>
                        <MarkdownBlock fallback="—">{subtask.desc}</MarkdownBlock>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        ) : null}
      </div>
    </section>
  );
}

function AuthGate() {
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Authentication Required</p>
          <h2>Login to submit</h2>
        </div>
        <p className="muted">Public reading stays open. Judge submissions are tied to accounts now.</p>
      </div>
      <div className="inline-actions">
        <button className="primary-button" type="button" onClick={() => navigate("/login")}>
          Login
        </button>
        <button className="ghost-link ghost-button" type="button" onClick={() => navigate("/register")}>
          Create account
        </button>
      </div>
    </section>
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

function ProblemShell({ authUser, problemId, tab }) {
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

function AuthPage({ mode, onAuthenticated }) {
  const [form, setForm] = useState({
    username: "",
    password: "",
    display_name: "",
    email: "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      const payload =
        mode === "register"
          ? form
          : {
              username: form.username,
              password: form.password,
            };
      const user = await fetchJson(mode === "register" ? "/auth/register" : "/auth/login", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      onAuthenticated(user);
      navigate("/");
    } catch (submitError) {
      setError(submitError.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="panel auth-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">{mode === "register" ? "Create Account" : "Login"}</p>
          <h1>{mode === "register" ? "Register" : "Welcome back"}</h1>
        </div>
        <p className="muted">Authentication uses a server-side session and HttpOnly cookie.</p>
      </div>

      <form className="auth-form" onSubmit={handleSubmit}>
        <label className="field">
          <span className="field-label">Username</span>
          <input
            className="text-input"
            value={form.username}
            onChange={(event) => setForm((current) => ({ ...current, username: event.target.value }))}
            required
          />
        </label>
        {mode === "register" ? (
          <>
            <label className="field">
              <span className="field-label">Display name</span>
              <input
                className="text-input"
                value={form.display_name}
                onChange={(event) => setForm((current) => ({ ...current, display_name: event.target.value }))}
              />
            </label>
            <label className="field">
              <span className="field-label">Email</span>
              <input
                className="text-input"
                type="email"
                value={form.email}
                onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))}
              />
            </label>
          </>
        ) : null}
        <label className="field">
          <span className="field-label">Password</span>
          <input
            className="text-input"
            type="password"
            value={form.password}
            onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))}
            required
          />
        </label>
        {error ? <p className="error">{error}</p> : null}
        <div className="inline-actions">
          <button className="primary-button" type="submit" disabled={submitting}>
            {submitting ? "Working..." : mode === "register" ? "Register" : "Login"}
          </button>
          <button
            className="ghost-link ghost-button"
            type="button"
            onClick={() => navigate(mode === "register" ? "/login" : "/register")}
          >
            {mode === "register" ? "Have an account?" : "Need an account?"}
          </button>
        </div>
      </form>
    </section>
  );
}

function ProblemEditorPage({ authUser, mode, problemId }) {
  const [form, setForm] = useState(DEFAULT_PROBLEM_FORM);
  const [loading, setLoading] = useState(mode === "edit");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (mode !== "edit") {
      return undefined;
    }

    let cancelled = false;
    async function loadProblem() {
      setLoading(true);
      setError("");
      try {
        const data = await fetchJson(`/problems/${problemId}/manage`);
        if (!cancelled) {
          setForm(toProblemForm(data));
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
  }, [mode, problemId]);

  if (!authUser) {
    return <AuthGate />;
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const payload = buildProblemPayload(form);
      const path = mode === "edit" ? `/problems/${problemId}` : "/problems";
      const method = mode === "edit" ? "PUT" : "POST";
      const saved = await fetchJson(path, {
        method,
        body: JSON.stringify(payload),
      });
      navigate(`/problems/${saved.id}`);
    } catch (saveError) {
      setError(saveError.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">{mode === "edit" ? "Problem Maintenance" : "Authoring"}</p>
          <h1>{mode === "edit" ? `Edit Problem #${problemId}` : "Create Problem"}</h1>
        </div>
        <p className="muted">Examples, testcases, and subtask data are entered as JSON arrays/objects.</p>
      </div>

      {loading ? <p className="muted">Loading editable problem state...</p> : null}
      {error ? <p className="error">{error}</p> : null}

      {!loading ? (
        <form className="problem-form" onSubmit={handleSubmit}>
          <div className="problem-form-grid">
            <label className="field">
              <span className="field-label">Title</span>
              <input
                className="text-input"
                value={form.title}
                onChange={(event) => setForm((current) => ({ ...current, title: event.target.value }))}
                required
              />
            </label>
            <label className="field">
              <span className="field-label">Slug</span>
              <input
                className="text-input"
                value={form.slug}
                onChange={(event) => setForm((current) => ({ ...current, slug: event.target.value }))}
                required
              />
            </label>
            <label className="field">
              <span className="field-label">Time limit (ms)</span>
              <input
                className="text-input"
                type="number"
                value={form.time_limit_ms}
                onChange={(event) => setForm((current) => ({ ...current, time_limit_ms: event.target.value }))}
                required
              />
            </label>
            <label className="field">
              <span className="field-label">Memory limit (MB)</span>
              <input
                className="text-input"
                type="number"
                value={form.memory_limit}
                onChange={(event) => setForm((current) => ({ ...current, memory_limit: event.target.value }))}
                required
              />
            </label>
          </div>

          <label className="field">
            <span className="field-label">Description</span>
            <textarea
              className="large-textarea"
              value={form.description}
              onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))}
            />
          </label>
          <label className="field">
            <span className="field-label">Input spec</span>
            <textarea
              className="large-textarea"
              value={form.input_spec}
              onChange={(event) => setForm((current) => ({ ...current, input_spec: event.target.value }))}
            />
          </label>
          <label className="field">
            <span className="field-label">Output spec</span>
            <textarea
              className="large-textarea"
              value={form.output_spec}
              onChange={(event) => setForm((current) => ({ ...current, output_spec: event.target.value }))}
            />
          </label>
          <label className="field checkbox-field">
            <input
              type="checkbox"
              checked={form.use_subtask}
              onChange={(event) => setForm((current) => ({ ...current, use_subtask: event.target.checked }))}
            />
            <span>Use subtask judging</span>
          </label>
          <label className="field">
            <span className="field-label">Checker source path</span>
            <input
              className="text-input"
              value={form.checker_source_path}
              onChange={(event) => setForm((current) => ({ ...current, checker_source_path: event.target.value }))}
            />
          </label>
          <label className="field">
            <span className="field-label">Examples JSON</span>
            <textarea
              className="code-textarea"
              value={form.examples}
              onChange={(event) => setForm((current) => ({ ...current, examples: event.target.value }))}
            />
          </label>
          <label className="field">
            <span className="field-label">Subtask info JSON</span>
            <textarea
              className="code-textarea"
              value={form.subtask_info}
              onChange={(event) => setForm((current) => ({ ...current, subtask_info: event.target.value }))}
            />
          </label>
          <label className="field">
            <span className="field-label">Testcases JSON</span>
            <textarea
              className="code-textarea"
              value={form.testcases}
              onChange={(event) => setForm((current) => ({ ...current, testcases: event.target.value }))}
            />
          </label>
          <div className="inline-actions">
            <button className="primary-button" type="submit" disabled={saving}>
              {saving ? "Saving..." : mode === "edit" ? "Update problem" : "Create problem"}
            </button>
            <button className="ghost-link ghost-button" type="button" onClick={() => navigate("/")}>
              Cancel
            </button>
          </div>
        </form>
      ) : null}
    </section>
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
  const [authUser, setAuthUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(true);

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
  }, [route.name]);

  useEffect(() => {
    let cancelled = false;

    async function loadAuth() {
      setAuthLoading(true);
      try {
        const data = await fetchJson("/auth/me");
        if (!cancelled) {
          setAuthUser(data);
        }
      } catch {
        if (!cancelled) {
          setAuthUser(null);
        }
      } finally {
        if (!cancelled) {
          setAuthLoading(false);
        }
      }
    }

    loadAuth().catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleLogout() {
    try {
      await fetchJson("/auth/logout", { method: "POST" });
    } catch {
      // Clear local auth state even if the server session is already gone.
    }
    setAuthUser(null);
    navigate("/");
  }

  return (
    <main className="app-shell">
      <SiteHeader authUser={authUser} authLoading={authLoading} onLogout={handleLogout} />

      {route.name === "home" ? <ProblemList problems={problems} loading={loading} error={error} /> : null}
      {route.name === "problem" ? <ProblemShell authUser={authUser} problemId={route.problemId} tab={route.tab} /> : null}
      {route.name === "login" ? <AuthPage mode="login" onAuthenticated={setAuthUser} /> : null}
      {route.name === "register" ? <AuthPage mode="register" onAuthenticated={setAuthUser} /> : null}
      {route.name === "problem-editor" ? (
        <ProblemEditorPage authUser={authUser} mode={route.mode} problemId={route.problemId} />
      ) : null}
      {route.name === "not-found" ? <NotFound /> : null}
    </main>
  );
}
