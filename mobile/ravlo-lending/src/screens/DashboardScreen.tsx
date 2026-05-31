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

interface LODashboard {
  leads: { total: number; new: number; active: number; contacted: number; pending: number; closed: number };
  tasks: { due_today: number; overdue: number; total_open: number };
  messages: { unread: number };
  pipeline: { total: number; active: number; volume: number };
}

const ROLE_COLORS: Record<string, string> = {
  loan_officer: Colors.blueprint,
  processor: Colors.softGlow,
  underwriter: Colors.info,
  borrower: Colors.success,
  admin: Colors.warning,
};

export default function DashboardScreen({ navigation }: any) {
  const { user, token } = useAuthStore();
  const [data, setData] = useState<LODashboard | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const res = await api.get('/mobile/lending/dashboard', {
        headers: { Authorization: `Bearer ${token}` },
      });
      setData(res.data);
    } catch {
      // fall through to show dashes
    }
  }, [token]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchData();
    setRefreshing(false);
  }, [fetchData]);

  const roleLabel = (user?.role || '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  const roleColor = ROLE_COLORS[user?.role || ''] || Colors.steel;

  const fmt = (val: number) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', notation: 'compact', maximumFractionDigits: 1 }).format(val);

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView
        contentContainerStyle={styles.scroll}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.blueprint} />}
      >
        {/* Header */}
        <View style={styles.header}>
          <View>
            <Text style={styles.greeting}>Good {getTimeOfDay()},</Text>
            <Text style={styles.userName}>{user?.first_name || 'there'}</Text>
          </View>
          <View style={[styles.roleBadge, { backgroundColor: roleColor + '22', borderColor: roleColor }]}>
            <Text style={[styles.roleText, { color: roleColor }]}>{roleLabel}</Text>
          </View>
        </View>

        {/* Alerts row */}
        {((data?.tasks?.overdue ?? 0) > 0 || (data?.messages?.unread ?? 0) > 0) && (
          <View style={styles.alertRow}>
            {(data?.tasks?.overdue ?? 0) > 0 && (
              <View style={styles.alertChip}>
                <Ionicons name="alert-circle" size={13} color={Colors.danger} />
                <Text style={styles.alertText}>{data!.tasks.overdue} overdue</Text>
              </View>
            )}
            {(data?.messages?.unread ?? 0) > 0 && (
              <View style={[styles.alertChip, { borderColor: Colors.info + '66', backgroundColor: Colors.info + '11' }]}>
                <Ionicons name="chatbubble" size={13} color={Colors.info} />
                <Text style={[styles.alertText, { color: Colors.info }]}>{data!.messages.unread} unread</Text>
              </View>
            )}
          </View>
        )}

        {/* Leads */}
        <Text style={styles.sectionTitle}>Leads</Text>
        <View style={styles.statsGrid}>
          <StatCard label="Total" value={String(data?.leads?.total ?? '—')} icon="people-outline" color={Colors.blueprint} />
          <StatCard label="New" value={String(data?.leads?.new ?? '—')} icon="add-circle-outline" color={Colors.info} />
          <StatCard label="Active" value={String(data?.leads?.active ?? '—')} icon="pulse-outline" color={Colors.success} />
          <StatCard label="Pending" value={String(data?.leads?.pending ?? '—')} icon="time-outline" color={Colors.warning} />
        </View>

        {/* Tasks & Pipeline */}
        <Text style={styles.sectionTitle}>Today</Text>
        <View style={styles.statsGrid}>
          <StatCard label="Due Today" value={String(data?.tasks?.due_today ?? '—')} icon="today-outline" color={Colors.warning} />
          <StatCard label="Overdue" value={String(data?.tasks?.overdue ?? '—')} icon="alert-circle-outline" color={Colors.danger} />
          <StatCard label="Active Loans" value={String(data?.pipeline?.active ?? '—')} icon="layers-outline" color={Colors.softGlow} />
          <StatCard label="Volume" value={data?.pipeline?.volume ? fmt(data.pipeline.volume) : '—'} icon="cash-outline" color={Colors.success} />
        </View>

        {/* Quick Actions */}
        <Text style={styles.sectionTitle}>Quick Actions</Text>
        <View style={styles.actionsGrid}>
          <QuickAction label="Leads" icon="people-outline" onPress={() => navigation.navigate('Leads')} />
          <QuickAction label="Tasks" icon="checkmark-circle-outline" onPress={() => navigation.navigate('Tasks')} />
          <QuickAction label="Messages" icon="chatbubbles-outline" onPress={() => navigation.navigate('Messages')} badge={data?.messages?.unread} />
          <QuickAction label="Pipeline" icon="layers-outline" onPress={() => navigation.navigate('Pipeline')} />
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

function QuickAction({ label, icon, onPress, badge }: { label: string; icon: any; onPress: () => void; badge?: number }) {
  return (
    <TouchableOpacity style={styles.actionCard} onPress={onPress} activeOpacity={0.75}>
      <View style={{ position: 'relative' }}>
        <Ionicons name={icon} size={24} color={Colors.blueprint} />
        {badge && badge > 0 ? (
          <View style={styles.actionBadge}>
            <Text style={styles.actionBadgeText}>{badge > 9 ? '9+' : badge}</Text>
          </View>
        ) : null}
      </View>
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
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: Spacing.md },
  greeting: { ...Typography.bodySmall, color: Colors.textMuted },
  userName: { ...Typography.h2, color: Colors.textPrimary, marginTop: 2 },
  roleBadge: { borderWidth: 1, borderRadius: Radii.full, paddingHorizontal: Spacing.sm, paddingVertical: 4 },
  roleText: { ...Typography.caption, fontWeight: '600' },
  alertRow: { flexDirection: 'row', gap: Spacing.sm, marginBottom: Spacing.md },
  alertChip: { flexDirection: 'row', alignItems: 'center', gap: 5, borderWidth: 1, borderColor: Colors.danger + '66', backgroundColor: Colors.danger + '11', borderRadius: Radii.full, paddingHorizontal: Spacing.sm, paddingVertical: 4 },
  alertText: { fontSize: 11, fontWeight: '600', color: Colors.danger },
  sectionTitle: { ...Typography.label, color: Colors.textMuted, marginBottom: Spacing.md, marginTop: Spacing.xs },
  statsGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.sm, marginBottom: Spacing.lg },
  statCard: { flex: 1, minWidth: '45%', backgroundColor: Colors.surface, borderRadius: Radii.md, padding: Spacing.md, borderWidth: 1, borderColor: Colors.border },
  statIcon: { width: 36, height: 36, borderRadius: Radii.sm, alignItems: 'center', justifyContent: 'center', marginBottom: Spacing.sm },
  statValue: { ...Typography.h3, color: Colors.textPrimary },
  statLabel: { ...Typography.caption, color: Colors.textMuted, marginTop: 2 },
  actionsGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.sm },
  actionCard: { flex: 1, minWidth: '22%', backgroundColor: Colors.surface, borderRadius: Radii.md, padding: Spacing.md, alignItems: 'center', borderWidth: 1, borderColor: Colors.border, gap: Spacing.xs },
  actionLabel: { ...Typography.caption, color: Colors.textSecondary, textAlign: 'center' },
  actionBadge: { position: 'absolute', top: -4, right: -6, width: 16, height: 16, borderRadius: 8, backgroundColor: Colors.danger, alignItems: 'center', justifyContent: 'center' },
  actionBadgeText: { fontSize: 9, fontWeight: '700', color: Colors.white },
});
