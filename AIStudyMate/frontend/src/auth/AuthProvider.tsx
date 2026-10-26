import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { authApi, configureSessionExpiry, tokenStore } from "../lib/api";
import type { User } from "../types/api";

interface AuthContextValue {
  user: User | null; initializing: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (input: { username: string; email: string; password: string; full_name: string }) => Promise<void>;
  logout: () => void;
}
const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [initializing, setInitializing] = useState(true);

  const logout = () => { tokenStore.clear(); setUser(null); };
  useEffect(() => { configureSessionExpiry(logout); }, []);
  useEffect(() => {
    const restore = async () => {
      if (!tokenStore.getRefresh()) { setInitializing(false); return; }
      try { await authApi.refresh(); setUser(await authApi.me()); } catch { logout(); }
      finally { setInitializing(false); }
    };
    void restore();
  }, []);

  const value = useMemo<AuthContextValue>(() => ({
    user, initializing,
    async login(username, password) { tokenStore.set(await authApi.login(username, password)); setUser(await authApi.me()); },
    async register(input) {
      await authApi.register(input);
      tokenStore.set(await authApi.login(input.username, input.password));
      setUser(await authApi.me());
    },
    logout,
  }), [user, initializing]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
