import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radii, Typography } from '../theme';
import { api } from '../services/api';

interface Deal {
  id: number;
  name: string;
  amount: number;
  return_rate: number;
  status: string;
  asset_class: string;
  description: string;
  created_at: string;
}

const STATUS_COLORS: Record<string, string> = {
  active: Colors.success,
  open: Colors.info,
  funded: Colors.success,
  closed: Colors.steel,
  pending: Colors.warning,
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
    } catch (err: any) {
      Alert.alert('Error', err.response?.data?.error || 'Could not load deal details.');
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

  const formatCurrency = (val: number) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(val);

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.centered}><ActivityIndicator size="large" color={Colors.blueprint} /></View>
      </SafeAreaView>
    );
  }

  if (!deal) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.centered}><Text style={styles.errorText}>Deal not found.</Text></View>
      </SafeAreaView>
    );
  }

  const statusColor = STATUS_COLORS[deal.status] || Colors.steel;

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.navBar}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Ionicons name="chevron-back" size={24} color={Colors.textPrimary} />
          <Text style={styles.backText}>Deals</Text>
        </TouchableOpacity>
      </View>
      <ScrollView
        contentContainerStyle={styles.scroll}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.blueprint} />}
      >
        <View style={styles.titleRow}>
          <Text style={styles.title}>{deal.name || 'Unnamed Deal'}</Text>
          <View style={[styles.statusBadge, { backgroundColor: statusColor + '22', borderColor: statusColor }]}>
            <Text style={[styles.statusText, { color: statusColor }]}>{deal.status}</Text>
          </View>
        </View>
        {deal.asset_class ? <Text style={styles.assetClass}>{deal.asset_class}</Text> : null}

        <View style={styles.metricsRow}>
          <View style={styles.metricCard}>
            <Text style={styles.metricLabel}>Investment</Text>
            <Text style={styles.metricValue}>{formatCurrency(deal.amount)}</Text>
          </View>
          <View style={styles.metricCard}>
            <Text style={styles.metricLabel}>Return Rate</Text>
            <Text style={[styles.metricValue, { color: Colors.success }]}>{deal.return_rate.toFixed(2)}%</Text>
          </View>
        </View>

        {deal.description ? (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Description</Text>
            <Text style={styles.description}>{deal.description}</Text>
          </View>
        ) : null}

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Details</Text>
          <DetailRow label="Status" value={deal.status} />
          <DetailRow label="Asset Class" value={deal.asset_class || '—'} />
          <DetailRow label="Created" value={deal.created_at ? new Date(deal.created_at).toLocaleDateString() : '—'} />
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.detailRow}>
      <Text style={styles.detailLabel}>{label}</Text>
      <Text style={styles.detailValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  errorText: { ...Typography.body, color: Colors.danger },
  navBar: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: Spacing.md, paddingVertical: Spacing.sm },
  backBtn: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  backText: { ...Typography.body, color: Colors.textPrimary },
  scroll: { padding: Spacing.lg },
  titleRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: Spacing.xs },
  title: { ...Typography.h2, color: Colors.textPrimary, flex: 1, marginRight: Spacing.sm },
  statusBadge: { borderWidth: 1, borderRadius: Radii.full, paddingHorizontal: Spacing.sm, paddingVertical: 3 },
  statusText: { ...Typography.caption, fontWeight: '700', textTransform: 'uppercase' },
  assetClass: { ...Typography.bodySmall, color: Colors.textMuted, marginBottom: Spacing.lg },
  metricsRow: { flexDirection: 'row', gap: Spacing.sm, marginBottom: Spacing.lg },
  metricCard: {
    flex: 1,
    backgroundColor: Colors.surface,
    borderRadius: Radii.md,
    padding: Spacing.md,
    borderWidth: 1,
    borderColor: Colors.border,
    alignItems: 'center',
  },
  metricLabel: { ...Typography.caption, color: Colors.textMuted, marginBottom: 4 },
  metricValue: { fontSize: 22, fontWeight: '800', color: Colors.blueprint },
  section: {
    backgroundColor: Colors.surface,
    borderRadius: Radii.md,
    padding: Spacing.md,
    marginBottom: Spacing.md,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  sectionTitle: { ...Typography.label, color: Colors.textMuted, marginBottom: Spacing.sm },
  description: { ...Typography.body, color: Colors.textSecondary, lineHeight: 24 },
  detailRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: Spacing.xs },
  detailLabel: { ...Typography.bodySmall, color: Colors.textMuted },
  detailValue: { ...Typography.bodySmall, color: Colors.textPrimary, fontWeight: '600' },
});
