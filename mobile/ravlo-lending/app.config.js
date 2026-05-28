// Dynamic config — extends app.json and injects env vars for EAS builds.
// EAS project ID: run `eas init` inside this directory to populate it.
export default ({ config }) => ({
  ...config,
  name: 'Ravlo Lending',
  slug: 'ravlo-lending',
  extra: {
    apiUrl: process.env.EXPO_PUBLIC_API_URL ?? 'https://ravlo.app',
    eas: {
      projectId: 'b8210393-8f43-46eb-bb63-92871f4cb7f0',
    },
  },
});