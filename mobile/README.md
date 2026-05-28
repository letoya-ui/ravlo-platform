# Ravlo Mobile Apps

Three standalone Expo SDK 52 apps for the Ravlo loan management platform.

## Apps

| App | Directory | Audience | Bundle ID |
|-----|-----------|----------|-----------|
| Ravlo Lending | `mobile/ravlo-lending/` | Loan officers, processors, underwriters, borrowers | `com.ravlo.lending` |
| Ravlo Investor | `mobile/ravlo-investor/` | Investors, partners/realtors | `com.ravlo.investor` |
| Ravlo Academy | `mobile/ravlo-academy/` | All users — training & education | `com.ravlo.academy` |

## Tech Stack

- **Framework:** Expo SDK 52 / React Native 0.76.5
- **Language:** TypeScript (strict mode)
- **Navigation:** React Navigation v6 (Bottom Tabs + Stack)
- **Auth state:** Zustand + expo-secure-store (JWT persisted securely)
- **API:** Axios, base URL from `EXPO_PUBLIC_API_URL` env var
- **Icons:** @expo/vector-icons (Ionicons)
- **Theme:** Dark — midnight background (`#0C1116`), blueprint primary (`#3A5C7A`)

## Running each app

```bash
# Ravlo Lending
cd mobile/ravlo-lending
npm install
npx expo start

# Ravlo Investor
cd mobile/ravlo-investor
npm install
npx expo start

# Ravlo Academy
cd mobile/ravlo-academy
npm install
npx expo start
```

## Backend API URL

Each app reads `EXPO_PUBLIC_API_URL` from the environment (falls back to `https://ravlo.app`).

Create a `.env` file in each app directory to override locally:

```
EXPO_PUBLIC_API_URL=http://192.168.1.100:5000
```

All API endpoints are under `/mobile/` — served by `LoanMVP/routes/mobile_api.py` (JWT-authenticated Flask Blueprint registered at `prefix=/mobile`).

## Backend setup

The mobile API blueprint must be registered in the main Flask app:

```python
from LoanMVP.routes.mobile_api import mobile_api
app.register_blueprint(mobile_api)
```

Required env vars on the server:
- `JWT_SECRET_KEY` (or `SECRET_KEY`) — JWT signing secret
- `ANTHROPIC_API_KEY` — for the Elena AI chat endpoint
