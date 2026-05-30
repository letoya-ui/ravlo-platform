import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
  TouchableOpacity,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radii, Typography } from '../../theme';
import { useAuthStore } from '../../store/authStore';
import { api } from '../../services/api';

interface Overview {
  users: {
    total: number;
    active: number;
    blocked: number;
    recent_signups: number;
    subscriptions: Record<string, number>;
    roles: Record<string, number>;
  };
  loans: { total: number; active: number; volume: number };
  companies: number;
  documents: number;
  access_requests: { pending: number; approved: number; total: number };
  pending_invites: number;
}

export default function AdminDashboardScreen({ navigation }: any) {
  const { user } = useAuthStore();
  const [data, setData] = useState<Overview | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const res = await api.get('/mobile/admin/overview');
      setData(res.data);
    } catch (err: any) {
      console.error('admin overview error', err?.response?.data);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchData();
    setRefreshing(false);
  }, [fetchData]);

  const fmt = (n: number) =>
    new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      notation: 'compact',
      maximumFractionDigits: 1,
    }).format(n);

  const subEntries = Object.entries(data?.users.subscriptions || {}).sort((a, b) => b[1] - a[1]);
  const roleEntries = Object.entries(data?.users.roles || {}).sort((a, b) => b[1] - a[1]);

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView
        contentContainerStyle={styles.scroll}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.blueprint} />
        }
      >
        {/* Header */}
        <View style={styles.header}>
          <View>
            <Text style={styles.eyebrow}>Owner View</Text>
            <Text style={styles.title}>Executive Dashboard</Text>
          </View>
          <View style={styles.adminBadge}>
            <Ionicons name="shield-checkmark-outline" size={14} color={Colors.blueprint} />
            <Text style={styles.adminBadgeText}>{(user?.role || '').replace('_', ' ')}</Text>
          </View>
        </View>

        {/* Core KPIs */}
        <Text style={styles.sectionTitle}>Platform Overview</Text>
        <View style={styles.grid}>
          <StatCard
            label="Total Users"
            value={String(data?.users.total ?? '—')}
            icon="people-outline"
            color={Colors.blueprint}
          />
          <StatCard
            label="New (30d)"
            value={String(data?.users.recent_signups ?? '—')}
            icon="person-add-outline"
            color={Colors.success}
          />
          <StatCard
            label="Active Loans"
            value={String(data?.loans.active ?? '—')}
            icon="pulse-outline"
            color={Colors.info}
          />
          <StatCard
            label="Loan Volume"
            value={data ? fmt(data.loans.volume) : '—'}
            icon="cash-outline"
            color={Colors.warning}
          />
          <StatCard
            label="Companies"
            value={String(data?.companies ?? '—')}
            icon="business-outline"
            color={Colors.softGlow}
          />
          <StatCard
            label="Documents"
            value={String(data?.documents ?? '—')}
            icon="document-text-outline"
            color={Colors.steel}
          />
        </View>

        {/* Alerts row */}
        <View style={styles.alertsRow}>
          <AlertChip
            label="Pending Requests"
            count={data?.access_requests.pending ?? 0}
            icon="time-outline"
            color={Colors.warning}
          />
          <AlertChip
            label="Pending Invites"
            count={data?.pending_invites ?? 0}
            icon="mail-outline"
            color={Colors.info}
          />
          <AlertChip
            label="Blocked Users"
            count={data?.users.blocked ?? 0}
            icon="ban-outline"
            color={Colors.error ?? '#EF4444'}
          />
        </View>

        {/* Subscription breakdown */}
        {subEntries.length > 0 && (
          <>
            <Text style={styles.sectionTitle}>Subscriptions</Text>
            <View style={styles.card}>
              {subEntries.map(([tier, count]) => (
                <BreakdownRow
                  key={tier}
                  label={tier.replace('_', ' ')}
                  count={count}
                  total={data?.users.total || 1}
                  color={SUB_COLORS[tier] || Colors.steel}
                />
              ))}
            </View>
          </>
        )}

        {/* Role breakdown */}
        {roleEntries.length > 0 && (
          <>
            <Text style={styles.sectionTitle}>Users by Role</Text>
            <View style={styles.card}>
              {roleEntries.map(([role, count]) => (
                <BreakdownRow
                  key={role}
                  label={role.replace(/_/g, ' ')}
                  count={count}
                  total={data?.users.total || 1}
                  color={ROLE_COLORS[role] || Colors.steel}
                />
              ))}
            </View>
          </>
        )}

        {/* Quick nav */}
        <Text style={styles.sectionTitle}>Quick Access</Text>
        <View style={styles.quickRow}>
          <QuickBtn
            label="All Users"
            icon="people-outline"
            onPress={() => navigation.navigate('AdminUsers')}
          />
          <QuickBtn
            label="Activity"
            icon="activity-outline"
            iconName="bar-chart-outline"
            onPress={() => navigation.navigate('AdminActivity')}
          />
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

function StatCard({ label, value, icon, color }: { label: string; value: string; icon: any; color: string }) {
  return (
    <View style={styles.statCard}>
      <View style={[styles.statIcon, { backgroundColor: color + '22' }]}>
        <Ionicons name={icon} size={20} color={color} />
      </View>
      <Text style={styles.statValue}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

function AlertChip({ label, count, icon, color }: { label: string; count: number; icon: any; color: string }) {
  return (
    <View style={[styles.alertChip, { borderColor: count > 0 ? color : Colors.border }]}>
      <Ionicons name={icon} size={14} color={count > 0 ? color : Colors.textMuted} />
      <Text style={[styles.alertCount, { color: count > 0 ? color : Colors.textMuted }]}>{count}</Text>
      <Text style={styles.alertLabel}>{label}</Text>
    </View>
  );
}

function BreakdownRow({ label, count, total, color }: { label: string; count: number; total: number; color: string }) {
  const pct = Math.round((count / total) * 100);
  return (
    <View style={styles.breakdownRow}>
      <View style={styles.breakdownLeft}>
        <View style={[styles.dot, { backgroundColor: color }]} />
        <Text style={styles.breakdownLabel}>{label}</Text>
      </View>
      <View style={styles.breakdownRight}>
        <View style={styles.barTrack}>
          <View style={[styles.barFill, { width: `${pct}%` as any, backgroundColor: color }]} />
        </View>
        <Text style={styles.breakdownCount}>{count}</Text>
      </View>
    </View>
  );
}

function QuickBtn({ label, icon, iconName, onPress }: { label: string; icon?: any; iconName?: any; onPress: () => void }) {
  return (
    <TouchableOpacity style={styles.quickBtn} onPress={onPress} activeOpacity={0.75}>
      <Ionicons name={iconName || icon} size={24} color={Colors.blueprint} />
      <Text style={styles.quickBtnLabel}>{label}</Text>
    </TouchableOpacity>
  );
}

const SUB_COLORS: Record<string, string> = {
  enterprise: Colors.blueprint,
  professional: Colors.info,
  starter: Colors.success,
  free: Colors.steel,
  loan_officer: Colors.softGlow,
  basic: Colors.warning,
};

const ROLE_COLORS: Record<string, string> = {
  loan_officer: Colors.blueprint,
  processor: Colors.softGlow,
  underwriter: Colors.info,
  borrower: Colors.success,
  admin: Colors.warning,
  executive: Colors.blueprint,
  platform_admin: Colors.blueprint,
  master_admin: Colors.blueprint,
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  scroll: { padding: Spacing.lg, paddingBottom: Spacing.xl * 2 },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: Spacing.xl,
  },
  eyebrow: { ...Typography.caption, color: Colors.textMuted },
  title: { ...Typography.h2, color: Colors.textPrimary, marginTop: 2 },
  adminBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: Colors.blueprint + '22',
    borderWidth: 1,
    borderColor: Colors.blueprint,
    borderRadius: Radii.full,
    paddingHorizontal: Spacing.sm,
    paddingVertical: 4,
  },
  adminBadgeText: { ...Typography.caption, color: Colors.blueprint, fontWeight: '600', textTransform: 'capitalize' },
  sectionTitle: { ...Typography.label, color: Colors.textMuted, marginBottom: Spacing.sm, marginTop: Spacing.md },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.sm, marginBottom: Spacing.sm },
  statCard: {
    flex: 1,
    minWidth: '45%',
    backgroundColor: Colors.surface,
    borderRadius: Radii.md,
    padding: Spacing.md,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  statIcon: {
    width: 36,
    height: 36,
    borderRadius: Radii.sm,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: Spacing.xs,
  },
  statValue: { ...Typography.h3, color: Colors.textPrimary },
  statLabel: { ...Typography.caption, color: Colors.textMuted, marginTop: 2 },
  alertsRow: { flexDirection: 'row', gap: Spacing.sm, marginBottom: Spacing.sm },
  alertChip: {
    flex: 1,
    flexDirection: 'column',
    alignItems: 'center',
    backgroundColor: Colors.surface,
    borderRadius: Radii.md,
    padding: Spacing.sm,
    borderWidth: 1,
    gap: 2,
  },
  alertCount: { ...Typography.h3, fontWeight: '700' },
  alertLabel: { ...Typography.caption, color: Colors.textMuted, textAlign: 'center', fontSize: 10 },
  card: {
    backgroundColor: Colors.surface,
    borderRadius: Radii.md,
    borderWidth: 1,
    borderColor: Colors.border,
    padding: Spacing.md,
    gap: Spacing.sm,
    marginBottom: Spacing.sm,
  },
  breakdownRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  breakdownLeft: { flexDirection: 'row', alignItems: 'center', gap: Spacing.xs, flex: 1 },
  dot: { width: 8, height: 8, borderRadius: 4 },
  breakdownLabel: { ...Typography.bodySmall, color: Colors.textSecondary, textTransform: 'capitalize' },
  breakdownRight: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm, flex: 1.5 },
  barTrack: { flex: 1, height: 6, backgroundColor: Colors.border, borderRadius: 3, overflow: 'hidden' },
  barFill: { height: 6, borderRadius: 3 },
  breakdownCount: { ...Typography.caption, color: Colors.textMuted, width: 28, textAlign: 'right' },
  quickRow: { flexDirection: 'row', gap: Spacing.sm },
  quickBtn: {
    flex: 1,
    backgroundColor: Colors.surface,
    borderRadius: Radii.md,
    padding: Spacing.md,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: Colors.border,
    gap: Spacing.xs,
  },
  quickBtnLabel: { ...Typography.caption, color: Colors.textSecondary },
});
