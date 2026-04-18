import { Link, useLocation } from "react-router-dom";
import { Skull } from "lucide-react";

export default function Header() {
  const { pathname } = useLocation();

  const linkClass = (path) =>
    `app-header__link${pathname === path ? " app-header__link--active" : ""}`;

  return (
    <header className="app-header">
      <Link to="/" className="app-header__logo" style={{ textDecoration: "none" }}>
        <Skull size={22} />
        <span>Dead Code Archaeologist</span>
      </Link>
      <nav className="app-header__nav">
        <Link to="/" className={linkClass("/")}>
          Analyze
        </Link>
      </nav>
    </header>
  );
}
