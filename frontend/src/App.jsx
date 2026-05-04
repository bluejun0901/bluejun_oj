import { useEffect, useState } from "react";
import "katex/dist/katex.min.css";

import { parseRoute } from "./utils/router";
import { fetchJson } from "./utils/api";
import { SiteHeader } from "./components/SiteHeader";
import { HomePage } from "./pages/Home";
import { ProblemPage } from "./pages/Problem";
import { LoginPage, RegisterPage } from "./pages/Auth";
import { ProblemEditorPage } from "./pages/ProblemEditor";
import { NotFoundPage } from "./pages/NotFound";

export default function App() {
  const [route, setRoute] = useState(() => parseRoute(window.location.pathname));
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
    window.history.pushState({}, "", "/");
    window.dispatchEvent(new PopStateEvent("popstate"));
  }

  return (
    <main className="app-shell">
      <SiteHeader authUser={authUser} authLoading={authLoading} onLogout={handleLogout} />

      {route.name === "home" ? <HomePage /> : null}
      {route.name === "problem" ? <ProblemPage authUser={authUser} problemId={route.problemId} tab={route.tab} /> : null}
      {route.name === "login" ? <LoginPage onAuthenticated={setAuthUser} /> : null}
      {route.name === "register" ? <RegisterPage onAuthenticated={setAuthUser} /> : null}
      {route.name === "problem-editor" ? (
        <ProblemEditorPage authUser={authUser} mode={route.mode} problemId={route.problemId} />
      ) : null}
      {route.name === "not-found" ? <NotFoundPage /> : null}
    </main>
  );
}
