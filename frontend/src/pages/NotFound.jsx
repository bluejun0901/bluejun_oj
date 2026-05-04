import { navigate } from "../utils/router";

export function NotFoundPage() {
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">404</p>
          <h1>Page not found</h1>
        </div>
      </div>
      <button className="primary-button" type="button" onClick={() => navigate("/")}>
        Go to problems
      </button>
    </section>
  );
}
