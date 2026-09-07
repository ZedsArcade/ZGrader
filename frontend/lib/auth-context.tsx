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
  logout: (options?: { revokeOnServer?: boolean }) => Promise<void>;
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
      .catch((error: unknown) => {
        // Only a 401 means the token is actually dead. This used to discard it
        // on *any* failure, which reads as obviously correct and is how the bug
        // survived: a network error, a 500, or the 503 the maintenance Worker
        // serves would each sign every user out and make them log in again.
        // On a server that is powered down between sessions that is the normal
        // case rather than an edge one.
        //
        // Keeping the token does not sign them back in here -- RequireAuth
        // gates on `user`, and we have none -- but it means one reload once the
        // backend is reachable restores the session instead of a password.
        if (error instanceof api.ApiError && error.status === 401) {
          window.localStorage.removeItem(TOKEN_KEY);
        }
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

  /** Sign out here, and on the server.
   *
   *  Clearing localStorage alone left the token valid for the rest of its
   *  24-hour life, so anyone holding a copy kept the session the user thought
   *  they had ended. The server call retires it for real.
   *
   *  Order is deliberate: the request is best-effort and the local clear is
   *  not. Bailing out when the network is down would leave someone signed in
   *  behind a button that appears to do nothing, which is worse than a session
   *  that outlives the click.
   *
   *  `revokeOnServer: false` is for the case where there is no longer an
   *  account to revoke against -- closing it already invalidated everything. */
  const logout = useCallback(
    async ({ revokeOnServer = true }: { revokeOnServer?: boolean } = {}) => {
      const current = window.localStorage.getItem(TOKEN_KEY);
      if (revokeOnServer && current) {
        try {
          await api.logoutSession(current);
        } catch {
          // Already expired, or unreachable. Sign out locally regardless.
        }
      }
      window.localStorage.removeItem(TOKEN_KEY);
      setToken(null);
      setUser(null);
    },
    []
  );

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
