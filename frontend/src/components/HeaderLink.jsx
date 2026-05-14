import { navigate } from "../utils/router";

export function HeaderLink({ href, children, primary = false }) {
  return (
    <a
      className={primary ? "primary-button compact-button" : "ghost-link"}
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
