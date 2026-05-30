import React from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radii, Typography } from '../theme';
import { useAuthStore } from '../store/authStore';

const MENU_ITEMS = [
  { label: 'Tasks', icon: 'checkmark-circle-outline', screen: 'Tasks', color: Colors.success },
  { label: 'Messages', icon: 'chatbubbles-outline', screen: 'Messages', color: Colors.blueprint },
  { label: 'Ravlo AI', icon: 'sparkles-outline', screen: 'RavloAI', color: Colors.softGlow },
  { label: 'Documents', icon: 'document-text-outline', screen: 'Loans', color: Colors.info },
  { label: 'Profile', icon: 'person-outline', screen: 'Profile', color: Colors.steel },
];

export default function MoreScreen({ navigation }: any) {
  const { user, logout } = useAuthStore();
  const first = user?.first_name || '';
  const role = (user?.role || '').replace(/_/g, ' ');

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <View style={styles.profileCard}>
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>
              {(first || user?.email || 'U')[0].toUpperCase()}
            </Text>
          </View>
          <View>
            <Text style={styles.userName}>{user?.full_name || user?.email}</Text>
            <Text style={styles.userRole}>{role}</Text>
          </View>
        </View>

        <View style={styles.grid}>
          {MENU_ITEMS.map(item => (
            <TouchableOpacity key={item.label} style={styles.gridItem}
              onPress={() => navigation.navigate(item.screen)} activeOpacity={0.75}>
              <View style={[styles.iconBox, { backgroundColor: item.color + '22' }]}>
                <Ionicons name={item.icon as any} size={26} color={item.color} />
              </View>
              <Text style={styles.gridLabel}>{item.label}</Text>
            </TouchableOpacity>
          ))}
        </View>

        <TouchableOpacity style={styles.logoutBtn} onPress={logout}>
          <Ionicons name="log-out-outline" size={20} color="#EF4444" />
          <Text style={styles.logoutText}>Sign Out</Text>
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  scroll: { padding: Spacing.lg },
  profileCard: { flexDirection: 'row', alignItems: 'center', gap: Spacing.md, backgroundColor: Colors.surface, borderRadius: Radii.md, borderWidth: 1, borderColor: Colors.border, padding: Spacing.md, marginBottom: Spacing.xl },
  avatar: { width: 52, height: 52, borderRadius: 26, backgroundColor: Colors.blueprint + '33', alignItems: 'center', justifyContent: 'center' },
  avatarText: { fontWeight: '800', fontSize: 22, color: Colors.blueprint },
  userName: { ...Typography.body, color: Colors.textPrimary, fontWeight: '700' },
  userRole: { ...Typography.caption, color: Colors.textMuted, textTransform: 'capitalize' },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.md, marginBottom: Spacing.xl },
  gridItem: { width: '45%', backgroundColor: Colors.surface, borderRadius: Radii.md, borderWidth: 1, borderColor: Colors.border, padding: Spacing.md, alignItems: 'center', gap: Spacing.sm },
  iconBox: { width: 52, height: 52, borderRadius: Radii.md, alignItems: 'center', justifyContent: 'center' },
  gridLabel: { ...Typography.caption, color: Colors.textSecondary, fontWeight: '600' },
  logoutBtn: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm, justifyContent: 'center', padding: Spacing.md, borderRadius: Radii.md, borderWidth: 1, borderColor: '#EF444433', backgroundColor: '#EF444408' },
  logoutText: { ...Typography.body, color: '#EF4444', fontWeight: '600' },
});
