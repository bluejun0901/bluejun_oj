import { MarkdownBlock } from "./MarkdownBlock";
import { sortedSubtasks } from "../utils/problem";

export function ProblemStatementView({
  problem,
  eyebrow = "Statement",
  title,
  action,
  banner,
  footer,
}) {
  const subtasks = sortedSubtasks(problem.subtask_info);

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">{eyebrow}</p>
          <h2>{title ?? problem.title}</h2>
        </div>
        <div className="panel-actions">
          <p className="meta">
            {problem.time_limit_ms} ms time limit · {problem.memory_limit} MB memory limit
          </p>
          {action}
        </div>
      </div>

      {banner ? <div className="notice-card">{banner}</div> : null}

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
            <p className="meta">Slug: {problem.slug || "—"}</p>
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

      {footer ? <div className="inline-actions statement-footer">{footer}</div> : null}
    </section>
  );
}
