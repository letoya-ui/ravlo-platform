import axios from 'axios';
const BASE_URL = process.env.EXPO_PUBLIC_API_URL || 'https://ravlohq.com';
export const api = axios.create({
  baseURL: BASE_URL,
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
});
