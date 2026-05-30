import React, { useEffect, useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, FlatList, TouchableOpacity,
  RefreshControl, ActivityIndicator,
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
  roi_percent: number;
  estimated_profit: number;
  deal_score: number | null;
  status: string;
}

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

export default function OpportunitiesScreen({ navigation }: any) {
  const [deals, setDeals] = useState<Deal[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchOpportunities = useCallback(async () => {
    try {
      const res = await api.get('/mobile/investor/opportunities');
      setDeals(res.data.opportunities || []);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchOpportunities(); }, [fetchOpportunities]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchOpportunities();
    setRefreshing(false);
  }, [fetchOpportunities]);

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
        <Text style={styles.title}>Opportunities</Text>
        <Text style={styles.subtitle}>Publicly shared deals</Text>
      </View>

      <FlatList
        data={deals}
        keyExtractor={d => String(d.id)}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.blueprint} />}
        contentContainerStyle={styles.listContent}
        ListEmptyComponent={
          <View style={styles.empty}>
            <Ionicons name="search-outline" size={48} color={Colors.textMuted} />
            <Text style={styles.emptyText}>No opportunities available right now</Text>
          </View>
        }
        renderItem={({ item }) => {
          const stratColor = STRATEGY_COLORS[item.strategy] || Colors.blueprint;
          const sc = scoreColor(item.deal_score);
          const location = [item.city, item.state].filter(Boolean).join(', ');
          return (
            <TouchableOpacity
              style={styles.card}
              onPress={() => navigation.navigate('DealDetail', { dealId: item.id })}
              activeOpacity={0.75}
            >
              <View style={styles.cardTop}>
                <View style={[styles.stratIcon, { backgroundColor: stratColor + '22' }]}>
                  <Ionicons name={STRATEGY_ICONS[item.strategy] || 'home-outline'} size={20} color={stratColor} />
                </View>
                <View style={styles.cardInfo}>
                  <Text style={styles.cardTitle} numberOfLines={1}>{item.title || item.address || 'Untitled'}</Text>
                  {location ? <Text style={styles.cardLocation}>{location}</Text> : null}
                  <View style={[styles.stratBadge, { backgroundColor: stratColor + '22', borderColor: stratColor + '66' }]}>
                    <Text style={[styles.stratText, { color: stratColor }]}>{strategyLabel(item.strategy)}</Text>
                  </View>
                </View>
                {item.deal_score !== null && (
                  <View style={[styles.scoreBadge, { backgroundColor: sc + '22', borderColor: sc }]}>
                    <Text style={[styles.scoreValue, { color: sc }]}>{item.deal_score}</Text>
                  </View>
                )}
              </View>

              <View style={styles.metricsRow}>
                <Metric label="Purchase" value={fmt(item.purchase_price)} />
                <Metric label="ARV" value={fmt(item.arv)} />
                <Metric label="Rehab" value={fmt(item.rehab_cost)} />
                <Metric
                  label="ROI"
                  value={`${item.roi_percent >= 0 ? '+' : ''}${item.roi_percent.toFixed(1)}%`}
                  valueColor={item.roi_percent >= 0 ? Colors.success : Colors.danger}
                />
              </View>

              {item.estimated_profit > 0 && (
                <View style={styles.profitRow}>
                  <Ionicons name="trending-up-outline" size={13} color={Colors.success} />
                  <Text style={styles.profitText}>Est. profit: {fmt(item.estimated_profit)}</Text>
                </View>
              )}
            </TouchableOpacity>
          );
        }}
      />
    </SafeAreaView>
  );
}

function Metric({ label, value, valueColor }: { label: string; value: string; valueColor?: string }) {
  return (
    <View style={styles.metric}>
      <Text style={styles.metricLabel}>{label}</Text>
      <Text style={[styles.metricValue, valueColor ? { color: valueColor } : {}]}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  header: { paddingHorizontal: Spacing.lg, paddingTop: Spacing.md, paddingBottom: Spacing.sm },
  title: { ...Typography.h2, color: Colors.textPrimary },
  subtitle: { ...Typography.caption, color: Colors.textMuted, marginTop: 2 },
  listContent: { paddingHorizontal: Spacing.lg, paddingBottom: Spacing.xl },
  card: { backgroundColor: Colors.surface, borderRadius: Radii.md, padding: Spacing.md, borderWidth: 1, borderColor: Colors.border, marginBottom: Spacing.sm },
  cardTop: { flexDirection: 'row', alignItems: 'flex-start', gap: Spacing.sm, marginBottom: Spacing.md },
  stratIcon: { width: 42, height: 42, borderRadius: Radii.sm, alignItems: 'center', justifyContent: 'center' },
  cardInfo: { flex: 1, minWidth: 0 },
  cardTitle: { ...Typography.bodySmall, color: Colors.textPrimary, fontWeight: '600' },
  cardLocation: { ...Typography.caption, color: Colors.textMuted, marginTop: 2 },
  stratBadge: { alignSelf: 'flex-start', borderWidth: 1, borderRadius: Radii.full, paddingHorizontal: 8, paddingVertical: 2, marginTop: 5 },
  stratText: { fontSize: 10, fontWeight: '700' },
  scoreBadge: { width: 42, height: 42, borderRadius: Radii.sm, borderWidth: 1.5, alignItems: 'center', justifyContent: 'center' },
  scoreValue: { fontSize: 15, fontWeight: '800' },
  metricsRow: { flexDirection: 'row', justifyContent: 'space-between', paddingTop: Spacing.sm, borderTopWidth: 1, borderTopColor: Colors.border },
  metric: { alignItems: 'center' },
  metricLabel: { ...Typography.caption, color: Colors.textMuted },
  metricValue: { ...Typography.bodySmall, color: Colors.textPrimary, fontWeight: '700', marginTop: 2 },
  profitRow: { flexDirection: 'row', alignItems: 'center', gap: 5, marginTop: Spacing.sm },
  profitText: { ...Typography.caption, color: Colors.success, fontWeight: '600' },
  empty: { alignItems: 'center', paddingTop: 80, gap: Spacing.md },
  emptyText: { ...Typography.body, color: Colors.textMuted, textAlign: 'center' },
});
