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
import HomeScreen from './src/screens/HomeScreen';
import LearnScreen from './src/screens/LearnScreen';
import ModuleDetailScreen from './src/screens/ModuleDetailScreen';
import LessonScreen from './src/screens/LessonScreen';
import ProgressScreen from './src/screens/ProgressScreen';
import ProfileScreen from './src/screens/ProfileScreen';
import RavloAIScreen from './src/screens/RavloAIScreen';
import BusinessPlanScreen from './src/screens/BusinessPlanScreen';
import OnboardingScreen from './src/screens/onboarding/OnboardingScreen';
import AvenueSelectionScreen from './src/screens/onboarding/AvenueSelectionScreen';
import AvenueUpgradeScreen from './src/screens/AvenueUpgradeScreen';

const Tab = createBottomTabNavigator();
const LearnStack = createStackNavigator();
const RootStack = createStackNavigator();

const TAB_OPTIONS = {
  tabBarStyle: { backgroundColor: Colors.surface, borderTopColor: Colors.border, borderTopWidth: 1 },
  tabBarActiveTintColor: Colors.blueprint,
  tabBarInactiveTintColor: Colors.textMuted,
  headerShown: false,
};

function LearnNavigator() {
  return (
    <LearnStack.Navigator screenOptions={{ headerShown: false }}>
      <LearnStack.Screen name="LearnHome" component={LearnScreen} />
      <LearnStack.Screen name="ModuleDetail" component={ModuleDetailScreen} />
      <LearnStack.Screen name="Lesson" component={LessonScreen} />
      <LearnStack.Screen name="AvenueUpgrade" component={AvenueUpgradeScreen} />
    </LearnStack.Navigator>
  );
}

function MainTabs() {
  return (
    <Tab.Navigator screenOptions={TAB_OPTIONS}>
      <Tab.Screen
        name="Home"
        component={HomeScreen}
        options={{ tabBarIcon: ({ color, size }) => <Ionicons name="home-outline" size={size} color={color} /> }}
      />
      <Tab.Screen
        name="Learn"
        component={LearnNavigator}
        options={{ tabBarIcon: ({ color, size }) => <Ionicons name="book-outline" size={size} color={color} /> }}
      />
      <Tab.Screen
        name="Coach"
        component={RavloAIScreen}
        options={{ tabBarLabel: 'AI Coach', tabBarIcon: ({ color, size }) => <Ionicons name="sparkles-outline" size={size} color={color} /> }}
      />
      <Tab.Screen
        name="Plan"
        component={BusinessPlanScreen}
        options={{ tabBarLabel: 'Biz Plan', tabBarIcon: ({ color, size }) => <Ionicons name="document-text-outline" size={size} color={color} /> }}
      />
      <Tab.Screen
        name="Progress"
        component={ProgressScreen}
        options={{ tabBarIcon: ({ color, size }) => <Ionicons name="bar-chart-outline" size={size} color={color} /> }}
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
  const { token, user, loadToken } = useAuthStore();
  const [onboardingDone, setOnboardingDone] = React.useState<boolean | null>(null);
  const [avenueSelected, setAvenueSelected] = React.useState<boolean>(false);

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
    registerForPushNotifications('academy');
    const cleanup = useNotificationListeners(
      (notification) => {
        Alert.alert(
          notification.request.content.title || 'Ravlo Academy',
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
            ) : !token ? (
              <RootStack.Screen name="Login" component={LoginScreen} />
            ) : !user?.chosen_avenue && !avenueSelected ? (
              <RootStack.Screen name="AvenueSelection">
                {() => <AvenueSelectionScreen onDone={() => setAvenueSelected(true)} />}
              </RootStack.Screen>
            ) : (
              <RootStack.Screen name="Main" component={MainTabs} />
            )}
          </RootStack.Navigator>
        </NavigationContainer>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}

const styles = StyleSheet.create({ root: { flex: 1 } });
