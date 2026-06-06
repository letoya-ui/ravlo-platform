import { create } from 'zustand';
import * as SecureStore from 'expo-secure-store';
import * as LocalAuthentication from 'expo-local-authentication';
import { Alert } from 'react-native';
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
  chosen_avenue: string | null;
  unlocked_avenues: string[];
  onboarding_complete: boolean;
}

interface AuthState {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  error: string | null;
  biometricAvailable: boolean;
  biometricEnabled: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  loadToken: () => Promise<void>;
  checkBiometric: () => Promise<void>;
  enableBiometric: () => Promise<void>;
  disableBiometric: () => Promise<void>;
  authenticateWithBiometric: () => Promise<boolean>;
  setChosenAvenue: (avenueId: string) => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  token: null,
  isLoading: false,
  error: null,
  biometricAvailable: false,
  biometricEnabled: false,

  checkBiometric: async () => {
    try {
      const compatible = await LocalAuthentication.hasHardwareAsync();
      const enrolled = await LocalAuthentication.isEnrolledAsync();
      const available = compatible && enrolled;
      const enabledVal = await SecureStore.getItemAsync('ravlo_biometric_enabled');
      set({ biometricAvailable: available, biometricEnabled: enabledVal === 'true' });
    } catch {
      set({ biometricAvailable: false, biometricEnabled: false });
    }
  },

  enableBiometric: async () => {
    try {
      await SecureStore.setItemAsync('ravlo_biometric_enabled', 'true');
      set({ biometricEnabled: true });
    } catch {
      // ignore
    }
  },

  disableBiometric: async () => {
    try {
      await SecureStore.deleteItemAsync('ravlo_biometric_enabled');
      set({ biometricEnabled: false });
    } catch {
      // ignore
    }
  },

  authenticateWithBiometric: async () => {
    try {
      const result = await LocalAuthentication.authenticateAsync({
        promptMessage: 'Sign in to Ravlo Academy',
        fallbackLabel: 'Use Password',
        cancelLabel: 'Cancel',
      });
      return result.success;
    } catch {
      return false;
    }
  },

  loadToken: async () => {
    try {
      const token = await SecureStore.getItemAsync('ravlo_token');
      if (token) {
        const enabledVal = await SecureStore.getItemAsync('ravlo_biometric_enabled');
        if (enabledVal === 'true') {
          const compatible = await LocalAuthentication.hasHardwareAsync();
          const enrolled = await LocalAuthentication.isEnrolledAsync();
          if (compatible && enrolled) {
            const result = await LocalAuthentication.authenticateAsync({
              promptMessage: 'Sign in to Ravlo Academy',
              fallbackLabel: 'Use Password',
              cancelLabel: 'Cancel',
            });
            if (!result.success) {
              await SecureStore.deleteItemAsync('ravlo_token');
              set({ biometricAvailable: compatible && enrolled, biometricEnabled: true });
              return;
            }
          }
        }
        api.defaults.headers.common['Authorization'] = `Bearer ${token}`;
        const res = await api.get('/mobile/auth/me');
        const compatible = await LocalAuthentication.hasHardwareAsync();
        const enrolled = await LocalAuthentication.isEnrolledAsync();
        const enabledFinal = await SecureStore.getItemAsync('ravlo_biometric_enabled');
        set({
          token,
          user: res.data.user,
          biometricAvailable: compatible && enrolled,
          biometricEnabled: enabledFinal === 'true',
        });
      } else {
        const compatible = await LocalAuthentication.hasHardwareAsync();
        const enrolled = await LocalAuthentication.isEnrolledAsync();
        const enabledVal = await SecureStore.getItemAsync('ravlo_biometric_enabled');
        set({ biometricAvailable: compatible && enrolled, biometricEnabled: enabledVal === 'true' });
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

      const compatible = await LocalAuthentication.hasHardwareAsync();
      const enrolled = await LocalAuthentication.isEnrolledAsync();
      if (compatible && enrolled) {
        set({ biometricAvailable: true });
        const alreadyEnabled = await SecureStore.getItemAsync('ravlo_biometric_enabled');
        if (alreadyEnabled !== 'true') {
          Alert.alert(
            'Enable Face ID / Touch ID?',
            'Sign in faster next time without entering your password.',
            [
              {
                text: 'Not Now',
                style: 'cancel',
              },
              {
                text: 'Enable',
                onPress: async () => {
                  await SecureStore.setItemAsync('ravlo_biometric_enabled', 'true');
                  set({ biometricEnabled: true });
                },
              },
            ]
          );
        }
      }
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

  setChosenAvenue: (avenueId: string) => {
    set(state => ({
      user: state.user ? { ...state.user, chosen_avenue: avenueId } : state.user,
    }));
  },
}));
