import { navigate } from "../utils/router";

export function TabLink({ active, children, href }) {
  return (
    <a
      className={`tab-link ${active ? "tab-link-active" : ""}`}
      href={href}
      onClick={(event) => {
        event.preventDefault();
        navigate(href);
      }}
    >
      {children}
    </a>
  );
}
