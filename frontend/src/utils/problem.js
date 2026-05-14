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

export function blankExample() {
  return { input: "", output: "" };
}

export function blankSubtask() {
  return { id: "", desc: "", score: 0, cases: "" };
}

export function formatSubtaskCases(value) {
  const numbers = [...new Set((value ?? []).filter((entry) => Number.isInteger(entry) && entry > 0))].sort((left, right) => left - right);
  if (numbers.length === 0) {
    return "";
  }

  const ranges = [];
  let start = numbers[0];
  let end = numbers[0];
  for (let index = 1; index < numbers.length; index += 1) {
    if (numbers[index] === end + 1) {
      end = numbers[index];
      continue;
    }
    ranges.push(start === end ? `${start}` : `${start}-${end}`);
    start = numbers[index];
    end = numbers[index];
  }
  ranges.push(start === end ? `${start}` : `${start}-${end}`);
  return ranges.join(", ");
}

export function parseSubtaskCases(value) {
  if (!value.trim()) {
    return [];
  }
  const seen = new Set();
  const numbers = [];
  for (const rawPart of value.split(",")) {
    const part = rawPart.trim();
    if (!part) {
      continue;
    }
    const rangeMatch = part.match(/^(\d+)\s*-\s*(\d+)$/);
    if (rangeMatch) {
      const start = Number(rangeMatch[1]);
      const end = Number(rangeMatch[2]);
      if (start > end) {
        throw new Error(`Invalid testcase range '${part}'`);
      }
      for (let current = start; current <= end; current += 1) {
        if (!seen.has(current)) {
          seen.add(current);
          numbers.push(current);
        }
      }
      continue;
    }
    if (!/^\d+$/.test(part)) {
      throw new Error(`Invalid testcase reference '${part}'`);
    }
    const caseId = Number(part);
    if (!seen.has(caseId)) {
      seen.add(caseId);
      numbers.push(caseId);
    }
  }
  return numbers.sort((left, right) => left - right);
}
