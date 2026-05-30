export default ({ config }) => ({
  ...config,
  name: 'Ravlo Academy',
  slug: 'ravlo-academy',
  version: '1.0.0',
  orientation: 'portrait',
  userInterfaceStyle: 'dark',
  android: {
    package: 'com.ravlohq.academy',
    adaptiveIcon: {
      backgroundColor: '#0A0F1E',
    },
  },
  ios: {
    bundleIdentifier: 'com.ravlohq.academy',
    supportsTablet: false,
  },
  extra: {
    apiUrl: process.env.EXPO_PUBLIC_API_URL ?? 'https://ravlohq.com',
    eas: {
      projectId: process.env.EAS_PROJECT_ID ?? '',
    },
  },
});
