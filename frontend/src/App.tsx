/* App: Root-Komponente mit Router und Auth-Guard */

import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "./hooks/useAuth";
import Header from "./components/layout/Header";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Events from "./pages/Events";
import Generator from "./pages/Generator";
import MusikerArea from "./pages/MusikerArea";

export default function App() {
  const auth = useAuth();

  // Nicht eingeloggt → Login
  if (!auth.isAuthenticated) {
    return (
      <Login
        onLogin={auth.login}
        onSetup={auth.setup}
        needsSetup={auth.needsSetup}
        loading={auth.loading}
        error={auth.error}
      />
    );
  }

  const isAdmin = auth.user?.role === "admin";

  return (
    <BrowserRouter>
      <div className="min-h-screen bg-[var(--color-bg)]">
        <Header user={auth.user} onLogout={auth.logout} />
        <main>
          <Routes>
            {/* Admin-Routes */}
            {isAdmin && (
              <>
                <Route path="/" element={<Dashboard />} />
                <Route path="/events" element={<Events />} />
                <Route path="/generator" element={<Generator />} />
              </>
            )}

            {/* Musiker + Admin */}
            <Route path="/musiker" element={<MusikerArea />} />

            {/* Fallback */}
            <Route path="*" element={<Navigate to={isAdmin ? "/" : "/musiker"} replace />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
