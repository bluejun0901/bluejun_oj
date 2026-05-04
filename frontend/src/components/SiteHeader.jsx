import { navigate } from "../utils/router";
import { HeaderLink } from "./HeaderLink";

export function SiteHeader({ authUser, authLoading, onLogout }) {
  return (
    <header className="site-header">
      <button className="brand-lockup" type="button" onClick={() => navigate("/")}>
        <span className="brand-mark">OJ</span>
        <span>
          <strong>Minimal Judge</strong>
          <span className="muted">online judge</span>
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
