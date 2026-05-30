import React, { useEffect } from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { createStackNavigator } from '@react-navigation/stack';
import { Ionicons } from '@expo/vector-icons';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { Alert, StyleSheet } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';

import { Colors } from './src/theme';
import { useAuthStore } from './src/store/authStore';
import { registerForPushNotifications, useNotificationListeners } from './src/services/notifications';
import LoginScreen from './src/screens/LoginScreen';
import DashboardScreen from './src/screens/DashboardScreen';
import DealsScreen from './src/screens/DealsScreen';
import DealDetailScreen from './src/screens/DealDetailScreen';
import OpportunitiesScreen from './src/screens/OpportunitiesScreen';
import PartnerScreen from './src/screens/PartnerScreen';
import ProfileScreen from './src/screens/ProfileScreen';
import RavloAIScreen from './src/screens/RavloAIScreen';
import OnboardingScreen from './src/screens/onboarding/OnboardingScreen';

const Tab = createBottomTabNavigator();
const Stack = createStackNavigator();
const RootStack = createStackNavigator();

const TAB_OPTIONS = {
  tabBarStyle: { backgroundColor: Colors.surface, borderTopColor: Colors.border, borderTopWidth: 1 },
  tabBarActiveTintColor: Colors.blueprint,
  tabBarInactiveTintColor: Colors.textMuted,
  headerShown: false,
};

function DealNavigator() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="DealList" component={DealsScreen} />
      <Stack.Screen name="DealDetail" component={DealDetailScreen} />
    </Stack.Navigator>
  );
}

function MainTabs() {
  return (
    <Tab.Navigator screenOptions={TAB_OPTIONS}>
      <Tab.Screen
        name="Dashboard"
        component={DashboardScreen}
        options={{ tabBarIcon: ({ color, size }) => <Ionicons name="grid-outline" size={size} color={color} /> }}
      />
      <Tab.Screen
        name="Deals"
        component={DealNavigator}
        options={{ tabBarIcon: ({ color, size }) => <Ionicons name="layers-outline" size={size} color={color} /> }}
      />
      <Tab.Screen
        name="Opportunities"
        component={OpportunitiesScreen}
        options={{ tabBarIcon: ({ color, size }) => <Ionicons name="search-outline" size={size} color={color} /> }}
      />
      <Tab.Screen
        name="RavloAI"
        component={RavloAIScreen}
        options={{ tabBarLabel: 'Ravlo AI', tabBarIcon: ({ color, size }) => <Ionicons name="sparkles-outline" size={size} color={color} /> }}
      />
      <Tab.Screen
        name="Profile"
        component={ProfileScreen}
        options={{ tabBarIcon: ({ color, size }) => <Ionicons name="person-outline" size={size} color={color} /> }}
      />
    </Tab.Navigator>
  );
}

export default function App() {
  const { token, loadToken } = useAuthStore();
  const [onboardingDone, setOnboardingDone] = React.useState<boolean | null>(null);

  useEffect(() => {
    const init = async () => {
      try {
        const done = await AsyncStorage.getItem('ravlo_onboarding_done');
        setOnboardingDone(done === 'true');
      } catch {
        setOnboardingDone(true);
      }
      await loadToken();
    };
    init();
  }, []);

  useEffect(() => {
    if (!token) return;
    registerForPushNotifications('investor');
    const cleanup = useNotificationListeners(
      (notification) => {
        Alert.alert(
          notification.request.content.title || 'Ravlo Investor',
          notification.request.content.body || '',
        );
      },
      (response) => {
        console.log('Notification tapped:', response.notification.request.content);
      }
    );
    return cleanup;
  }, [token]);

  if (onboardingDone === null) return null;

  return (
    <GestureHandlerRootView style={styles.root}>
      <SafeAreaProvider>
        <NavigationContainer>
          <RootStack.Navigator screenOptions={{ headerShown: false }}>
            {!onboardingDone ? (
              <RootStack.Screen name="Onboarding">
                {() => <OnboardingScreen onDone={() => setOnboardingDone(true)} />}
              </RootStack.Screen>
            ) : token ? (
              <RootStack.Screen name="Main" component={MainTabs} />
            ) : (
              <RootStack.Screen name="Login" component={LoginScreen} />
            )}
          </RootStack.Navigator>
        </NavigationContainer>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}

const styles = StyleSheet.create({ root: { flex: 1 } });
