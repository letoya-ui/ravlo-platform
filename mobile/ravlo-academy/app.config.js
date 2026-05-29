export default ({ config }) => ({
  ...config,
  name: 'Ravlo Academy',
  slug: 'ravlo-academy',
  extra: {
    apiUrl: process.env.EXPO_PUBLIC_API_URL ?? 'https://ravlo.app',
  },
});
