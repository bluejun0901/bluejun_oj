import { navigate } from "../utils/router";

export function DraftNav({ draftId, active }) {
  const items = [
    { key: "statement", label: "statement", href: `/drafts/${draftId}/statement` },
    { key: "subtasks", label: "subtasks", href: `/drafts/${draftId}/subtasks` },
    { key: "testcases", label: "testcases", href: `/drafts/${draftId}/testcases` },
    { key: "checker", label: "checker", href: `/drafts/${draftId}/checker` },
    { key: "preview", label: "preview", href: `/drafts/${draftId}/preview` },
  ];

  return (
    <nav className="tabs" aria-label="Draft navigation">
      {items.map((item) => (
        <button
          key={item.key}
          type="button"
          className={`tab-link ${active === item.key ? "tab-link-active" : ""}`}
          onClick={() => navigate(item.href)}
        >
          {item.label}
        </button>
      ))}
    </nav>
  );
}
