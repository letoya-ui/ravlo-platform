import { create } from 'zustand';
import * as SecureStore from 'expo-secure-store';
import { api } from '../services/api';

interface User {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  role: string;
  subscription: string;
  university_tier: string | null;
  onboarding_complete: boolean;
}

interface AuthState {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  loadToken: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: null,
  isLoading: false,
  error: null,

  loadToken: async () => {
    try {
      const token = await SecureStore.getItemAsync('ravlo_token');
      if (token) {
        api.defaults.headers.common['Authorization'] = `Bearer ${token}`;
        const res = await api.get('/mobile/auth/me');
        set({ token, user: res.data.user });
      }
    } catch {
      await SecureStore.deleteItemAsync('ravlo_token');
    }
  },

  login: async (email: string, password: string) => {
    set({ isLoading: true, error: null });
    try {
      const res = await api.post('/mobile/auth/login', { email, password });
      const { token, user } = res.data;
      await SecureStore.setItemAsync('ravlo_token', token);
      api.defaults.headers.common['Authorization'] = `Bearer ${token}`;
      set({ token, user, isLoading: false });
    } catch (err: any) {
      const msg = err.response?.data?.error || 'Login failed';
      set({ error: msg, isLoading: false });
      throw new Error(msg);
    }
  },

  logout: async () => {
    await SecureStore.deleteItemAsync('ravlo_token');
    delete api.defaults.headers.common['Authorization'];
    set({ user: null, token: null });
  },
}));
