import Constants from 'expo-constants';
import * as Device from 'expo-device';
import { Platform } from 'react-native';
import { api } from './api';

const isExpoGo = Constants.appOwnership === 'expo';

// Use require() instead of import so the module only initialises when NOT in
// Expo Go. Static imports always run module-level side effects immediately,
// but expo-notifications throws during its own init in Expo Go SDK 53+.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let Notifications: any = null;

if (!isExpoGo) {
  try {
    Notifications = require('expo-notifications');
    Notifications.setNotificationHandler({
      handleNotification: async () => ({
        shouldShowAlert: true,
        shouldPlaySound: true,
        shouldSetBadge: true,
      }),
    });
  } catch {
    // not available
  }
}

export async function registerForPushNotifications(
  appName: 'lending' | 'investor' | 'academy'
): Promise<string | null> {
  if (!Notifications || !Device.isDevice) return null;

  try {
    const { status: existingStatus } = await Notifications.getPermissionsAsync();
    let finalStatus = existingStatus;

    if (existingStatus !== 'granted') {
      const { status } = await Notifications.requestPermissionsAsync();
      finalStatus = status;
    }

    if (finalStatus !== 'granted') return null;

    if (Platform.OS === 'android') {
      await Notifications.setNotificationChannelAsync('default', {
        name: 'Default',
        importance: Notifications.AndroidImportance.MAX,
        vibrationPattern: [0, 250, 250, 250],
      });
    }

    const token = (await Notifications.getExpoPushTokenAsync()).data;

    try {
      await api.post('/mobile/notifications/register', {
        push_token: token,
        platform: Platform.OS,
        app: appName,
      });
    } catch (e) {
      console.warn('Failed to register push token', e);
    }

    return token;
  } catch (e) {
    console.warn('Push notification registration error', e);
    return null;
  }
}

export function useNotificationListeners(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  onNotification: (n: any) => void,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  onResponse: (r: any) => void
): () => void {
  if (!Notifications) return () => {};
  const notifSub = Notifications.addNotificationReceivedListener(onNotification);
  const responseSub = Notifications.addNotificationResponseReceivedListener(onResponse);
  return () => {
    notifSub.remove();
    responseSub.remove();
  };
}
