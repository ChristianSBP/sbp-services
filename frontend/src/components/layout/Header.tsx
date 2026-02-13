/* Header-Komponente: Frosted glass Navigation */

import { Link, useLocation } from "react-router-dom";
import type { User } from "../../types";

interface HeaderProps {
  user: User | null;
  onLogout: () => void;
}

export default function Header({ user, onLogout }: HeaderProps) {
  const location = useLocation();
  const isAdmin = user?.role === "admin";

  const navItems = isAdmin
    ? [
        { path: "/", label: "Jahresplan" },
        { path: "/events", label: "Events" },
        { path: "/generator", label: "Dienstplan" },
        { path: "/musiker", label: "Musiker" },
      ]
    : [
        { path: "/musiker", label: "Dienstpläne" },
      ];

  return (
    <header className="glass-header sticky top-0 z-50 border-b border-[var(--color-border)]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-14">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-2">
            <span className="text-lg font-semibold tracking-tight text-[var(--color-primary)]">
              Planung SBP
            </span>
          </Link>

          {/* Navigation */}
          <nav className="flex items-center gap-1">
            {navItems.map((item) => (
              <Link
                key={item.path}
                to={item.path}
                className={`px-3 py-1.5 text-sm font-medium rounded-lg transition-colors ${
                  location.pathname === item.path
                    ? "bg-[var(--color-accent)]/10 text-[var(--color-accent)]"
                    : "text-[var(--color-secondary)] hover:text-[var(--color-primary)] hover:bg-black/5"
                }`}
              >
                {item.label}
              </Link>
            ))}
          </nav>

          {/* User-Info + Logout */}
          <div className="flex items-center gap-3">
            {user && (
              <span className="text-xs text-[var(--color-secondary)]">
                {user.email || user.role}
              </span>
            )}
            <button
              onClick={onLogout}
              className="text-xs text-[var(--color-secondary)] hover:text-[var(--color-error)] transition-colors"
            >
              Abmelden
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}
