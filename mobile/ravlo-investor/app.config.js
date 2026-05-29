export default ({ config }) => ({
  ...config,
  name: 'Ravlo Investor',
  slug: 'ravlo-investor',
  extra: {
    apiUrl: process.env.EXPO_PUBLIC_API_URL ?? 'https://ravlo.app',
    eas: {
      projectId: process.env.EAS_PROJECT_ID_INVESTOR ?? 'REPLACE_WITH_EAS_PROJECT_ID',
    },
  },
});
