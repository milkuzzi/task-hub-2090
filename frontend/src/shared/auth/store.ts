import { create } from 'zustand';
import type { User } from '@/shared/types';

// Access-токен — только в памяти (не в localStorage), refresh — в httpOnly cookie (§13.6.3).
interface AuthState {
  accessToken: string | null;
  user: User | null;
  setSession: (token: string, user: User) => void;
  setUser: (user: User) => void;
  clear: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  accessToken: null,
  user: null,
  setSession: (accessToken, user) => set({ accessToken, user }),
  setUser: (user) => set({ user }),
  clear: () => set({ accessToken: null, user: null }),
}));
