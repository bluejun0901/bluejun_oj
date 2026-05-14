export function parseRoute(pathname) {
  if (pathname === "/") {
    return { name: "home" };
  }
  if (pathname === "/login") {
    return { name: "login" };
  }
  if (pathname === "/register") {
    return { name: "register" };
  }
  if (pathname === "/drafts") {
    return { name: "draft-list" };
  }
  if (pathname === "/drafts/new") {
    return { name: "draft-new" };
  }

  const draftStatementMatch = pathname.match(/^\/drafts\/(\d+)\/statement\/?$/);
  if (draftStatementMatch) {
    return { name: "draft-statement", draftId: Number(draftStatementMatch[1]) };
  }

  const draftSubtasksMatch = pathname.match(/^\/drafts\/(\d+)\/subtasks\/?$/);
  if (draftSubtasksMatch) {
    return { name: "draft-subtasks", draftId: Number(draftSubtasksMatch[1]) };
  }

  const draftTestcasesMatch = pathname.match(/^\/drafts\/(\d+)\/testcases\/?$/);
  if (draftTestcasesMatch) {
    return { name: "draft-testcases", draftId: Number(draftTestcasesMatch[1]) };
  }

  const draftTestcaseDetailMatch = pathname.match(/^\/drafts\/(\d+)\/testcases\/(\d+)\/?$/);
  if (draftTestcaseDetailMatch) {
    return {
      name: "draft-testcase-detail",
      draftId: Number(draftTestcaseDetailMatch[1]),
      testcaseId: Number(draftTestcaseDetailMatch[2]),
    };
  }

  const draftCheckerMatch = pathname.match(/^\/drafts\/(\d+)\/checker\/?$/);
  if (draftCheckerMatch) {
    return { name: "draft-checker", draftId: Number(draftCheckerMatch[1]) };
  }

  const draftPreviewMatch = pathname.match(/^\/drafts\/(\d+)\/preview\/?$/);
  if (draftPreviewMatch) {
    return { name: "draft-preview", draftId: Number(draftPreviewMatch[1]) };
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

export function navigate(pathname) {
  if (window.location.pathname === pathname) {
    return;
  }
  window.history.pushState({}, "", pathname);
  window.dispatchEvent(new PopStateEvent("popstate"));
}
