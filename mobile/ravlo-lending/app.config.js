export default ({ config }) => ({
  ...config,
  name: 'Ravlo Lending',
  slug: 'ravlo-lending',
  owner: 'letoyamason',
  version: '1.0.0',
  orientation: 'portrait',
  userInterfaceStyle: 'dark',
  android: {
    package: 'com.ravlohq.lending',
    adaptiveIcon: {
      backgroundColor: '#0A0F1E',
    },
  },
  ios: {
    bundleIdentifier: 'com.ravlohq.lending',
    supportsTablet: false,
  },
  extra: {
    apiUrl: process.env.EXPO_PUBLIC_API_URL ?? 'https://ravlohq.com',
    eas: {
      projectId: process.env.EAS_PROJECT_ID || config?.extra?.eas?.projectId || '',
    },
  },
});
