import { create } from "zustand";

interface AuthUser {
  name: string;
  email: string;
  role: string;
}

interface AuthState {
  user: AuthUser | null;
  // ready=false ate o bootstrap (/api/me) terminar; evita piscar tela.
  ready: boolean;
  setUser: (user: AuthUser | null) => void;
}

// SSO central (oauth2-proxy): nao ha token local. A sessao vive no cookie
// wildcard .soarespicon.adv.br e os headers X-Auth-Request-* sao injetados
// pelo edge. O usuario corrente vem de GET /api/me.
export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  ready: false,
  setUser: (user) => set({ user, ready: true }),
}));
