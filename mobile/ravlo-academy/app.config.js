export default ({ config }) => ({
  ...config,
  name: 'Ravlo Academy',
  slug: 'ravlo-academy',
  extra: {
    apiUrl: process.env.EXPO_PUBLIC_API_URL ?? 'https://ravlo.app',
    eas: {
      projectId: process.env.EAS_PROJECT_ID_ACADEMY ?? 'REPLACE_WITH_EAS_PROJECT_ID',
    },
  },
});
