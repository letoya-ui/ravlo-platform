# Ravlo Mobile — Setup & Deployment Guide

## Apps

| App | Bundle ID (iOS) | Package (Android) | Audience |
|-----|----------------|-------------------|----------|
| `ravlo-lending` | `com.ravlo.lending` | `com.ravlo.lending` | Loan officers, processors, underwriters, borrowers |
| `ravlo-investor` | `com.ravlo.investor` | `com.ravlo.investor` | Investors, partners, realtors |
| `ravlo-academy` | `com.ravlo.academy` | `com.ravlo.academy` | All users (training) |

---

## Local Development

```bash
# Install dependencies for a specific app
cd mobile/ravlo-lending
npm install

# Start the dev server
EXPO_PUBLIC_API_URL=https://ravlo.app npx expo start

# Or with a local backend
EXPO_PUBLIC_API_URL=http://localhost:5000 npx expo start
```

Repeat for `ravlo-investor` and `ravlo-academy`.

---

## First-time EAS Setup

Run this once per app on your machine:

```bash
# Install EAS CLI globally
npm install -g eas-cli

# Log in to Expo
eas login

# Initialize each app (creates EAS project, writes project ID to app.config.js)
cd mobile/ravlo-lending  && eas init
cd mobile/ravlo-investor && eas init
cd mobile/ravlo-academy  && eas init
```

After `eas init`, replace the `REPLACE_WITH_EAS_PROJECT_ID` placeholder in each `app.config.js` with the generated project ID.

---

## GitHub Secrets Required

Set these in **Settings → Secrets → Actions** on the GitHub repo:

| Secret | Description |
|--------|-------------|
| `EXPO_TOKEN` | Expo access token (create at expo.dev/accounts/settings/access-tokens) |
| `RAVLO_API_URL` | Production backend URL (e.g. `https://ravlo.app`) |
| `EAS_PROJECT_ID_LENDING` | EAS project ID for ravlo-lending |
| `EAS_PROJECT_ID_INVESTOR` | EAS project ID for ravlo-investor |
| `EAS_PROJECT_ID_ACADEMY` | EAS project ID for ravlo-academy |

---

## Build Profiles

| Profile | Use case | Distribution |
|---------|----------|-------------|
| `development` | Local dev with dev client | Internal (TestFlight / direct install) |
| `preview` | QA / stakeholder testing | Internal — iOS: TestFlight, Android: APK |
| `production` | App Store & Google Play submission | Public |

### Trigger a preview build manually

Go to **Actions → Ravlo Mobile — EAS Build → Run workflow**, select the app and `preview` profile.

### Trigger a production build + store submission

Select `production` profile in the workflow dispatch. The `submit` job runs automatically after a successful build.

---

## App Store Checklist (per app)

- [ ] Replace `REPLACE_WITH_APPLE_ID` in `eas.json`
- [ ] Replace `REPLACE_WITH_APP_STORE_CONNECT_APP_ID` in `eas.json`
- [ ] Replace `REPLACE_WITH_TEAM_ID` in `eas.json`
- [ ] Add `google-play-service-account.json` (Android) — download from Google Play Console
- [ ] Add app icons to `assets/icon.png` (1024×1024) and `assets/adaptive-icon.png` (Android)
- [ ] Add splash screen to `assets/splash.png`
- [ ] Run `eas init` to generate EAS project IDs
- [ ] Set all GitHub secrets listed above

---

## OTA Updates (EAS Update)

Once apps are live you can push JS-only updates without an App Store review:

```bash
cd mobile/ravlo-lending
eas update --branch production --message "Fix loan status badge"
```

Users receive the update silently on next app launch.
