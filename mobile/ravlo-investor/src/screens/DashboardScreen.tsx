import React, { useEffect, useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, RefreshControl,
  TouchableOpacity, ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radii, Typography } from '../theme';
import { useAuthStore } from '../store/authStore';
import { api } from '../services/api';

const STRATEGY_ICONS: Record<string, any> = {
  'fix_and_flip': 'hammer-outline',
  'brrrr': 'repeat-outline',
  'buy_and_hold': 'home-outline',
  'wholesale': 'swap-horizontal-outline',
  'new_construction': 'business-outline',
};

const STRATEGY_COLORS: Record<string, string> = {
  'fix_and_flip': Colors.warning,
  'brrrr': Colors.blueprint,
  'buy_and_hold': Colors.success,
  'wholesale': Colors.info,
  'new_construction': Colors.softGlow,
};

const STATUS_COLORS: Record<string, string> = {
  active: Colors.success,
  funded: Colors.blueprint,
  closed: Colors.steel,
  pending: Colors.warning,
};

interface DealSummary {
  id: number;
  title: string;
  address: string;
  strategy: string;
  purchase_price: number;
  roi_percent: number;
  deal_score: number | null;
  status: string;
  submitted_for_funding: boolean;
}

interface DashboardData {
  total_deals: number;
  active_deals: number;
  funded_deals: number;
  avg_roi: number;
  avg_deal_score: number;
  strategy_breakdown: Record<string, number>;
  recent_deals: DealSummary[];
}

export default function DashboardScreen({ navigation }: any) {
  const { user } = useAuthStore();
  const [data, setData] = useState<DashboardData | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const res = await api.get('/mobile/investor/dashboard');
      setData(res.data);
    } catch {
      // show dashes on error
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchData();
    setRefreshing(false);
  }, [fetchData]);

  const fmt = (val: number) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', notation: 'compact', maximumFractionDigits: 1 }).format(val);

  const strategyLabel = (s: string) =>
    (s || 'Unknown').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

  const scoreColor = (score: number | null) => {
    if (!score) return Colors.steel;
    if (score >= 80) return Colors.success;
    if (score >= 60) return Colors.warning;
    return Colors.danger;
  };

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView
        contentContainerStyle={styles.scroll}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.blueprint} />}
      >
        {/* Header */}
        <View style={styles.header}>
          <View>
            <Text style={styles.greeting}>Welcome back,</Text>
            <Text style={styles.userName}>{user?.first_name || 'Investor'}</Text>
          </View>
          <View style={styles.roleBadge}>
            <Ionicons name="trending-up-outline" size={14} color={Colors.success} />
            <Text style={styles.roleText}>Investor</Text>
          </View>
        </View>

        {/* Stats grid */}
        <Text style={styles.sectionTitle}>Portfolio Overview</Text>
        <View style={styles.statsGrid}>
          <StatCard label="Total Deals" value={String(data?.total_deals ?? '—')} icon="layers-outline" color={Colors.blueprint} />
          <StatCard label="Active" value={String(data?.active_deals ?? '—')} icon="pulse-outline" color={Colors.success} />
          <StatCard label="Funded" value={String(data?.funded_deals ?? '—')} icon="checkmark-circle-outline" color={Colors.warning} />
          <StatCard
            label="Avg ROI"
            value={data ? `${data.avg_roi.toFixed(1)}%` : '—'}
            icon="trending-up-outline"
            color={Colors.success}
          />
        </View>

        {/* Deal score highlight */}
        {(data?.avg_deal_score ?? 0) > 0 && (
          <View style={styles.scoreCard}>
            <View style={styles.scoreLeft}>
              <Text style={styles.scoreTitle}>Avg Deal Score</Text>
              <Text style={styles.scoreSubtitle}>Across all analyzed deals</Text>
            </View>
            <View style={[styles.scoreBadge, { backgroundColor: scoreColor(data!.avg_deal_score) + '22', borderColor: scoreColor(data!.avg_deal_score) }]}>
              <Text style={[styles.scoreValue, { color: scoreColor(data!.avg_deal_score) }]}>
                {data!.avg_deal_score.toFixed(0)}
              </Text>
              <Text style={[styles.scoreMax, { color: scoreColor(data!.avg_deal_score) }]}>/100</Text>
            </View>
          </View>
        )}

        {/* Strategy breakdown */}
        {data?.strategy_breakdown && Object.keys(data.strategy_breakdown).length > 0 && (
          <>
            <Text style={styles.sectionTitle}>By Strategy</Text>
            <View style={styles.strategyRow}>
              {Object.entries(data.strategy_breakdown).map(([s, count]) => {
                const color = STRATEGY_COLORS[s] || Colors.steel;
                const icon = STRATEGY_ICONS[s] || 'briefcase-outline';
                return (
                  <View key={s} style={[styles.strategyChip, { borderColor: color + '66', backgroundColor: color + '11' }]}>
                    <Ionicons name={icon} size={14} color={color} />
                    <Text style={[styles.strategyLabel, { color }]}>{strategyLabel(s)}</Text>
                    <Text style={[styles.strategyCount, { color }]}>{count}</Text>
                  </View>
                );
              })}
            </View>
          </>
        )}

        {/* Quick actions */}
        <Text style={styles.sectionTitle}>Quick Actions</Text>
        <View style={styles.actionsRow}>
          <ActionBtn icon="layers-outline" label="My Deals" onPress={() => navigation.navigate('Deals')} />
          <ActionBtn icon="search-outline" label="Opportunities" onPress={() => navigation.navigate('Opportunities')} />
          <ActionBtn icon="sparkles-outline" label="Ravlo AI" onPress={() => navigation.navigate('RavloAI')} />
        </View>

        {/* Recent deals */}
        {(data?.recent_deals?.length ?? 0) > 0 && (
          <>
            <View style={styles.sectionRow}>
              <Text style={styles.sectionTitle}>Recent Deals</Text>
              <TouchableOpacity onPress={() => navigation.navigate('Deals')}>
                <Text style={styles.seeAll}>See all</Text>
              </TouchableOpacity>
            </View>
            {data!.recent_deals.map(deal => {
              const sc = scoreColor(deal.deal_score);
              const statusColor = STATUS_COLORS[deal.status] || Colors.steel;
              return (
                <TouchableOpacity
                  key={deal.id}
                  style={styles.dealCard}
                  onPress={() => navigation.navigate('Deals', { screen: 'DealDetail', params: { dealId: deal.id } })}
                  activeOpacity={0.75}
                >
                  <View style={styles.dealHeader}>
                    <View style={styles.dealIcon}>
                      <Ionicons name={STRATEGY_ICONS[deal.strategy] || 'home-outline'} size={18} color={STRATEGY_COLORS[deal.strategy] || Colors.blueprint} />
                    </View>
                    <View style={styles.dealInfo}>
                      <Text style={styles.dealTitle} numberOfLines={1}>{deal.title || deal.address || 'Untitled'}</Text>
                      <Text style={styles.dealStrategy}>{strategyLabel(deal.strategy)}</Text>
                    </View>
                    <View style={styles.dealRight}>
                      {deal.deal_score !== null && (
                        <View style={[styles.dealScore, { backgroundColor: sc + '22', borderColor: sc }]}>
                          <Text style={[styles.dealScoreText, { color: sc }]}>{deal.deal_score}</Text>
                        </View>
                      )}
                      <Text style={[styles.dealROI, deal.roi_percent >= 0 ? styles.positive : styles.negative]}>
                        {deal.roi_percent >= 0 ? '+' : ''}{deal.roi_percent.toFixed(1)}%
                      </Text>
                    </View>
                  </View>
                  {deal.purchase_price > 0 && (
                    <Text style={styles.dealPrice}>{fmt(deal.purchase_price)} purchase</Text>
                  )}
                  {deal.submitted_for_funding && (
                    <View style={styles.fundingBadge}>
                      <Ionicons name="checkmark-circle" size={12} color={Colors.warning} />
                      <Text style={styles.fundingText}>Submitted for funding</Text>
                    </View>
                  )}
                </TouchableOpacity>
              );
            })}
          </>
        )}
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

function ActionBtn({ icon, label, onPress }: any) {
  return (
    <TouchableOpacity style={styles.actionCard} onPress={onPress} activeOpacity={0.75}>
      <Ionicons name={icon} size={22} color={Colors.blueprint} />
      <Text style={styles.actionLabel}>{label}</Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  scroll: { padding: Spacing.lg },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: Spacing.lg },
  greeting: { ...Typography.bodySmall, color: Colors.textMuted },
  userName: { ...Typography.h2, color: Colors.textPrimary, marginTop: 2 },
  roleBadge: { flexDirection: 'row', alignItems: 'center', gap: 5, backgroundColor: Colors.success + '22', borderRadius: Radii.full, paddingHorizontal: Spacing.sm, paddingVertical: 4 },
  roleText: { ...Typography.caption, color: Colors.success, fontWeight: '600' },
  sectionTitle: { ...Typography.label, color: Colors.textMuted, marginBottom: Spacing.md, marginTop: Spacing.sm },
  sectionRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: Spacing.sm, marginBottom: Spacing.md },
  seeAll: { ...Typography.caption, color: Colors.blueprint },
  statsGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.sm, marginBottom: Spacing.lg },
  statCard: { flex: 1, minWidth: '45%', backgroundColor: Colors.surface, borderRadius: Radii.md, padding: Spacing.md, borderWidth: 1, borderColor: Colors.border },
  statIcon: { width: 36, height: 36, borderRadius: Radii.sm, alignItems: 'center', justifyContent: 'center', marginBottom: Spacing.sm },
  statValue: { ...Typography.h3, color: Colors.textPrimary },
  statLabel: { ...Typography.caption, color: Colors.textMuted, marginTop: 2 },
  scoreCard: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', backgroundColor: Colors.surface, borderRadius: Radii.md, padding: Spacing.md, borderWidth: 1, borderColor: Colors.border, marginBottom: Spacing.lg },
  scoreLeft: {},
  scoreTitle: { ...Typography.body, color: Colors.textPrimary, fontWeight: '600' },
  scoreSubtitle: { ...Typography.caption, color: Colors.textMuted, marginTop: 2 },
  scoreBadge: { flexDirection: 'row', alignItems: 'baseline', borderWidth: 1.5, borderRadius: Radii.md, paddingHorizontal: Spacing.md, paddingVertical: Spacing.sm },
  scoreValue: { fontSize: 28, fontWeight: '800' },
  scoreMax: { fontSize: 13, fontWeight: '600', marginLeft: 2 },
  strategyRow: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.sm, marginBottom: Spacing.lg },
  strategyChip: { flexDirection: 'row', alignItems: 'center', gap: 5, borderWidth: 1, borderRadius: Radii.full, paddingHorizontal: Spacing.sm, paddingVertical: 5 },
  strategyLabel: { ...Typography.caption, fontWeight: '600' },
  strategyCount: { ...Typography.caption, fontWeight: '800' },
  actionsRow: { flexDirection: 'row', gap: Spacing.sm, marginBottom: Spacing.lg },
  actionCard: { flex: 1, backgroundColor: Colors.surface, borderRadius: Radii.md, padding: Spacing.md, alignItems: 'center', borderWidth: 1, borderColor: Colors.border, gap: Spacing.xs },
  actionLabel: { ...Typography.caption, color: Colors.textSecondary, textAlign: 'center' },
  dealCard: { backgroundColor: Colors.surface, borderRadius: Radii.md, padding: Spacing.md, borderWidth: 1, borderColor: Colors.border, marginBottom: Spacing.sm },
  dealHeader: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm },
  dealIcon: { width: 36, height: 36, borderRadius: Radii.sm, backgroundColor: Colors.blueprint + '22', alignItems: 'center', justifyContent: 'center' },
  dealInfo: { flex: 1, minWidth: 0 },
  dealTitle: { ...Typography.bodySmall, color: Colors.textPrimary, fontWeight: '600' },
  dealStrategy: { ...Typography.caption, color: Colors.textMuted, marginTop: 1 },
  dealRight: { alignItems: 'flex-end', gap: 4 },
  dealScore: { borderWidth: 1, borderRadius: Radii.sm, paddingHorizontal: 6, paddingVertical: 2 },
  dealScoreText: { fontSize: 11, fontWeight: '800' },
  dealROI: { ...Typography.caption, fontWeight: '700' },
  positive: { color: Colors.success },
  negative: { color: Colors.danger },
  dealPrice: { ...Typography.caption, color: Colors.textMuted, marginTop: 6, marginLeft: 44 },
  fundingBadge: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 6, marginLeft: 44 },
  fundingText: { ...Typography.caption, color: Colors.warning },
});
