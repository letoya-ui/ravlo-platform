import React, { useEffect, useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, RefreshControl,
  TouchableOpacity, ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radii, Typography } from '../theme';
import { api } from '../services/api';

interface Deal {
  id: number;
  title: string;
  address: string;
  city: string;
  state: string;
  strategy: string;
  purchase_price: number;
  arv: number;
  rehab_cost: number;
  estimated_rent: number;
  deal_score: number | null;
  roi_percent: number;
  estimated_profit: number;
  status: string;
  submitted_for_funding: boolean;
  reveal_is_public: boolean;
  notes: string;
  created_at: string;
  updated_at: string;
}

const STATUS_COLORS: Record<string, string> = {
  active: Colors.success,
  funded: Colors.blueprint,
  closed: Colors.steel,
  pending: Colors.warning,
};

const STRATEGY_COLORS: Record<string, string> = {
  fix_and_flip: Colors.warning,
  brrrr: Colors.blueprint,
  buy_and_hold: Colors.success,
  wholesale: Colors.info,
  new_construction: Colors.softGlow,
};

const STRATEGY_ICONS: Record<string, any> = {
  fix_and_flip: 'hammer-outline',
  brrrr: 'repeat-outline',
  buy_and_hold: 'home-outline',
  wholesale: 'swap-horizontal-outline',
  new_construction: 'business-outline',
};

export default function DealDetailScreen({ route, navigation }: any) {
  const { dealId } = route.params;
  const [deal, setDeal] = useState<Deal | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchDeal = useCallback(async () => {
    try {
      const res = await api.get(`/mobile/investor/deals/${dealId}`);
      setDeal(res.data.deal);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [dealId]);

  useEffect(() => { fetchDeal(); }, [fetchDeal]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchDeal();
    setRefreshing(false);
  }, [fetchDeal]);

  const fmt = (val: number) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', notation: 'compact', maximumFractionDigits: 1 }).format(val);

  const fmtFull = (val: number) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(val);

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <ActivityIndicator color={Colors.blueprint} style={{ flex: 1 }} />
      </SafeAreaView>
    );
  }

  if (!deal) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.centered}>
          <Ionicons name="alert-circle-outline" size={40} color={Colors.danger} />
          <Text style={styles.errorText}>Deal not found.</Text>
        </View>
      </SafeAreaView>
    );
  }

  const statusColor = STATUS_COLORS[deal.status] || Colors.steel;
  const stratColor = STRATEGY_COLORS[deal.strategy] || Colors.blueprint;
  const stratIcon = STRATEGY_ICONS[deal.strategy] || 'home-outline';
  const stratLabel = (deal.strategy || 'Unknown').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  const location = [deal.address, deal.city, deal.state].filter(Boolean).join(', ');

  const scoreColor = deal.deal_score
    ? deal.deal_score >= 80 ? Colors.success : deal.deal_score >= 60 ? Colors.warning : Colors.danger
    : Colors.steel;

  const totalProjectCost = deal.purchase_price + deal.rehab_cost;

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.nav}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Ionicons name="chevron-back" size={24} color={Colors.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.navTitle} numberOfLines={1}>{deal.title || 'Deal Detail'}</Text>
        <View style={{ width: 40 }} />
      </View>

      <ScrollView
        contentContainerStyle={styles.scroll}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.blueprint} />}
      >
        {/* Header */}
        <View style={styles.headerCard}>
          <View style={styles.headerTop}>
            <View style={[styles.stratIconBox, { backgroundColor: stratColor + '22' }]}>
              <Ionicons name={stratIcon} size={22} color={stratColor} />
            </View>
            <View style={styles.headerInfo}>
              <Text style={styles.dealTitle}>{deal.title || deal.address || 'Untitled Deal'}</Text>
              {location ? <Text style={styles.dealLocation} numberOfLines={2}>{location}</Text> : null}
              <View style={styles.badgeRow}>
                <View style={[styles.badge, { backgroundColor: stratColor + '22', borderColor: stratColor + '66' }]}>
                  <Text style={[styles.badgeText, { color: stratColor }]}>{stratLabel}</Text>
                </View>
                <View style={[styles.badge, { backgroundColor: statusColor + '22', borderColor: statusColor + '66' }]}>
                  <Text style={[styles.badgeText, { color: statusColor }]}>{deal.status}</Text>
                </View>
              </View>
            </View>
            {deal.deal_score !== null && (
              <View style={[styles.scoreBox, { backgroundColor: scoreColor + '22', borderColor: scoreColor }]}>
                <Text style={[styles.scoreValue, { color: scoreColor }]}>{deal.deal_score}</Text>
                <Text style={[styles.scoreLabel, { color: scoreColor }]}>score</Text>
              </View>
            )}
          </View>

          {deal.submitted_for_funding && (
            <View style={styles.fundingBanner}>
              <Ionicons name="checkmark-circle" size={14} color={Colors.warning} />
              <Text style={styles.fundingText}>Submitted for funding</Text>
            </View>
          )}
        </View>

        {/* Key numbers */}
        <Text style={styles.sectionTitle}>Deal Numbers</Text>
        <View style={styles.metricsGrid}>
          <MetricCard label="Purchase Price" value={fmtFull(deal.purchase_price)} color={Colors.blueprint} icon="home-outline" />
          <MetricCard label="After Repair Value" value={fmtFull(deal.arv)} color={Colors.success} icon="trending-up-outline" />
          <MetricCard label="Rehab Cost" value={fmtFull(deal.rehab_cost)} color={Colors.warning} icon="hammer-outline" />
          <MetricCard label="Total Project Cost" value={fmtFull(totalProjectCost)} color={Colors.info} icon="layers-outline" />
        </View>

        {/* Returns */}
        <View style={styles.returnsCard}>
          <View style={styles.returnItem}>
            <Text style={styles.returnLabel}>Est. Profit</Text>
            <Text style={[styles.returnValue, deal.estimated_profit >= 0 ? styles.positive : styles.negative]}>
              {deal.estimated_profit >= 0 ? '+' : ''}{fmtFull(deal.estimated_profit)}
            </Text>
          </View>
          <View style={styles.returnDivider} />
          <View style={styles.returnItem}>
            <Text style={styles.returnLabel}>ROI</Text>
            <Text style={[styles.returnValue, deal.roi_percent >= 0 ? styles.positive : styles.negative]}>
              {deal.roi_percent >= 0 ? '+' : ''}{deal.roi_percent.toFixed(2)}%
            </Text>
          </View>
          {deal.estimated_rent > 0 && (
            <>
              <View style={styles.returnDivider} />
              <View style={styles.returnItem}>
                <Text style={styles.returnLabel}>Est. Rent/mo</Text>
                <Text style={[styles.returnValue, { color: Colors.success }]}>{fmt(deal.estimated_rent)}</Text>
              </View>
            </>
          )}
        </View>

        {/* Notes */}
        {deal.notes ? (
          <>
            <Text style={styles.sectionTitle}>Notes</Text>
            <View style={styles.notesCard}>
              <Text style={styles.notesText}>{deal.notes}</Text>
            </View>
          </>
        ) : null}

        {/* Meta */}
        <Text style={styles.sectionTitle}>Info</Text>
        <View style={styles.infoCard}>
          <InfoRow label="Created" value={new Date(deal.created_at).toLocaleDateString()} />
          <InfoRow label="Updated" value={new Date(deal.updated_at).toLocaleDateString()} />
          <InfoRow label="Public" value={deal.reveal_is_public ? 'Yes — shared publicly' : 'No'} />
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

function MetricCard({ label, value, color, icon }: { label: string; value: string; color: string; icon: any }) {
  return (
    <View style={styles.metricCard}>
      <View style={[styles.metricIcon, { backgroundColor: color + '22' }]}>
        <Ionicons name={icon} size={16} color={color} />
      </View>
      <Text style={styles.metricLabel}>{label}</Text>
      <Text style={[styles.metricValue, { color }]}>{value}</Text>
    </View>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.infoRow}>
      <Text style={styles.infoLabel}>{label}</Text>
      <Text style={styles.infoValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: Spacing.md },
  errorText: { ...Typography.body, color: Colors.danger },
  nav: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: Spacing.md, paddingVertical: Spacing.sm },
  backBtn: { padding: 8 },
  navTitle: { ...Typography.bodySmall, color: Colors.textPrimary, fontWeight: '700', flex: 1, textAlign: 'center' },
  scroll: { padding: Spacing.lg, paddingBottom: Spacing.xxl },
  headerCard: { backgroundColor: Colors.surface, borderRadius: Radii.md, padding: Spacing.md, borderWidth: 1, borderColor: Colors.border, marginBottom: Spacing.lg },
  headerTop: { flexDirection: 'row', alignItems: 'flex-start', gap: Spacing.sm },
  stratIconBox: { width: 46, height: 46, borderRadius: Radii.sm, alignItems: 'center', justifyContent: 'center' },
  headerInfo: { flex: 1, minWidth: 0 },
  dealTitle: { ...Typography.body, color: Colors.textPrimary, fontWeight: '700' },
  dealLocation: { ...Typography.caption, color: Colors.textMuted, marginTop: 3 },
  badgeRow: { flexDirection: 'row', gap: Spacing.xs, marginTop: 6, flexWrap: 'wrap' },
  badge: { borderWidth: 1, borderRadius: Radii.full, paddingHorizontal: 8, paddingVertical: 2 },
  badgeText: { fontSize: 10, fontWeight: '700' },
  scoreBox: { width: 50, height: 50, borderRadius: Radii.sm, borderWidth: 1.5, alignItems: 'center', justifyContent: 'center' },
  scoreValue: { fontSize: 18, fontWeight: '800' },
  scoreLabel: { fontSize: 9, fontWeight: '600' },
  fundingBanner: { flexDirection: 'row', alignItems: 'center', gap: 5, marginTop: Spacing.sm, paddingTop: Spacing.sm, borderTopWidth: 1, borderTopColor: Colors.border },
  fundingText: { ...Typography.caption, color: Colors.warning, fontWeight: '600' },
  sectionTitle: { ...Typography.label, color: Colors.textMuted, marginBottom: Spacing.md, marginTop: Spacing.sm },
  metricsGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.sm, marginBottom: Spacing.lg },
  metricCard: { flex: 1, minWidth: '45%', backgroundColor: Colors.surface, borderRadius: Radii.md, padding: Spacing.md, borderWidth: 1, borderColor: Colors.border },
  metricIcon: { width: 32, height: 32, borderRadius: Radii.sm, alignItems: 'center', justifyContent: 'center', marginBottom: Spacing.sm },
  metricLabel: { ...Typography.caption, color: Colors.textMuted },
  metricValue: { ...Typography.body, fontWeight: '700', marginTop: 3 },
  returnsCard: { flexDirection: 'row', backgroundColor: Colors.surface, borderRadius: Radii.md, padding: Spacing.md, borderWidth: 1, borderColor: Colors.border, marginBottom: Spacing.lg },
  returnItem: { flex: 1, alignItems: 'center' },
  returnLabel: { ...Typography.caption, color: Colors.textMuted },
  returnValue: { ...Typography.h3, marginTop: 4 },
  returnDivider: { width: 1, backgroundColor: Colors.border, marginHorizontal: Spacing.sm },
  positive: { color: Colors.success },
  negative: { color: Colors.danger },
  notesCard: { backgroundColor: Colors.surface, borderRadius: Radii.md, padding: Spacing.md, borderWidth: 1, borderColor: Colors.border, marginBottom: Spacing.lg },
  notesText: { ...Typography.body, color: Colors.textSecondary, lineHeight: 24 },
  infoCard: { backgroundColor: Colors.surface, borderRadius: Radii.md, borderWidth: 1, borderColor: Colors.border, overflow: 'hidden', marginBottom: Spacing.lg },
  infoRow: { flexDirection: 'row', justifyContent: 'space-between', padding: Spacing.md, borderBottomWidth: 1, borderBottomColor: Colors.border },
  infoLabel: { ...Typography.bodySmall, color: Colors.textMuted },
  infoValue: { ...Typography.bodySmall, color: Colors.textPrimary, fontWeight: '600' },
});
