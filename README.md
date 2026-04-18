# Investment AI

Final Year Project workspace for the Investment AI platform.

## Repository Overview

This repository currently contains:

- `investai-mobile/` - React Native + Expo mobile application
- `backend/` - Backend service folder (currently scaffolded, implementation pending)

## Project Structure

```text
investment_AI/
  backend/
  investai-mobile/
    App.js
    app.json
    index.js
    package.json
    .env.example
    src/
      api/
      navigation/
      screens/
      store/
      theme/
```

## Prerequisites

Install the following before running the app:

- Node.js 18+
- npm 9+
- Expo CLI (optional globally, can use `npx expo`)
- Android Studio emulator or Expo Go app on a physical device

## Mobile App Setup (`investai-mobile`)

1. Go to the mobile folder:

```bash
cd investai-mobile
```

2. Install dependencies:

```bash
npm install
```

3. Create environment file from example:

```bash
cp .env.example .env
```

For Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

4. Update `.env` values:

- `EXPO_PUBLIC_API_BASE_URL` - Your backend API base URL (for example: `https://your-backend.up.railway.app/api/v1`)
- `EXPO_PUBLIC_FIREBASE_API_KEY` - Firebase API key used by the app

## Run the Mobile App

From `investai-mobile/`:

```bash
npm run start
```

Platform shortcuts:

```bash
npm run android
npm run ios
npm run web
```

## Backend Status

`backend/` is present for service development, but no backend source files or run scripts are committed yet.

## Notes

- Expo config is in `investai-mobile/app.json`.
- API client configuration is in `investai-mobile/src/api/`.
- Auth state management uses Zustand in `investai-mobile/src/store/authStore.js`.
