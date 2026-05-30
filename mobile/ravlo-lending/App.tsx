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

// ── Shared screens ──────────────────────────────────────────────────────────
import LoginScreen from './src/screens/LoginScreen';
import ProfileScreen from './src/screens/ProfileScreen';
import OnboardingScreen from './src/screens/onboarding/OnboardingScreen';
import DocumentUploadScreen from './src/screens/documents/DocumentUploadScreen';
import MessagesScreen from './src/screens/MessagesScreen';
import MessageThreadScreen from './src/screens/MessageThreadScreen';
import MoreScreen from './src/screens/MoreScreen';
import ElenaScreen from './src/screens/ElenaScreen';

// ── Admin screens ────────────────────────────────────────────────────────────
import AdminDashboardScreen from './src/screens/admin/AdminDashboardScreen';
import AdminUsersScreen from './src/screens/admin/AdminUsersScreen';
import AdminActivityScreen from './src/screens/admin/AdminActivityScreen';

// ── Loan Officer / shared pipeline screens ───────────────────────────────────
import DashboardScreen from './src/screens/DashboardScreen';
import LoanListScreen from './src/screens/LoanListScreen';
import LoanDetailScreen from './src/screens/LoanDetailScreen';
import LeadsScreen from './src/screens/LeadsScreen';
import LeadDetailScreen from './src/screens/LeadDetailScreen';
import BorrowersScreen from './src/screens/BorrowersScreen';
import TasksScreen from './src/screens/TasksScreen';

// ── Processor screens ────────────────────────────────────────────────────────
import ProcessorQueueScreen from './src/screens/processor/ProcessorQueueScreen';
import ProcessorConditionsScreen from './src/screens/processor/ProcessorConditionsScreen';
import ProcessorLoanDetailScreen from './src/screens/processor/ProcessorLoanDetailScreen';

// ── Underwriter screens ──────────────────────────────────────────────────────
import UnderwriterQueueScreen from './src/screens/underwriter/UnderwriterQueueScreen';
import UnderwriterLoanReviewScreen from './src/screens/underwriter/UnderwriterLoanReviewScreen';

// ── Borrower screens ─────────────────────────────────────────────────────────
import BorrowerDashboardScreen from './src/screens/borrower/BorrowerDashboardScreen';
import BorrowerLoanDetailScreen from './src/screens/borrower/BorrowerLoanDetailScreen';
import BorrowerConditionsScreen from './src/screens/borrower/BorrowerConditionsScreen';

// ─── Navigators ──────────────────────────────────────────────────────────────

const Tab = createBottomTabNavigator();
const Stack = createStackNavigator();
const RootStack = createStackNavigator();

const TAB_OPTIONS = {
  tabBarStyle: { backgroundColor: Colors.surface, borderTopColor: Colors.border, borderTopWidth: 1 },
  tabBarActiveTintColor: Colors.blueprint,
  tabBarInactiveTintColor: Colors.textMuted,
  headerShown: false,
};

// ── Stack navigators ─────────────────────────────────────────────────────────

function LoanNavigator() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="LoanList" component={LoanListScreen} />
      <Stack.Screen name="LoanDetail" component={LoanDetailScreen} />
      <Stack.Screen name="DocumentUpload" component={DocumentUploadScreen} />
    </Stack.Navigator>
  );
}

function LeadNavigator() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="LeadList" component={LeadsScreen} />
      <Stack.Screen name="LeadDetail" component={LeadDetailScreen} />
    </Stack.Navigator>
  );
}

function MessagesNavigator() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="MessagesList" component={MessagesScreen} />
      <Stack.Screen name="MessageThread" component={MessageThreadScreen} />
    </Stack.Navigator>
  );
}

function MoreNavigator() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="MoreMenu" component={MoreScreen} />
      <Stack.Screen name="Tasks" component={TasksScreen} />
      <Stack.Screen name="Messages" component={MessagesScreen} />
      <Stack.Screen name="MessageThread" component={MessageThreadScreen} />
      <Stack.Screen name="RavloAI" component={ElenaScreen} />
      <Stack.Screen name="Profile" component={ProfileScreen} />
      <Stack.Screen name="DocumentUpload" component={DocumentUploadScreen} />
    </Stack.Navigator>
  );
}

function AdminNavigator() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="AdminDashboard" component={AdminDashboardScreen} />
      <Stack.Screen name="AdminUsers" component={AdminUsersScreen} />
      <Stack.Screen name="AdminActivity" component={AdminActivityScreen} />
    </Stack.Navigator>
  );
}

function ProcessorQueueNavigator() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="ProcessorQueue" component={ProcessorQueueScreen} />
      <Stack.Screen name="ProcessorLoanDetail" component={ProcessorLoanDetailScreen} />
    </Stack.Navigator>
  );
}

function UnderwriterQueueNavigator() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="UnderwriterQueue" component={UnderwriterQueueScreen} />
      <Stack.Screen name="UnderwriterLoanReview" component={UnderwriterLoanReviewScreen} />
    </Stack.Navigator>
  );
}

function BorrowerHomeNavigator() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="BorrowerDashboard" component={BorrowerDashboardScreen} />
      <Stack.Screen name="BorrowerLoanDetail" component={BorrowerLoanDetailScreen} />
      <Stack.Screen name="DocumentUpload" component={DocumentUploadScreen} />
      <Stack.Screen name="Messages" component={MessagesScreen} />
      <Stack.Screen name="MessageThread" component={MessageThreadScreen} />
    </Stack.Navigator>
  );
}

// ── Tab sets ──────────────────────────────────────────────────────────────────

function AdminTabs() {
  return (
    <Tab.Navigator screenOptions={TAB_OPTIONS}>
      <Tab.Screen
        name="OwnerHome"
        component={AdminNavigator}
        options={{ tabBarLabel: 'Overview', tabBarIcon: ({ color, size }) => <Ionicons name="stats-chart-outline" size={size} color={color} /> }}
      />
      <Tab.Screen
        name="Pipeline"
        component={LoanNavigator}
        options={{ tabBarIcon: ({ color, size }) => <Ionicons name="layers-outline" size={size} color={color} /> }}
      />
      <Tab.Screen
        name="Users"
        component={AdminUsersScreen}
        options={{ tabBarIcon: ({ color, size }) => <Ionicons name="people-outline" size={size} color={color} /> }}
      />
      <Tab.Screen
        name="Activity"
        component={AdminActivityScreen}
        options={{ tabBarIcon: ({ color, size }) => <Ionicons name="pulse-outline" size={size} color={color} /> }}
      />
      <Tab.Screen
        name="AdminMore"
        component={MoreNavigator}
        options={{ tabBarLabel: 'More', tabBarIcon: ({ color, size }) => <Ionicons name="ellipsis-horizontal-outline" size={size} color={color} /> }}
      />
    </Tab.Navigator>
  );
}

function LoanOfficerTabs() {
  return (
    <Tab.Navigator screenOptions={TAB_OPTIONS}>
      <Tab.Screen
        name="Dashboard"
        component={DashboardScreen}
        options={{ tabBarIcon: ({ color, size }) => <Ionicons name="grid-outline" size={size} color={color} /> }}
      />
      <Tab.Screen
        name="Leads"
        component={LeadNavigator}
        options={{ tabBarIcon: ({ color, size }) => <Ionicons name="people-outline" size={size} color={color} /> }}
      />
      <Tab.Screen
        name="Pipeline"
        component={LoanNavigator}
        options={{ tabBarIcon: ({ color, size }) => <Ionicons name="layers-outline" size={size} color={color} /> }}
      />
      <Tab.Screen
        name="Borrowers"
        component={BorrowersScreen}
        options={{ tabBarIcon: ({ color, size }) => <Ionicons name="person-circle-outline" size={size} color={color} /> }}
      />
      <Tab.Screen
        name="More"
        component={MoreNavigator}
        options={{ tabBarIcon: ({ color, size }) => <Ionicons name="ellipsis-horizontal-outline" size={size} color={color} /> }}
      />
    </Tab.Navigator>
  );
}

function ProcessorTabs() {
  return (
    <Tab.Navigator screenOptions={TAB_OPTIONS}>
      <Tab.Screen
        name="Queue"
        component={ProcessorQueueNavigator}
        options={{ tabBarIcon: ({ color, size }) => <Ionicons name="list-outline" size={size} color={color} /> }}
      />
      <Tab.Screen
        name="Conditions"
        component={ProcessorConditionsScreen}
        options={{ tabBarIcon: ({ color, size }) => <Ionicons name="checkmark-done-outline" size={size} color={color} /> }}
      />
      <Tab.Screen
        name="Messages"
        component={MessagesNavigator}
        options={{ tabBarIcon: ({ color, size }) => <Ionicons name="chatbubbles-outline" size={size} color={color} /> }}
      />
      <Tab.Screen
        name="ProcessorMore"
        component={MoreNavigator}
        options={{ tabBarLabel: 'More', tabBarIcon: ({ color, size }) => <Ionicons name="ellipsis-horizontal-outline" size={size} color={color} /> }}
      />
    </Tab.Navigator>
  );
}

function UnderwriterTabs() {
  return (
    <Tab.Navigator screenOptions={TAB_OPTIONS}>
      <Tab.Screen
        name="UWQueue"
        component={UnderwriterQueueNavigator}
        options={{ tabBarLabel: 'Queue', tabBarIcon: ({ color, size }) => <Ionicons name="documents-outline" size={size} color={color} /> }}
      />
      <Tab.Screen
        name="Messages"
        component={MessagesNavigator}
        options={{ tabBarIcon: ({ color, size }) => <Ionicons name="chatbubbles-outline" size={size} color={color} /> }}
      />
      <Tab.Screen
        name="UWMore"
        component={MoreNavigator}
        options={{ tabBarLabel: 'More', tabBarIcon: ({ color, size }) => <Ionicons name="ellipsis-horizontal-outline" size={size} color={color} /> }}
      />
    </Tab.Navigator>
  );
}

function BorrowerTabs() {
  return (
    <Tab.Navigator screenOptions={TAB_OPTIONS}>
      <Tab.Screen
        name="BorrowerHome"
        component={BorrowerHomeNavigator}
        options={{ tabBarLabel: 'Home', tabBarIcon: ({ color, size }) => <Ionicons name="home-outline" size={size} color={color} /> }}
      />
      <Tab.Screen
        name="Conditions"
        component={BorrowerConditionsScreen}
        options={{ tabBarIcon: ({ color, size }) => <Ionicons name="checkmark-circle-outline" size={size} color={color} /> }}
      />
      <Tab.Screen
        name="BorrowerMessages"
        component={MessagesNavigator}
        options={{ tabBarLabel: 'Messages', tabBarIcon: ({ color, size }) => <Ionicons name="chatbubbles-outline" size={size} color={color} /> }}
      />
      <Tab.Screen
        name="BorrowerMore"
        component={MoreNavigator}
        options={{ tabBarLabel: 'More', tabBarIcon: ({ color, size }) => <Ionicons name="ellipsis-horizontal-outline" size={size} color={color} /> }}
      />
    </Tab.Navigator>
  );
}

// ─── Role-based dispatcher ────────────────────────────────────────────────────

const ADMIN_ROLES = ['admin', 'platform_admin', 'master_admin', 'lending_admin', 'executive'];

function RoleBasedTabs() {
  const { user } = useAuthStore();
  const role = user?.role || '';
  if (ADMIN_ROLES.includes(role)) return <AdminTabs />;
  if (role === 'loan_officer') return <LoanOfficerTabs />;
  if (role === 'processor') return <ProcessorTabs />;
  if (role === 'underwriter') return <UnderwriterTabs />;
  if (role === 'borrower') return <BorrowerTabs />;
  // Fallback: loan officer view for any unrecognised internal role
  return <LoanOfficerTabs />;
}

// ─── Root App ─────────────────────────────────────────────────────────────────

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
        Alert.alert(
          notification.request.content.title || 'Ravlo Lending',
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

const styles = StyleSheet.create({ root: { flex: 1 } });
