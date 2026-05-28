// Dynamic config — extends app.json and injects env vars for EAS builds.
// EAS project ID: run `eas init` inside this directory to populate it.
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
  updates: {
    url: `https://u.expo.dev/${process.env.EAS_PROJECT_ID_INVESTOR ?? 'REPLACE_WITH_EAS_PROJECT_ID'}`,
  },
  runtimeVersion: {
    policy: 'appVersion',
  },
});
