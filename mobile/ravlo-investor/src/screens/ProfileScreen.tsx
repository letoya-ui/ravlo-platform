import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radii, Typography } from '../theme';
import { useAuthStore } from '../store/authStore';

export default function ProfileScreen() {
  const { user, logout } = useAuthStore();

  const handleLogout = () => {
    Alert.alert(
      'Sign Out',
      'Are you sure you want to sign out?',
      [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Sign Out', style: 'destructive', onPress: logout },
      ]
    );
  };

  const initials = [
    user?.first_name?.[0] || '',
    user?.last_name?.[0] || '',
  ].join('').toUpperCase() || '?';

  const roleLabel = (user?.role || '').replace('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase());

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <Text style={styles.pageTitle}>Profile</Text>
        <View style={styles.avatarSection}>
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>{initials}</Text>
          </View>
          <Text style={styles.fullName}>{user?.full_name || '—'}</Text>
          <Text style={styles.roleLabel}>{roleLabel}</Text>
        </View>
        <View style={styles.infoCard}>
          <InfoRow icon="mail-outline" label="Email" value={user?.email || '—'} />
          <InfoRow icon="shield-outline" label="Role" value={roleLabel} />
          <InfoRow icon="star-outline" label="Subscription" value={user?.subscription || 'Free'} />
          <InfoRow
            icon="checkmark-circle-outline"
            label="Onboarding"
            value={user?.onboarding_complete ? 'Complete' : 'Incomplete'}
          />
        </View>
        <TouchableOpacity style={styles.logoutBtn} onPress={handleLogout} activeOpacity={0.8}>
          <Ionicons name="log-out-outline" size={20} color={Colors.danger} />
          <Text style={styles.logoutText}>Sign Out</Text>
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
}

function InfoRow({ icon, label, value }: { icon: any; label: string; value: string }) {
  return (
    <View style={styles.infoRow}>
      <View style={styles.infoIcon}>
        <Ionicons name={icon} size={18} color={Colors.blueprint} />
      </View>
      <View style={styles.infoContent}>
        <Text style={styles.infoLabel}>{label}</Text>
        <Text style={styles.infoValue}>{value}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  scroll: { padding: Spacing.lg },
  pageTitle: { ...Typography.h2, color: Colors.textPrimary, marginBottom: Spacing.lg },
  avatarSection: { alignItems: 'center', marginBottom: Spacing.xl },
  avatar: {
    width: 80,
    height: 80,
    borderRadius: Radii.full,
    backgroundColor: Colors.blueprint,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: Spacing.md,
  },
  avatarText: { fontSize: 30, fontWeight: '700', color: Colors.white },
  fullName: { ...Typography.h3, color: Colors.textPrimary },
  roleLabel: { ...Typography.bodySmall, color: Colors.textMuted, marginTop: 4 },
  infoCard: {
    backgroundColor: Colors.surface,
    borderRadius: Radii.md,
    borderWidth: 1,
    borderColor: Colors.border,
    marginBottom: Spacing.lg,
    overflow: 'hidden',
  },
  infoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: Spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: Colors.border,
  },
  infoIcon: { width: 36, alignItems: 'center' },
  infoContent: { flex: 1 },
  infoLabel: { ...Typography.caption, color: Colors.textMuted },
  infoValue: { ...Typography.body, color: Colors.textPrimary },
  logoutBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.sm,
    backgroundColor: Colors.danger + '15',
    borderWidth: 1,
    borderColor: Colors.danger + '40',
    borderRadius: Radii.md,
    paddingVertical: Spacing.md,
  },
  logoutText: { ...Typography.label, color: Colors.danger, fontSize: 16 },
});
