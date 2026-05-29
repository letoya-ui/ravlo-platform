import * as Notifications from 'expo-notifications';
import * as Device from 'expo-device';
import Constants from 'expo-constants';
import { Platform } from 'react-native';
import { api } from './api';

const isExpoGo = Constants.appOwnership === 'expo';

if (!isExpoGo) {
  Notifications.setNotificationHandler({
    handleNotification: async () => ({
      shouldShowAlert: true,
      shouldPlaySound: true,
      shouldSetBadge: true,
    }),
  });
}

export async function registerForPushNotifications(
  appName: 'lending' | 'investor' | 'academy'
): Promise<string | null> {
  if (isExpoGo) return null;
  if (!Device.isDevice) return null;

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
  onNotification: (n: Notifications.Notification) => void,
  onResponse: (r: Notifications.NotificationResponse) => void
): () => void {
  if (isExpoGo) return () => {};
  const notifSub = Notifications.addNotificationReceivedListener(onNotification);
  const responseSub = Notifications.addNotificationResponseReceivedListener(onResponse);
  return () => {
    notifSub.remove();
    responseSub.remove();
  };
}
