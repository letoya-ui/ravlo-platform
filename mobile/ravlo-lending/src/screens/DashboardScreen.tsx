import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
  TouchableOpacity,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radii, Typography } from '../theme';
import { useAuthStore } from '../store/authStore';
import { api } from '../services/api';

interface PipelineSummary {
  total: number;
  active: number;
  closed: number;
  volume: number;
}

const ROLE_COLORS: Record<string, string> = {
  loan_officer: Colors.blueprint,
  processor: Colors.softGlow,
  underwriter: Colors.info,
  borrower: Colors.success,
  admin: Colors.warning,
};

export default function DashboardScreen({ navigation }: any) {
  const { user } = useAuthStore();
  const [summary, setSummary] = useState<PipelineSummary | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetchSummary = useCallback(async () => {
    try {
      const res = await api.get('/mobile/lending/pipeline/summary');
      setSummary(res.data);
    } catch (err: any) {
      Alert.alert('Error', err.response?.data?.error || 'Could not load pipeline data.');
    }
  }, []);

  useEffect(() => { fetchSummary(); }, [fetchSummary]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchSummary();
    setRefreshing(false);
  }, [fetchSummary]);

  const roleLabel = (user?.role || '').replace('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  const roleColor = ROLE_COLORS[user?.role || ''] || Colors.steel;

  const formatCurrency = (val: number) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', notation: 'compact', maximumFractionDigits: 1 }).format(val);

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView
        contentContainerStyle={styles.scroll}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.blueprint} />}
      >
        <View style={styles.header}>
          <View>
            <Text style={styles.greeting}>Good {getTimeOfDay()},</Text>
            <Text style={styles.userName}>{user?.first_name || 'there'} 👋</Text>
          </View>
          <View style={[styles.roleBadge, { backgroundColor: roleColor + '22', borderColor: roleColor }]}>
            <Text style={[styles.roleText, { color: roleColor }]}>{roleLabel}</Text>
          </View>
        </View>

        <Text style={styles.sectionTitle}>Pipeline Overview</Text>
        <View style={styles.statsGrid}>
          <StatCard label="Total Loans" value={String(summary?.total ?? '—')} icon="layers-outline" color={Colors.info} />
          <StatCard label="Active" value={String(summary?.active ?? '—')} icon="pulse-outline" color={Colors.success} />
          <StatCard label="Closed" value={String(summary?.closed ?? '—')} icon="checkmark-circle-outline" color={Colors.steel} />
          <StatCard label="Volume" value={summary ? formatCurrency(summary.volume) : '—'} icon="cash-outline" color={Colors.warning} />
        </View>

        <Text style={styles.sectionTitle}>Quick Actions</Text>
        <View style={styles.actionsGrid}>
          <QuickAction label="View Loans" icon="documents-outline" onPress={() => navigation.navigate('Loans')} />
          <QuickAction label="Ask Elena" icon="sparkles-outline" onPress={() => navigation.navigate('Elena')} />
          <QuickAction label="My Profile" icon="person-outline" onPress={() => navigation.navigate('Profile')} />
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

function StatCard({ label, value, icon, color }: { label: string; value: string; icon: any; color: string }) {
  return (
    <View style={styles.statCard}>
      <View style={[styles.statIcon, { backgroundColor: color + '22' }]}>
        <Ionicons name={icon} size={22} color={color} />
      </View>
      <Text style={styles.statValue}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

function QuickAction({ label, icon, onPress }: { label: string; icon: any; onPress: () => void }) {
  return (
    <TouchableOpacity style={styles.actionCard} onPress={onPress} activeOpacity={0.75}>
      <Ionicons name={icon} size={26} color={Colors.blueprint} />
      <Text style={styles.actionLabel}>{label}</Text>
    </TouchableOpacity>
  );
}

function getTimeOfDay() {
  const h = new Date().getHours();
  if (h < 12) return 'morning';
  if (h < 17) return 'afternoon';
  return 'evening';
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  scroll: { padding: Spacing.lg },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: Spacing.xl },
  greeting: { ...Typography.bodySmall, color: Colors.textMuted },
  userName: { ...Typography.h2, color: Colors.textPrimary, marginTop: 2 },
  roleBadge: { borderWidth: 1, borderRadius: Radii.full, paddingHorizontal: Spacing.sm, paddingVertical: 4 },
  roleText: { ...Typography.caption, fontWeight: '600' },
  sectionTitle: { ...Typography.label, color: Colors.textMuted, marginBottom: Spacing.md, marginTop: Spacing.sm },
  statsGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.sm, marginBottom: Spacing.lg },
  statCard: {
    flex: 1,
    minWidth: '45%',
    backgroundColor: Colors.surface,
    borderRadius: Radii.md,
    padding: Spacing.md,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  statIcon: { width: 40, height: 40, borderRadius: Radii.sm, alignItems: 'center', justifyContent: 'center', marginBottom: Spacing.sm },
  statValue: { ...Typography.h3, color: Colors.textPrimary },
  statLabel: { ...Typography.caption, color: Colors.textMuted, marginTop: 2 },
  actionsGrid: { flexDirection: 'row', gap: Spacing.sm },
  actionCard: {
    flex: 1,
    backgroundColor: Colors.surface,
    borderRadius: Radii.md,
    padding: Spacing.md,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: Colors.border,
    gap: Spacing.xs,
  },
  actionLabel: { ...Typography.caption, color: Colors.textSecondary, textAlign: 'center' },
});
