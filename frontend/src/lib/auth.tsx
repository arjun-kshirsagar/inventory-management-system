"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import {
  api,
  errorMessage,
  refreshAccessToken,
  setAccessToken,
  setUnauthorizedHandler,
  type Schemas,
} from "@/lib/api/client";

type User = Schemas["UserOut"];

type AuthState = {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  const queryClient = useQueryClient();

  const loadUser = useCallback(async () => {
    const { data } = await api.GET("/api/v1/auth/me");
    setUser(data ?? null);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setUser(null);
      router.replace("/login");
    });
    // Restore the session from the refresh cookie on first load.
    refreshAccessToken()
      .then((token) => (token ? loadUser() : undefined))
      .finally(() => setLoading(false));
  }, [loadUser, router]);

  const login = useCallback(
    async (email: string, password: string) => {
      const { data, error } = await api.POST("/api/v1/auth/login", { body: { email, password } });
      if (!data) throw new Error(errorMessage(error));
      setAccessToken(data.access_token);
      await loadUser();
    },
    [loadUser],
  );

  const logout = useCallback(async () => {
    await api.POST("/api/v1/auth/logout");
    setAccessToken(null);
    setUser(null);
    queryClient.clear();
    router.replace("/login");
  }, [queryClient, router]);

  const value = useMemo(() => ({ user, loading, login, logout }), [user, loading, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
