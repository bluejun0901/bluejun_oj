import { navigate } from "../utils/router";

export function AuthGate() {
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Authentication Required</p>
          <h2>Login to submit</h2>
        </div>
        <p className="muted">Public reading stays open. Judge submissions are tied to accounts now.</p>
      </div>
      <div className="inline-actions">
        <button className="primary-button" type="button" onClick={() => navigate("/login")}>
          Login
        </button>
        <button className="ghost-link ghost-button" type="button" onClick={() => navigate("/register")}>
          Create account
        </button>
      </div>
    </section>
  );
}
