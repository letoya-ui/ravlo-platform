import React, { useEffect, useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, RefreshControl,
  TouchableOpacity, ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radii, Typography } from '../theme';
import { api } from '../services/api';

const STRATEGY_COLORS: Record<string, string> = {
  fix_and_flip: Colors.warning,
  flip: Colors.warning,
  brrrr: Colors.blueprint,
  buy_and_hold: Colors.success,
  rental: Colors.success,
  wholesale: Colors.info,
  note: Colors.softGlow,
  new_construction: Colors.softGlow,
};

const STATUS_COLORS: Record<string, string> = {
  pipeline: Colors.info,
  active: Colors.success,
  closed: Colors.steel,
  dead: Colors.danger,
};

interface Investment {
  id: number;
  title: string;
  strategy: string;
  address: string;
  city: string;
  state: string;
  status: string;
  stage: string;
  purchase_price: number;
  rehab_budget: number;
  arv: number;
  monthly_rent: number;
  loan_amount: number;
  projected_profit: number;
  projected_roi: number;
  notes: string;
  created_at: string;
}

interface PortfolioStats {
  total: number;
  total_invested: number;
  total_arv: number;
  total_profit: number;
  by_status: Record<string, number>;
  by_strategy: Record<string, number>;
}

const STATUS_FILTERS = ['All', 'pipeline', 'active', 'closed'];

export default function PortfolioScreen() {
  const [investments, setInvestments] = useState<Investment[]>([]);
  const [stats, setStats] = useState<PortfolioStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter] = useState('All');

  const fetch = useCallback(async () => {
    try {
      const res = await api.get('/mobile/investor/portfolio');
      setInvestments(res.data.investments || []);
      setStats(res.data.stats || null);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetch();
    setRefreshing(false);
  }, [fetch]);

  const fmt = (v: number) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', notation: 'compact', maximumFractionDigits: 1 }).format(v);

  const stratLabel = (s: string) => (s || '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

  const filtered = filter === 'All' ? investments : investments.filter(i => i.status === filter);

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <ActivityIndicator color={Colors.blueprint} style={{ flex: 1 }} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Portfolio</Text>
        <Text style={styles.subtitle}>{stats?.total ?? 0} investments</Text>
      </View>

      <ScrollView
        contentContainerStyle={styles.scroll}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.blueprint} />}
        showsVerticalScrollIndicator={false}
      >
        {/* Stats */}
        {stats && (
          <>
            <View style={styles.statsGrid}>
              <StatCard label="Total Invested" value={fmt(stats.total_invested)} color={Colors.blueprint} icon="layers-outline" />
              <StatCard label="Total ARV" value={fmt(stats.total_arv)} color={Colors.success} icon="trending-up-outline" />
              <StatCard label="Projected Profit" value={fmt(stats.total_profit)} color={stats.total_profit >= 0 ? Colors.success : Colors.danger} icon="cash-outline" />
              <StatCard label="Investments" value={String(stats.total)} color={Colors.info} icon="briefcase-outline" />
            </View>

            {Object.keys(stats.by_status).length > 0 && (
              <>
                <Text style={styles.sectionTitle}>By Status</Text>
                <View style={styles.breakdownRow}>
                  {Object.entries(stats.by_status).map(([s, count]) => {
                    const color = STATUS_COLORS[s] || Colors.steel;
                    return (
                      <View key={s} style={[styles.breakdownChip, { backgroundColor: color + '18', borderColor: color + '44' }]}>
                        <Text style={[styles.breakdownCount, { color }]}>{count}</Text>
                        <Text style={[styles.breakdownLabel, { color }]}>{s.charAt(0).toUpperCase() + s.slice(1)}</Text>
                      </View>
                    );
                  })}
                </View>
              </>
            )}

            {Object.keys(stats.by_strategy).length > 0 && (
              <>
                <Text style={styles.sectionTitle}>By Strategy</Text>
                <View style={styles.breakdownRow}>
                  {Object.entries(stats.by_strategy).map(([s, count]) => {
                    const color = STRATEGY_COLORS[s] || Colors.steel;
                    return (
                      <View key={s} style={[styles.breakdownChip, { backgroundColor: color + '18', borderColor: color + '44' }]}>
                        <Text style={[styles.breakdownCount, { color }]}>{count}</Text>
                        <Text style={[styles.breakdownLabel, { color }]}>{stratLabel(s)}</Text>
                      </View>
                    );
                  })}
                </View>
              </>
            )}
          </>
        )}

        {/* Filter chips */}
        <View style={styles.filterRow}>
          {STATUS_FILTERS.map(f => (
            <TouchableOpacity
              key={f}
              style={[styles.chip, filter === f && styles.chipActive]}
              onPress={() => setFilter(f)}
            >
              <Text style={[styles.chipText, filter === f && styles.chipTextActive]}>
                {f === 'All' ? 'All' : f.charAt(0).toUpperCase() + f.slice(1)}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Investments list */}
        {filtered.length === 0 ? (
          <View style={styles.empty}>
            <Ionicons name="briefcase-outline" size={48} color={Colors.textMuted} />
            <Text style={styles.emptyText}>
              {investments.length === 0 ? 'No investments tracked yet' : 'No investments match filter'}
            </Text>
          </View>
        ) : (
          filtered.map(inv => {
            const stratColor = STRATEGY_COLORS[inv.strategy] || Colors.blueprint;
            const statusColor = STATUS_COLORS[inv.status] || Colors.steel;
            const allIn = inv.purchase_price + inv.rehab_budget;
            const location = [inv.city, inv.state].filter(Boolean).join(', ');
            return (
              <View key={inv.id} style={styles.card}>
                <View style={styles.cardTop}>
                  <View style={[styles.cardIcon, { backgroundColor: stratColor + '22' }]}>
                    <Ionicons name="home-outline" size={18} color={stratColor} />
                  </View>
                  <View style={styles.cardInfo}>
                    <Text style={styles.cardTitle} numberOfLines={1}>{inv.title}</Text>
                    {location ? <Text style={styles.cardLocation}>{location}</Text> : null}
                    <View style={styles.badgeRow}>
                      {inv.strategy ? (
                        <View style={[styles.badge, { backgroundColor: stratColor + '22', borderColor: stratColor + '55' }]}>
                          <Text style={[styles.badgeText, { color: stratColor }]}>{stratLabel(inv.strategy)}</Text>
                        </View>
                      ) : null}
                      <View style={[styles.badge, { backgroundColor: statusColor + '22', borderColor: statusColor + '55' }]}>
                        <Text style={[styles.badgeText, { color: statusColor }]}>{inv.status}</Text>
                      </View>
                      {inv.stage ? (
                        <View style={[styles.badge, { backgroundColor: Colors.border }]}>
                          <Text style={[styles.badgeText, { color: Colors.textMuted }]}>{inv.stage}</Text>
                        </View>
                      ) : null}
                    </View>
                  </View>
                  {inv.projected_roi !== 0 && (
                    <Text style={[styles.roiText, { color: inv.projected_roi >= 0 ? Colors.success : Colors.danger }]}>
                      {inv.projected_roi >= 0 ? '+' : ''}{inv.projected_roi.toFixed(1)}%
                    </Text>
                  )}
                </View>
                <View style={styles.metricsRow}>
                  <MiniMetric label="Purchase" value={fmt(inv.purchase_price)} />
                  <MiniMetric label="All-In" value={fmt(allIn)} />
                  {inv.arv > 0 && <MiniMetric label="ARV" value={fmt(inv.arv)} />}
                  {inv.projected_profit !== 0 && (
                    <MiniMetric
                      label="Profit"
                      value={fmt(inv.projected_profit)}
                      color={inv.projected_profit >= 0 ? Colors.success : Colors.danger}
                    />
                  )}
                </View>
              </View>
            );
          })
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

function StatCard({ label, value, color, icon }: { label: string; value: string; color: string; icon: any }) {
  return (
    <View style={[styles.statCard, { borderColor: color + '33' }]}>
      <View style={[styles.statIcon, { backgroundColor: color + '18' }]}>
        <Ionicons name={icon} size={16} color={color} />
      </View>
      <Text style={[styles.statValue, { color }]}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

function MiniMetric({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <View style={styles.miniMetric}>
      <Text style={styles.miniLabel}>{label}</Text>
      <Text style={[styles.miniValue, color ? { color } : {}]}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  header: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingHorizontal: Spacing.lg, paddingTop: Spacing.md, paddingBottom: Spacing.sm,
  },
  title: { ...Typography.h2, color: Colors.textPrimary },
  subtitle: { ...Typography.bodySmall, color: Colors.textMuted },
  scroll: { padding: Spacing.lg, paddingTop: Spacing.sm, paddingBottom: Spacing.xxl },
  statsGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.sm, marginBottom: Spacing.lg },
  statCard: { flex: 1, minWidth: '45%', backgroundColor: Colors.surface, borderRadius: Radii.md, padding: Spacing.md, borderWidth: 1 },
  statIcon: { width: 30, height: 30, borderRadius: Radii.sm, alignItems: 'center', justifyContent: 'center', marginBottom: Spacing.sm },
  statValue: { fontSize: 16, fontWeight: '800', marginBottom: 2 },
  statLabel: { ...Typography.caption, color: Colors.textMuted },
  sectionTitle: { ...Typography.label, color: Colors.textMuted, marginBottom: Spacing.sm, marginTop: Spacing.xs },
  breakdownRow: { flexDirection: 'row', gap: Spacing.sm, flexWrap: 'wrap', marginBottom: Spacing.md },
  breakdownChip: { borderRadius: Radii.md, borderWidth: 1, paddingHorizontal: Spacing.md, paddingVertical: Spacing.sm, alignItems: 'center', minWidth: 70 },
  breakdownCount: { fontSize: 20, fontWeight: '800' },
  breakdownLabel: { fontSize: 10, fontWeight: '600', marginTop: 2 },
  filterRow: { flexDirection: 'row', gap: Spacing.sm, marginBottom: Spacing.md, flexWrap: 'wrap' },
  chip: { paddingHorizontal: Spacing.md, paddingVertical: 6, borderRadius: Radii.full, borderWidth: 1, borderColor: Colors.border, backgroundColor: Colors.surface },
  chipActive: { backgroundColor: Colors.blueprint, borderColor: Colors.blueprint },
  chipText: { ...Typography.caption, color: Colors.textMuted, fontWeight: '600' },
  chipTextActive: { color: Colors.white },
  empty: { alignItems: 'center', paddingTop: Spacing.xxl, gap: Spacing.md },
  emptyText: { ...Typography.body, color: Colors.textMuted },
  card: { backgroundColor: Colors.surface, borderRadius: Radii.md, padding: Spacing.md, marginBottom: Spacing.sm, borderWidth: 1, borderColor: Colors.border },
  cardTop: { flexDirection: 'row', alignItems: 'flex-start', gap: Spacing.sm, marginBottom: Spacing.sm },
  cardIcon: { width: 36, height: 36, borderRadius: Radii.sm, alignItems: 'center', justifyContent: 'center' },
  cardInfo: { flex: 1, minWidth: 0 },
  cardTitle: { ...Typography.bodySmall, color: Colors.textPrimary, fontWeight: '600' },
  cardLocation: { ...Typography.caption, color: Colors.textMuted, marginTop: 2 },
  badgeRow: { flexDirection: 'row', gap: 4, marginTop: 5, flexWrap: 'wrap' },
  badge: { borderWidth: 1, borderRadius: Radii.full, paddingHorizontal: 7, paddingVertical: 2 },
  badgeText: { fontSize: 9, fontWeight: '700', textTransform: 'uppercase' },
  roiText: { fontSize: 14, fontWeight: '800' },
  metricsRow: { flexDirection: 'row', justifyContent: 'space-between', paddingTop: Spacing.sm, borderTopWidth: 1, borderTopColor: Colors.border },
  miniMetric: { alignItems: 'center' },
  miniLabel: { fontSize: 10, color: Colors.textMuted },
  miniValue: { ...Typography.caption, color: Colors.textPrimary, fontWeight: '700', marginTop: 2 },
});
