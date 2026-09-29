import React, { useCallback, useEffect, useRef } from 'react';
import { Platform } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { NavigationContainer, createNavigationContainerRef } from '@react-navigation/native';
import {
  useFonts,
  Roboto_100Thin,
  Roboto_100Thin_Italic,
  Roboto_300Light,
  Roboto_300Light_Italic,
  Roboto_400Regular,
  Roboto_400Regular_Italic,
  Roboto_500Medium,
  Roboto_500Medium_Italic,
  Roboto_700Bold,
  Roboto_700Bold_Italic,
  Roboto_900Black,
  Roboto_900Black_Italic,
  Roboto_800ExtraBold
} from '@expo-google-fonts/roboto';
import * as SplashScreenLib from 'expo-splash-screen';
import AppNavigator from './src/navigation/AppNavigator';
import { useAuthStore } from './src/store/authStore';
import { useLanguageStore } from './src/store/languageStore';
import { pushApi } from './src/api/api';
import { ToastHost } from './src/components/Toast';

const navigationRef = createNavigationContainerRef();

// Keep the splash screen visible while we fetch resources
SplashScreenLib.preventAutoHideAsync();

export default function App() {
  const restoreSession = useAuthStore(state => state.restoreSession);
  const initLanguage = useLanguageStore(state => state.init);

  useEffect(() => {
    restoreSession();
    // Loads the saved UI language before the first screen renders, so a
    // Sinhala/Tamil user never sees an English flash (I-15).
    initLanguage();
  }, []);

  // A tapped push opens the Alerts tab. The tap can arrive before the signed-in
  // stack exists (cold start, session still restoring, first-run assessment),
  // so it is held until the root route is MainTab and retried on every
  // navigation state change.
  const pendingAlerts = useRef(false);
  const openPendingAlerts = useCallback(() => {
    if (!pendingAlerts.current || !navigationRef.isReady()) return;
    const root = navigationRef.getRootState();
    if (root?.routes?.[root.index]?.name !== 'MainTab') return;
    pendingAlerts.current = false;
    navigationRef.navigate('MainTab', { screen: 'Alerts' });
  }, []);

  useEffect(() => {
    // Lazy-required for the same reason as in api.js: no native module on web.
    if (Platform.OS === 'web') return undefined;
    const Notifications = require('expo-notifications');
    const openAlerts = () => { pendingAlerts.current = true; openPendingAlerts(); };
    const responseSub = Notifications.addNotificationResponseReceivedListener(openAlerts);
    // Cold start: the tap that launched the app fired before the listener existed.
    Notifications.getLastNotificationResponseAsync()
      .then(response => {
        if (!response) return;
        openAlerts();
        Notifications.clearLastNotificationResponseAsync().catch(() => {});
      })
      .catch(() => {});
    // FCM rotates tokens; send the new one while signed in.
    const tokenSub = Notifications.addPushTokenListener(() => {
      if (useAuthStore.getState().isAuthenticated) pushApi.register();
    });
    return () => { responseSub.remove(); tokenSub.remove(); };
  }, [openPendingAlerts]);
  const [fontsLoaded] = useFonts({
    Roboto_100Thin,
    Roboto_100Thin_Italic,
    Roboto_300Light,
    Roboto_300Light_Italic,
    Roboto_400Regular,
    Roboto_400Regular_Italic,
    Roboto_500Medium,
    Roboto_500Medium_Italic,
    Roboto_700Bold,
    Roboto_700Bold_Italic,
    Roboto_900Black,
    Roboto_900Black_Italic,
    Roboto_800ExtraBold,
    'Satoshi-Light': require('./assets/fonts/satoshi/Satoshi-Light.otf'),
    'Satoshi-Regular': require('./assets/fonts/satoshi/Satoshi-Regular.otf'),
    'Satoshi-Medium': require('./assets/fonts/satoshi/Satoshi-Medium.otf'),
    'Satoshi-Bold': require('./assets/fonts/satoshi/Satoshi-Bold.otf'),
    'Satoshi-Black': require('./assets/fonts/satoshi/Satoshi-Black.otf'),
  });

  const onLayoutRootView = React.useCallback(async () => {
    if (fontsLoaded) {
      await SplashScreenLib.hideAsync();
    }
  }, [fontsLoaded]);

  if (!fontsLoaded) {
    return null;
  }

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider onLayout={onLayoutRootView}>
        <NavigationContainer ref={navigationRef} onReady={openPendingAlerts} onStateChange={openPendingAlerts}>
          <AppNavigator />
        </NavigationContainer>
        <ToastHost />
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
