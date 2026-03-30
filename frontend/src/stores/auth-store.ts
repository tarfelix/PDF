import { create } from "zustand";

interface AuthUser {
  name: string;
  email: string;
  role: string;
}

interface AuthState {
  token: string | null;
  user: AuthUser | null;
  login: (token: string, user: AuthUser) => void;
  logout: () => void;
}

const TOKEN_KEY = "pdf-editor-token";
const USER_KEY = "pdf-editor-user";

function loadFromStorage(): { token: string | null; user: AuthUser | null } {
  const token = localStorage.getItem(TOKEN_KEY);
  const raw = localStorage.getItem(USER_KEY);
  if (token && raw) {
    try {
      return { token, user: JSON.parse(raw) };
    } catch {
      // corrupted
    }
  }
  return { token: null, user: null };
}

const initial = loadFromStorage();

export const useAuthStore = create<AuthState>((set) => ({
  token: initial.token,
  user: initial.user,

  login: (token, user) => {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
    set({ token, user });
  },

  logout: () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    set({ token: null, user: null });
  },
}));
