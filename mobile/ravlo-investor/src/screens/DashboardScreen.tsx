import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
  Alert,
  FlatList,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radii, Typography } from '../theme';
import { useAuthStore } from '../store/authStore';
import { api } from '../services/api';

interface InvestorStats {
  total_invested: number;
  active_deals: number;
  total_deals: number;
  avg_return: number;
}

interface Deal {
  id: number;
  name: string;
  amount: number;
  return_rate: number;
  status: string;
  asset_class: string;
}

const STATUS_COLORS: Record<string, string> = {
  active: Colors.success,
  open: Colors.info,
  funded: Colors.success,
  closed: Colors.steel,
  pending: Colors.warning,
};

export default function DashboardScreen({ navigation }: any) {
  const { user } = useAuthStore();
  const [stats, setStats] = useState<InvestorStats | null>(null);
  const [recentDeals, setRecentDeals] = useState<Deal[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [statsRes, dealsRes] = await Promise.all([
        api.get('/mobile/investor/dashboard'),
        api.get('/mobile/investor/deals'),
      ]);
      setStats(statsRes.data);
      setRecentDeals((dealsRes.data.deals || []).slice(0, 5));
    } catch (err: any) {
      Alert.alert('Error', err.response?.data?.error || 'Could not load dashboard.');
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchData();
    setRefreshing(false);
  }, [fetchData]);

  const formatCurrency = (val: number) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', notation: 'compact', maximumFractionDigits: 1 }).format(val);

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView
        contentContainerStyle={styles.scroll}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.blueprint} />}
      >
        <View style={styles.header}>
          <Text style={styles.greeting}>Welcome back,</Text>
          <Text style={styles.userName}>{user?.first_name || 'Investor'}</Text>
        </View>

        <Text style={styles.sectionTitle}>Portfolio Overview</Text>
        <View style={styles.statsGrid}>
          <StatCard
            label="Total Invested"
            value={stats ? formatCurrency(stats.total_invested) : '—'}
            icon="cash-outline"
            color={Colors.success}
          />
          <StatCard
            label="Active Deals"
            value={stats ? String(stats.active_deals) : '—'}
            icon="pulse-outline"
            color={Colors.info}
          />
          <StatCard
            label="Total Deals"
            value={stats ? String(stats.total_deals) : '—'}
            icon="layers-outline"
            color={Colors.blueprint}
          />
          <StatCard
            label="Avg Return"
            value={stats ? `${stats.avg_return.toFixed(2)}%` : '—'}
            icon="trending-up-outline"
            color={Colors.warning}
          />
        </View>

        <Text style={styles.sectionTitle}>Recent Deals</Text>
        {recentDeals.length === 0 ? (
          <View style={styles.emptyContainer}>
            <Ionicons name="trending-up-outline" size={40} color={Colors.textMuted} />
            <Text style={styles.emptyText}>No deals yet</Text>
          </View>
        ) : (
          recentDeals.map((deal) => (
            <View key={deal.id} style={styles.dealCard}>
              <View style={styles.dealHeader}>
                <Text style={styles.dealName} numberOfLines={1}>{deal.name || 'Unnamed Deal'}</Text>
                <View style={[styles.statusBadge, { backgroundColor: (STATUS_COLORS[deal.status] || Colors.steel) + '22' }]}>
                  <Text style={[styles.statusText, { color: STATUS_COLORS[deal.status] || Colors.steel }]}>
                    {deal.status}
                  </Text>
                </View>
              </View>
              <View style={styles.dealMeta}>
                <Text style={styles.dealAmount}>{formatCurrency(deal.amount)}</Text>
                <Text style={styles.dealReturn}>{deal.return_rate.toFixed(2)}% return</Text>
              </View>
              {deal.asset_class ? <Text style={styles.dealClass}>{deal.asset_class}</Text> : null}
            </View>
          ))
        )}
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

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  scroll: { padding: Spacing.lg },
  header: { marginBottom: Spacing.xl },
  greeting: { ...Typography.bodySmall, color: Colors.textMuted },
  userName: { ...Typography.h2, color: Colors.textPrimary, marginTop: 2 },
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
  emptyContainer: { alignItems: 'center', paddingVertical: Spacing.xl, gap: Spacing.md },
  emptyText: { ...Typography.body, color: Colors.textMuted },
  dealCard: {
    backgroundColor: Colors.surface,
    borderRadius: Radii.md,
    padding: Spacing.md,
    marginBottom: Spacing.sm,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  dealHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: Spacing.xs },
  dealName: { ...Typography.body, color: Colors.textPrimary, fontWeight: '600', flex: 1 },
  statusBadge: { borderRadius: Radii.full, paddingHorizontal: Spacing.sm, paddingVertical: 2 },
  statusText: { ...Typography.caption, fontWeight: '700', textTransform: 'uppercase' },
  dealMeta: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 },
  dealAmount: { ...Typography.body, color: Colors.blueprint, fontWeight: '700' },
  dealReturn: { ...Typography.bodySmall, color: Colors.success },
  dealClass: { ...Typography.caption, color: Colors.textMuted },
});
