import React, { useEffect, useRef } from 'react';
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
import LoanListScreen from './src/screens/LoanListScreen';
import LoanDetailScreen from './src/screens/LoanDetailScreen';
import DocumentUploadScreen from './src/screens/documents/DocumentUploadScreen';
import RavloAIScreen from './src/screens/ElenaScreen';
import ProfileScreen from './src/screens/ProfileScreen';
import OnboardingScreen from './src/screens/onboarding/OnboardingScreen';
import AdminDashboardScreen from './src/screens/admin/AdminDashboardScreen';
import AdminUsersScreen from './src/screens/admin/AdminUsersScreen';
import AdminActivityScreen from './src/screens/admin/AdminActivityScreen';

const Tab = createBottomTabNavigator();
const LoanStack = createStackNavigator();
const AdminStack = createStackNavigator();
const RootStack = createStackNavigator();

const ADMIN_ROLES = ['admin', 'platform_admin', 'master_admin', 'lending_admin', 'executive'];

function LoanNavigator() {
  return (
    <LoanStack.Navigator screenOptions={{ headerShown: false }}>
      <LoanStack.Screen name="LoanList" component={LoanListScreen} />
      <LoanStack.Screen name="LoanDetail" component={LoanDetailScreen} />
      <LoanStack.Screen name="DocumentUpload" component={DocumentUploadScreen} />
    </LoanStack.Navigator>
  );
}

function AdminNavigator() {
  return (
    <AdminStack.Navigator screenOptions={{ headerShown: false }}>
      <AdminStack.Screen name="AdminDashboard" component={AdminDashboardScreen} />
      <AdminStack.Screen name="AdminUsers" component={AdminUsersScreen} />
      <AdminStack.Screen name="AdminActivity" component={AdminActivityScreen} />
    </AdminStack.Navigator>
  );
}

function MainTabs() {
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        headerShown: false,
        tabBarStyle: styles.tabBar,
        tabBarActiveTintColor: Colors.blueprint,
        tabBarInactiveTintColor: Colors.textMuted,
        tabBarIcon: ({ color, size }) => {
          let iconName: keyof typeof Ionicons.glyphMap = 'grid-outline';
          if (route.name === 'Dashboard') iconName = 'grid-outline';
          else if (route.name === 'Loans') iconName = 'documents-outline';
          else if (route.name === 'RavloAI') iconName = 'sparkles-outline';
          else if (route.name === 'Profile') iconName = 'person-outline';
          return <Ionicons name={iconName} size={size} color={color} />;
        },
      })}
    >
      <Tab.Screen name="Dashboard" component={DashboardScreen} />
      <Tab.Screen name="Loans" component={LoanNavigator} />
      <Tab.Screen name="RavloAI" component={RavloAIScreen} options={{ tabBarLabel: 'Ravlo AI' }} />
      <Tab.Screen name="Profile" component={ProfileScreen} />
    </Tab.Navigator>
  );
}

function AdminTabs() {
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        headerShown: false,
        tabBarStyle: styles.tabBar,
        tabBarActiveTintColor: Colors.blueprint,
        tabBarInactiveTintColor: Colors.textMuted,
        tabBarIcon: ({ color, size }) => {
          let iconName: keyof typeof Ionicons.glyphMap = 'grid-outline';
          if (route.name === 'OwnerHome') iconName = 'stats-chart-outline';
          else if (route.name === 'Users') iconName = 'people-outline';
          else if (route.name === 'Activity') iconName = 'pulse-outline';
          else if (route.name === 'RavloAI') iconName = 'sparkles-outline';
          else if (route.name === 'Profile') iconName = 'person-outline';
          return <Ionicons name={iconName} size={size} color={color} />;
        },
      })}
    >
      <Tab.Screen
        name="OwnerHome"
        component={AdminNavigator}
        options={{ tabBarLabel: 'Overview' }}
      />
      <Tab.Screen
        name="Users"
        component={AdminUsersScreen}
        options={{ tabBarLabel: 'Users' }}
      />
      <Tab.Screen
        name="Activity"
        component={AdminActivityScreen}
        options={{ tabBarLabel: 'Activity' }}
      />
      <Tab.Screen
        name="RavloAI"
        component={RavloAIScreen}
        options={{ tabBarLabel: 'Ravlo AI' }}
      />
      <Tab.Screen name="Profile" component={ProfileScreen} />
    </Tab.Navigator>
  );
}

function RoleBasedTabs() {
  const { user } = useAuthStore();
  const isAdmin = ADMIN_ROLES.includes(user?.role || '');
  return isAdmin ? <AdminTabs /> : <MainTabs />;
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
    registerForPushNotifications('lending');
    const cleanup = useNotificationListeners(
      (notification) => {
        const title = notification.request.content.title || 'Ravlo Lending';
        const body = notification.request.content.body || '';
        Alert.alert(title, body);
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
                {() => (
                  <OnboardingScreen
                    onDone={() => setOnboardingDone(true)}
                  />
                )}
              </RootStack.Screen>
            ) : token ? (
              <RootStack.Screen name="Main" component={RoleBasedTabs} />
            ) : (
              <RootStack.Screen name="Login" component={LoginScreen} />
            )}
          </RootStack.Navigator>
        </NavigationContainer>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  tabBar: {
    backgroundColor: Colors.surface,
    borderTopColor: Colors.border,
    borderTopWidth: 1,
  },
});
