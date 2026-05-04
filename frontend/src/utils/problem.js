export const DEFAULT_PROBLEM_FORM = {
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

export function sortedSubtasks(subtaskInfo) {
  return Object.entries(subtaskInfo ?? {}).sort(([left], [right]) => {
    const leftNumber = Number(left);
    const rightNumber = Number(right);
    if (Number.isFinite(leftNumber) && Number.isFinite(rightNumber)) {
      return leftNumber - rightNumber;
    }
    return left.localeCompare(right);
  });
}

export function toProblemForm(problem) {
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

export function parseStructuredField(label, value, fallback) {
  if (!value.trim()) {
    return fallback;
  }
  try {
    return JSON.parse(value);
  } catch {
    throw new Error(`${label} must be valid JSON`);
  }
}

export function buildProblemPayload(form) {
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

export function canEditProblem(problem, authUser) {
  if (!problem || !authUser) {
    return false;
  }
  return authUser.role === "admin" || problem.author?.id === authUser.id;
}
