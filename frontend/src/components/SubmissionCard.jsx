import { formatExecutionTime, formatMemoryUsage, formatScore, formatTimestamp } from "../utils/formatters";

export function SubmissionCard({ submission }) {
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
