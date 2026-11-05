"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  ApiError,
  clearStoredToken,
  fetchMe,
  getStoredToken,
  login as apiLogin,
  logoutSession,
  refreshSession,
  setStoredToken,
  SIGNED_OUT_EVENT,
} from "@/lib/api";
import { UserRecord, UserRole } from "@/lib/types";

/**
 * Optimistic session restore: decode the JWT payload locally (display only —
 * the API still verifies the signature on every request). This keeps the
 * session alive across page reloads even if the API is briefly unreachable;
 * only a real 401 logs the user out.
 */
const decodeUserFromToken = (token: string): UserRecord | null => {
  try {
    const payload = JSON.parse(atob(token.split(".")[1])) as {
      sub?: string;
      email?: string;
      name?: string;
      role?: string;
      exp?: number;
    };
    if (!payload.sub || !payload.role) return null;
    if (payload.exp && payload.exp * 1000 < Date.now()) return null;
    return {
      id: payload.sub,
      email: payload.email ?? "",
      name: payload.name ?? payload.email ?? "User",
      role: payload.role as UserRole,
      active: true,
    };
  } catch {
    return null;
  }
};

const ROLE_LEVELS: Record<UserRole, number> = {
  viewer: 0,
  security: 1,
  ehs: 1,
  operator: 1,
  supervisor: 2,
  admin: 3,
};

export type AuthContextValue = {
  user: UserRecord | null;
  token: string | null;
  initializing: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  /** True when the current user's role is at or above the given role. */
  hasRole: (minimum: UserRole) => boolean;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export const AuthProvider = ({ children }: { children: React.ReactNode }) => {
  const [user, setUser] = useState<UserRecord | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [initializing, setInitializing] = useState(true);

  useEffect(() => {
    let active = true;

    const restoreSession = async () => {
      let stored = getStoredToken();
      let decoded = stored ? decodeUserFromToken(stored) : null;
      if (!decoded) {
        // Access tokens are short-lived; the HttpOnly refresh cookie decides
        // whether this browser is still signed in.
        clearStoredToken();
        try {
          stored = await refreshSession();
        } catch {
          stored = null; // API unreachable: show sign-in, which reports the outage.
        }
        decoded = stored ? decodeUserFromToken(stored) : null;
        if (!stored || !decoded) {
          if (active) setInitializing(false);
          return;
        }
      }

      // Restore the session immediately from the token, then confirm with
      // the API in the background.
      if (active) {
        setToken(stored);
        setUser(decoded);
        setInitializing(false);
      }

      try {
        const me = await fetchMe();
        if (active) setUser(me);
      } catch (error) {
        // fetchMe already tried a refresh; only an explicit rejection ends
        // the session. Network/API-restart failures keep the user signed in.
        if (error instanceof ApiError && error.status === 401) {
          clearStoredToken();
          if (active) {
            setToken(null);
            setUser(null);
          }
        }
      }
    };

    void restoreSession();
    const signedOut = () => {
      if (!active) return;
      setToken(null);
      setUser(null);
    };
    window.addEventListener(SIGNED_OUT_EVENT, signedOut);
    return () => {
      active = false;
      window.removeEventListener(SIGNED_OUT_EVENT, signedOut);
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const response = await apiLogin(email, password);
    setStoredToken(response.token);
    setToken(response.token);
    setUser(response.user);
  }, []);

  const logout = useCallback(() => {
    void logoutSession().finally(clearStoredToken);
    setToken(null);
    setUser(null);
  }, []);

  const hasRole = useCallback(
    (minimum: UserRole) => {
      if (!user) return false;
      return ROLE_LEVELS[user.role] >= ROLE_LEVELS[minimum];
    },
    [user]
  );

  const value = useMemo(
    () => ({ user, token, initializing, login, logout, hasRole }),
    [user, token, initializing, login, logout, hasRole]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
};
