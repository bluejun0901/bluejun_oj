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

export function navigate(pathname) {
  if (window.location.pathname === pathname) {
    return;
  }
  window.history.pushState({}, "", pathname);
  window.dispatchEvent(new PopStateEvent("popstate"));
}
