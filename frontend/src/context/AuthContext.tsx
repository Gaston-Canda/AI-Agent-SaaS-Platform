import { createContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY } from "../api/client";
import {
  login as loginRequest,
  register as registerRequest,
  type AuthResponse,
  type AuthUser,
  type LoginInput,
  type RegisterInput,
} from "../api/auth";

const USER_KEY = "auth_user";

interface AuthContextValue {
  user: AuthUser | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  login: (input: LoginInput) => Promise<void>;
  register: (input: RegisterInput) => Promise<void>;
  logout: () => void;
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined);

function persistSession(payload: AuthResponse): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, payload.access_token);
  localStorage.setItem(REFRESH_TOKEN_KEY, payload.refresh_token);
  localStorage.setItem(USER_KEY, JSON.stringify(payload.user));
}

export function AuthProvider({ children }: { children: ReactNode }): JSX.Element {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);

  useEffect(() => {
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    const rawUser = localStorage.getItem(USER_KEY);
    if (!token || !rawUser) {
      return;
    }
    try {
      setAccessToken(token);
      setUser(JSON.parse(rawUser) as AuthUser);
    } catch {
      localStorage.removeItem(ACCESS_TOKEN_KEY);
      localStorage.removeItem(REFRESH_TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
    }
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      accessToken,
      isAuthenticated: Boolean(user && accessToken),
      login: async (input: LoginInput) => {
        const payload = await loginRequest(input);
        persistSession(payload);
        setUser(payload.user);
        setAccessToken(payload.access_token);
      },
      register: async (input: RegisterInput) => {
        const payload = await registerRequest(input);
        persistSession(payload);
        setUser(payload.user);
        setAccessToken(payload.access_token);
      },
      logout: () => {
        setUser(null);
        setAccessToken(null);
        localStorage.removeItem(ACCESS_TOKEN_KEY);
        localStorage.removeItem(REFRESH_TOKEN_KEY);
        localStorage.removeItem(USER_KEY);
      },
    }),
    [accessToken, user]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
