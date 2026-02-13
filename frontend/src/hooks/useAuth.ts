/* Auth Hook: Login/Logout/Token-Management */

import { useState, useEffect, useCallback } from "react";
import type { User, AuthState } from "../types";
import { authAPI } from "../api/client";

export function useAuth(): AuthState & {
  login: (type: "admin" | "musiker", email: string, password: string) => Promise<void>;
  setup: (email: string, password: string) => Promise<void>;
  logout: () => void;
  loading: boolean;
  error: string | null;
  needsSetup: boolean;
} {
  const [token, setToken] = useState<string | null>(
    localStorage.getItem("sbp_token")
  );
  const [user, setUser] = useState<User | null>(() => {
    const stored = localStorage.getItem("sbp_user");
    return stored ? JSON.parse(stored) : null;
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [needsSetup, setNeedsSetup] = useState(false);

  // Auth-Status pruefen
  useEffect(() => {
    authAPI.status().then((res) => {
      setNeedsSetup(!res.data.admin_exists);
    }).catch(() => {});
  }, []);

  const login = useCallback(
    async (type: "admin" | "musiker", email: string, password: string) => {
      setLoading(true);
      setError(null);
      try {
        const res = await authAPI.login(type, email, password);
        const { token: newToken, user: newUser } = res.data;
        localStorage.setItem("sbp_token", newToken);
        localStorage.setItem("sbp_user", JSON.stringify(newUser));
        setToken(newToken);
        setUser(newUser);
      } catch (err: unknown) {
        const msg = (err as { response?: { data?: { error?: string } } })?.response?.data?.error || "Login fehlgeschlagen.";
        setError(msg);
        throw new Error(msg);
      } finally {
        setLoading(false);
      }
    },
    []
  );

  const setup = useCallback(async (email: string, password: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await authAPI.setup(email, password);
      const { token: newToken, user: newUser } = res.data;
      localStorage.setItem("sbp_token", newToken);
      localStorage.setItem("sbp_user", JSON.stringify(newUser));
      setToken(newToken);
      setUser(newUser);
      setNeedsSetup(false);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { error?: string } } })?.response?.data?.error || "Setup fehlgeschlagen.";
      setError(msg);
      throw new Error(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("sbp_token");
    localStorage.removeItem("sbp_user");
    setToken(null);
    setUser(null);
  }, []);

  return {
    token,
    user,
    isAuthenticated: !!token && !!user,
    login,
    setup,
    logout,
    loading,
    error,
    needsSetup,
  };
}
