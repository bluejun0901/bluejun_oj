import { useEffect, useState } from "react";
import { fetchJson } from "../utils/api";
import { navigate } from "../utils/router";
import { DEFAULT_PROBLEM_FORM, toProblemForm, buildProblemPayload } from "../utils/problem";
import { AuthGate } from "../components/AuthGate";

export function ProblemEditorPage({ authUser, mode, problemId }) {
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
