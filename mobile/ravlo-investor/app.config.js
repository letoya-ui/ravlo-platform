export default ({ config }) => ({
  ...config,
  name: 'Ravlo Investor',
  slug: 'ravlo-investor',
  extra: {
    apiUrl: process.env.EXPO_PUBLIC_API_URL ?? 'https://ravlohq.com',
  },
});
