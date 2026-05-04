export function formatTimestamp(value) {
  return new Date(value).toLocaleString();
}

export function formatExecutionTime(value) {
  return typeof value === "number" ? `${value} ms` : "—";
}

export function formatMemoryUsage(value) {
  return typeof value === "number" ? `${value} KB` : "—";
}

export function formatScore(score, maxScore) {
  if (typeof score !== "number" || typeof maxScore !== "number") {
    return null;
  }
  return `${score}/${maxScore}`;
}
