import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ScrollView, Alert } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radii, Typography } from '../theme';
import { useAuthStore } from '../store/authStore';

const MENU_ITEMS = [
  { icon: 'checkmark-circle-outline', label: 'Tasks', screen: 'Tasks', color: Colors.success },
  { icon: 'chatbubbles-outline', label: 'Messages', screen: 'Messages', color: Colors.info },
  { icon: 'sparkles-outline', label: 'Ravlo AI', screen: 'RavloAI', color: Colors.warning },
  { icon: 'document-text-outline', label: 'Documents', screen: 'DocumentUpload', color: Colors.blueprint },
  { icon: 'person-outline', label: 'Profile', screen: 'Profile', color: Colors.softGlow },
];

export default function MoreScreen({ navigation }: any) {
  const { user, logout } = useAuthStore();

  const handleSignOut = () => {
    Alert.alert('Sign Out', 'Are you sure you want to sign out?', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Sign Out', style: 'destructive', onPress: logout },
    ]);
  };

  const roleLabel = (user?.role || '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <Text style={styles.title}>More</Text>

        {/* User card */}
        <View style={styles.userCard}>
          <View style={styles.userAvatar}>
            <Text style={styles.userAvatarText}>
              {((user?.first_name || '?')[0] + (user?.last_name || '?')[0]).toUpperCase()}
            </Text>
          </View>
          <View style={styles.userInfo}>
            <Text style={styles.userName}>{user?.first_name} {user?.last_name}</Text>
            <Text style={styles.userEmail}>{user?.email}</Text>
            <View style={styles.roleBadge}>
              <Text style={styles.roleText}>{roleLabel}</Text>
            </View>
          </View>
        </View>

        {/* Menu grid */}
        <View style={styles.grid}>
          {MENU_ITEMS.map(item => (
            <TouchableOpacity
              key={item.screen}
              style={styles.menuItem}
              onPress={() => navigation.navigate(item.screen)}
              activeOpacity={0.75}
            >
              <View style={[styles.menuIcon, { backgroundColor: item.color + '22' }]}>
                <Ionicons name={item.icon as any} size={24} color={item.color} />
              </View>
              <Text style={styles.menuLabel}>{item.label}</Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Sign out */}
        <TouchableOpacity style={styles.signOutBtn} onPress={handleSignOut} activeOpacity={0.75}>
          <Ionicons name="log-out-outline" size={20} color={Colors.danger} />
          <Text style={styles.signOutText}>Sign Out</Text>
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  scroll: { padding: Spacing.lg, paddingBottom: Spacing.xxl },
  title: { ...Typography.h2, color: Colors.textPrimary, marginBottom: Spacing.lg },
  userCard: { flexDirection: 'row', alignItems: 'center', backgroundColor: Colors.surface, borderRadius: Radii.md, padding: Spacing.md, borderWidth: 1, borderColor: Colors.border, marginBottom: Spacing.xl },
  userAvatar: { width: 52, height: 52, borderRadius: 26, backgroundColor: Colors.blueprint + '33', alignItems: 'center', justifyContent: 'center', marginRight: Spacing.md },
  userAvatarText: { ...Typography.h3, color: Colors.blueprint },
  userInfo: { flex: 1 },
  userName: { ...Typography.bodySmall, color: Colors.textPrimary, fontWeight: '700' },
  userEmail: { ...Typography.caption, color: Colors.textMuted, marginTop: 2 },
  roleBadge: { marginTop: 6, alignSelf: 'flex-start', backgroundColor: Colors.blueprint + '22', borderRadius: Radii.full, paddingHorizontal: 8, paddingVertical: 2 },
  roleText: { ...Typography.caption, color: Colors.blueprint, fontWeight: '600' },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.sm, marginBottom: Spacing.xl },
  menuItem: { width: '30%', backgroundColor: Colors.surface, borderRadius: Radii.md, borderWidth: 1, borderColor: Colors.border, padding: Spacing.md, alignItems: 'center', gap: Spacing.sm, flexGrow: 1 },
  menuIcon: { width: 48, height: 48, borderRadius: Radii.md, alignItems: 'center', justifyContent: 'center' },
  menuLabel: { ...Typography.caption, color: Colors.textSecondary, textAlign: 'center' },
  signOutBtn: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm, justifyContent: 'center', padding: Spacing.md, borderRadius: Radii.md, borderWidth: 1, borderColor: Colors.danger + '44', backgroundColor: Colors.danger + '11' },
  signOutText: { ...Typography.bodySmall, color: Colors.danger, fontWeight: '600' },
});
