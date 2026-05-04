import { useEffect, useState } from "react";
import { fetchJson } from "../utils/api";
import { navigate } from "../utils/router";

function AuthPage({ mode, onAuthenticated }) {
  const [form, setForm] = useState({
    username: "",
    password: "",
    display_name: "",
    email: "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      const payload =
        mode === "register"
          ? form
          : {
              username: form.username,
              password: form.password,
            };
      const user = await fetchJson(mode === "register" ? "/auth/register" : "/auth/login", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      onAuthenticated(user);
      navigate("/");
    } catch (submitError) {
      setError(submitError.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="panel auth-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">{mode === "register" ? "Create Account" : "Login"}</p>
          <h1>{mode === "register" ? "Register" : "Welcome back"}</h1>
        </div>
        <p className="muted">Authentication uses a server-side session and HttpOnly cookie.</p>
      </div>

      <form className="auth-form" onSubmit={handleSubmit}>
        <label className="field">
          <span className="field-label">Username</span>
          <input
            className="text-input"
            value={form.username}
            onChange={(event) => setForm((current) => ({ ...current, username: event.target.value }))}
            required
          />
        </label>
        {mode === "register" ? (
          <>
            <label className="field">
              <span className="field-label">Display name</span>
              <input
                className="text-input"
                value={form.display_name}
                onChange={(event) => setForm((current) => ({ ...current, display_name: event.target.value }))}
              />
            </label>
            <label className="field">
              <span className="field-label">Email</span>
              <input
                className="text-input"
                type="email"
                value={form.email}
                onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))}
              />
            </label>
          </>
        ) : null}
        <label className="field">
          <span className="field-label">Password</span>
          <input
            className="text-input"
            type="password"
            value={form.password}
            onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))}
            required
          />
        </label>
        {error ? <p className="error">{error}</p> : null}
        <div className="inline-actions">
          <button className="primary-button" type="submit" disabled={submitting}>
            {submitting ? "Working..." : mode === "register" ? "Register" : "Login"}
          </button>
          <button
            className="ghost-link ghost-button"
            type="button"
            onClick={() => navigate(mode === "register" ? "/login" : "/register")}
          >
            {mode === "register" ? "Have an account?" : "Need an account?"}
          </button>
        </div>
      </form>
    </section>
  );
}

export function LoginPage({ onAuthenticated }) {
  return <AuthPage mode="login" onAuthenticated={onAuthenticated} />;
}

export function RegisterPage({ onAuthenticated }) {
  return <AuthPage mode="register" onAuthenticated={onAuthenticated} />;
}
