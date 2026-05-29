export default ({ config }) => ({
  ...config,
  name: 'Ravlo Lending',
  slug: 'ravlo-lending',
  extra: {
    apiUrl: process.env.EXPO_PUBLIC_API_URL ?? 'https://ravlohq.com',
  },
});
