"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import * as api from "./api";

interface AuthContextValue {
  user: api.User | null;
  token: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<api.User>;
  register: (
    email: string,
    password: string,
    acceptTerms: boolean,
    marketingConsent?: boolean
  ) => Promise<api.User>;
  logout: () => void;
  /** Swap in a token issued by the server mid-session (after a password
   *  change, which retires the previous one). */
  adoptToken: (token: string) => Promise<void>;
  /** Re-read the current user, e.g. after a profile update. */
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

const TOKEN_KEY = "zgrader_token";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<api.User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const stored = window.localStorage.getItem(TOKEN_KEY);
    if (!stored) {
      setLoading(false);
      return;
    }
    api
      .getMe(stored)
      .then((me) => {
        setToken(stored);
        setUser(me);
      })
      .catch(() => {
        window.localStorage.removeItem(TOKEN_KEY);
      })
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const { access_token } = await api.login(email, password);
    const me = await api.getMe(access_token);
    window.localStorage.setItem(TOKEN_KEY, access_token);
    setToken(access_token);
    setUser(me);
    return me;
  }, []);

  const register = useCallback(
    async (email: string, password: string, acceptTerms: boolean, marketingConsent = false) => {
      await api.register(email, password, acceptTerms, marketingConsent);
      return login(email, password);
    },
    [login]
  );

  // Called after a password change: the old token has been retired
  // server-side, so the session has to adopt the replacement rather than
  // keep using a token that now 401s.
  const adoptToken = useCallback(async (nextToken: string) => {
    const me = await api.getMe(nextToken);
    window.localStorage.setItem(TOKEN_KEY, nextToken);
    setToken(nextToken);
    setUser(me);
  }, []);

  const refreshUser = useCallback(async () => {
    if (!token) return;
    setUser(await api.getMe(token));
  }, [token]);

  const logout = useCallback(() => {
    window.localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, token, loading, login, register, logout, adoptToken, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
