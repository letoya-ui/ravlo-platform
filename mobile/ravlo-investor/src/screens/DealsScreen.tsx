import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  FlatList,
  StyleSheet,
  TouchableOpacity,
  RefreshControl,
  Alert,
  ActivityIndicator,
  ScrollView,
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
}

const STATUS_COLORS: Record<string, string> = {
  active: Colors.success,
  open: Colors.info,
  funded: Colors.success,
  closed: Colors.steel,
  pending: Colors.warning,
};

const ALL_FILTER = 'All';

export default function DealsScreen({ navigation }: any) {
  const [deals, setDeals] = useState<Deal[]>([]);
  const [filtered, setFiltered] = useState<Deal[]>([]);
  const [activeFilter, setActiveFilter] = useState(ALL_FILTER);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const statuses = [ALL_FILTER, 'active', 'open', 'funded', 'closed', 'pending'];

  const fetchDeals = useCallback(async () => {
    try {
      const res = await api.get('/mobile/investor/deals');
      const data: Deal[] = res.data.deals || [];
      setDeals(data);
      setFiltered(activeFilter === ALL_FILTER ? data : data.filter((d) => d.status === activeFilter));
    } catch (err: any) {
      Alert.alert('Error', err.response?.data?.error || 'Could not load deals.');
    } finally {
      setLoading(false);
    }
  }, [activeFilter]);

  useEffect(() => { fetchDeals(); }, [fetchDeals]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchDeals();
    setRefreshing(false);
  }, [fetchDeals]);

  const applyFilter = (status: string) => {
    setActiveFilter(status);
    setFiltered(status === ALL_FILTER ? deals : deals.filter((d) => d.status === status));
  };

  const formatCurrency = (val: number) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', notation: 'compact', maximumFractionDigits: 1 }).format(val);

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.centered}><ActivityIndicator size="large" color={Colors.blueprint} /></View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Deals</Text>
      </View>

      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.filterScroll} contentContainerStyle={styles.filterRow}>
        {statuses.map((s) => (
          <TouchableOpacity
            key={s}
            style={[styles.filterChip, activeFilter === s && styles.filterChipActive]}
            onPress={() => applyFilter(s)}
          >
            <Text style={[styles.filterText, activeFilter === s && styles.filterTextActive]}>
              {s.charAt(0).toUpperCase() + s.slice(1)}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      <FlatList
        data={filtered}
        keyExtractor={(item) => String(item.id)}
        contentContainerStyle={styles.list}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.blueprint} />}
        ListEmptyComponent={
          <View style={styles.empty}>
            <Ionicons name="trending-up-outline" size={48} color={Colors.textMuted} />
            <Text style={styles.emptyText}>No deals found</Text>
          </View>
        }
        renderItem={({ item }) => (
          <TouchableOpacity
            style={styles.card}
            onPress={() => navigation.navigate('DealDetail', { dealId: item.id })}
            activeOpacity={0.75}
          >
            <View style={styles.cardHeader}>
              <Text style={styles.dealName} numberOfLines={1}>{item.name || 'Unnamed Deal'}</Text>
              <View style={[styles.statusBadge, { backgroundColor: (STATUS_COLORS[item.status] || Colors.steel) + '22' }]}>
                <Text style={[styles.statusText, { color: STATUS_COLORS[item.status] || Colors.steel }]}>{item.status}</Text>
              </View>
            </View>
            {item.asset_class ? <Text style={styles.assetClass}>{item.asset_class}</Text> : null}
            <View style={styles.cardFooter}>
              <Text style={styles.amount}>{formatCurrency(item.amount)}</Text>
              <Text style={styles.returnRate}>{item.return_rate.toFixed(2)}% return</Text>
            </View>
          </TouchableOpacity>
        )}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  header: { paddingHorizontal: Spacing.lg, paddingTop: Spacing.md, paddingBottom: Spacing.sm },
  title: { ...Typography.h2, color: Colors.textPrimary },
  filterScroll: { flexGrow: 0 },
  filterRow: { paddingHorizontal: Spacing.lg, paddingBottom: Spacing.md, gap: Spacing.sm },
  filterChip: {
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.xs + 2,
    borderRadius: Radii.full,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.surface,
  },
  filterChipActive: { borderColor: Colors.blueprint, backgroundColor: Colors.blueprint + '22' },
  filterText: { ...Typography.caption, color: Colors.textMuted, fontWeight: '600' },
  filterTextActive: { color: Colors.blueprint },
  list: { paddingHorizontal: Spacing.lg, paddingBottom: Spacing.xl },
  card: {
    backgroundColor: Colors.surface,
    borderRadius: Radii.md,
    padding: Spacing.md,
    marginBottom: Spacing.sm,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 },
  dealName: { ...Typography.body, color: Colors.textPrimary, fontWeight: '600', flex: 1 },
  statusBadge: { borderRadius: Radii.full, paddingHorizontal: Spacing.sm, paddingVertical: 2 },
  statusText: { ...Typography.caption, fontWeight: '700', textTransform: 'uppercase' },
  assetClass: { ...Typography.caption, color: Colors.textMuted, marginBottom: Spacing.sm },
  cardFooter: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: Spacing.sm },
  amount: { ...Typography.body, color: Colors.blueprint, fontWeight: '700' },
  returnRate: { ...Typography.bodySmall, color: Colors.success },
  empty: { alignItems: 'center', paddingTop: Spacing.xxl, gap: Spacing.md },
  emptyText: { ...Typography.body, color: Colors.textMuted },
});
