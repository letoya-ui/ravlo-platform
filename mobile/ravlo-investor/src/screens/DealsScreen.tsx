import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
  View, Text, FlatList, StyleSheet, TouchableOpacity,
  RefreshControl, ActivityIndicator, ScrollView,
  Modal, TextInput, KeyboardAvoidingView, Platform, Pressable,
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
  submitted_for_funding: boolean;
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

const STATUS_FILTERS = ['All', 'active', 'funded', 'pending', 'closed'];

export default function DealsScreen({ navigation }: any) {
  const [deals, setDeals] = useState<Deal[]>([]);
  const [activeFilter, setActiveFilter] = useState('All');
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [searchVisible, setSearchVisible] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [activeSearch, setActiveSearch] = useState('');
  const searchInputRef = useRef<TextInput>(null);

  const fetchDeals = useCallback(async (p = 1, status = activeFilter, reset = false, q = activeSearch) => {
    try {
      const res = await api.get('/mobile/investor/deals', {
        params: { page: p, status: status === 'All' ? '' : status, q: q || undefined },
      });
      const newDeals = res.data.deals || [];
      setDeals(prev => (reset || p === 1) ? newDeals : [...prev, ...newDeals]);
      setTotal(res.data.total || 0);
      setPage(p);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [activeFilter, activeSearch]);

  useEffect(() => { fetchDeals(1, activeFilter, true, activeSearch); }, [activeFilter, activeSearch]);

  const submitSearch = () => {
    setActiveSearch(searchText.trim());
    setSearchVisible(false);
  };

  const clearSearch = () => {
    setSearchText('');
    setActiveSearch('');
    setSearchVisible(false);
  };

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchDeals(1, activeFilter, true);
    setRefreshing(false);
  }, [fetchDeals, activeFilter]);

  const onEndReached = () => {
    if (!loading && deals.length < total) fetchDeals(page + 1, activeFilter, false, activeSearch);
  };

  const fmt = (val: number) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', notation: 'compact', maximumFractionDigits: 1 }).format(val);

  const stratLabel = (s: string) =>
    (s || '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

  const scoreColor = (score: number | null) => {
    if (!score) return Colors.steel;
    if (score >= 80) return Colors.success;
    if (score >= 60) return Colors.warning;
    return Colors.danger;
  };

  if (loading && deals.length === 0) {
    return (
      <SafeAreaView style={styles.container}>
        <ActivityIndicator color={Colors.blueprint} style={{ flex: 1 }} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <View>
          <Text style={styles.title}>My Deals</Text>
          <Text style={styles.subtitle}>
            {activeSearch ? `${total} result${total !== 1 ? 's' : ''} for "${activeSearch}"` : `${total} total`}
          </Text>
        </View>
        <TouchableOpacity style={[styles.searchBtn, activeSearch ? styles.searchBtnActive : null]} onPress={() => { setSearchText(activeSearch); setSearchVisible(true); }}>
          <Ionicons name={activeSearch ? 'search' : 'search-outline'} size={20} color={activeSearch ? Colors.white : Colors.textMuted} />
        </TouchableOpacity>
      </View>

      <Modal visible={searchVisible} transparent animationType="fade" onRequestClose={() => setSearchVisible(false)}>
        <Pressable style={styles.overlay} onPress={() => setSearchVisible(false)}>
          <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={styles.searchModal}>
            <Pressable onPress={() => {}}>
              <Text style={styles.searchModalTitle}>Search Deals</Text>
              <View style={styles.searchInputRow}>
                <Ionicons name="search-outline" size={18} color={Colors.textMuted} style={{ marginRight: 8 }} />
                <TextInput
                  ref={searchInputRef}
                  style={styles.searchInput}
                  placeholder="Title, address, city, state…"
                  placeholderTextColor={Colors.textMuted}
                  value={searchText}
                  onChangeText={setSearchText}
                  onSubmitEditing={submitSearch}
                  returnKeyType="search"
                  autoFocus
                  autoCapitalize="none"
                />
                {searchText.length > 0 && (
                  <TouchableOpacity onPress={() => setSearchText('')}>
                    <Ionicons name="close-circle" size={18} color={Colors.textMuted} />
                  </TouchableOpacity>
                )}
              </View>
              <View style={styles.searchActions}>
                <TouchableOpacity style={styles.searchClearBtn} onPress={clearSearch}>
                  <Text style={styles.searchClearText}>Clear</Text>
                </TouchableOpacity>
                <TouchableOpacity style={styles.searchSubmitBtn} onPress={submitSearch}>
                  <Text style={styles.searchSubmitText}>Search</Text>
                </TouchableOpacity>
              </View>
            </Pressable>
          </KeyboardAvoidingView>
        </Pressable>
      </Modal>

      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.filterScroll} contentContainerStyle={styles.filterRow}>
        {STATUS_FILTERS.map(s => (
          <TouchableOpacity
            key={s}
            style={[styles.chip, activeFilter === s && styles.chipActive]}
            onPress={() => setActiveFilter(s)}
          >
            <Text style={[styles.chipText, activeFilter === s && styles.chipTextActive]}>
              {s === 'All' ? 'All' : s.charAt(0).toUpperCase() + s.slice(1)}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      <FlatList
        data={deals}
        keyExtractor={d => String(d.id)}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.blueprint} />}
        onEndReached={onEndReached}
        onEndReachedThreshold={0.2}
        ListFooterComponent={loading && !refreshing ? <ActivityIndicator color={Colors.blueprint} style={{ margin: 16 }} /> : null}
        contentContainerStyle={styles.list}
        ListEmptyComponent={
          <View style={styles.empty}>
            <Ionicons name="layers-outline" size={48} color={Colors.textMuted} />
            <Text style={styles.emptyText}>No deals yet</Text>
          </View>
        }
        renderItem={({ item }) => {
          const stratColor = STRATEGY_COLORS[item.strategy] || Colors.blueprint;
          const statusColor = STATUS_COLORS[item.status] || Colors.steel;
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
                  <Ionicons name={STRATEGY_ICONS[item.strategy] || 'home-outline'} size={18} color={stratColor} />
                </View>
                <View style={styles.cardInfo}>
                  <Text style={styles.cardTitle} numberOfLines={1}>{item.title || item.address || 'Untitled Deal'}</Text>
                  {location ? <Text style={styles.cardLocation}>{location}</Text> : null}
                  <View style={styles.badgeRow}>
                    {item.strategy ? (
                      <View style={[styles.badge, { backgroundColor: stratColor + '22', borderColor: stratColor + '55' }]}>
                        <Text style={[styles.badgeText, { color: stratColor }]}>{stratLabel(item.strategy)}</Text>
                      </View>
                    ) : null}
                    <View style={[styles.badge, { backgroundColor: statusColor + '22', borderColor: statusColor + '55' }]}>
                      <Text style={[styles.badgeText, { color: statusColor }]}>{item.status}</Text>
                    </View>
                    {item.submitted_for_funding && (
                      <View style={[styles.badge, { backgroundColor: Colors.warning + '22', borderColor: Colors.warning + '55' }]}>
                        <Text style={[styles.badgeText, { color: Colors.warning }]}>Funded</Text>
                      </View>
                    )}
                  </View>
                </View>
                {item.deal_score !== null && (
                  <View style={[styles.scoreBox, { backgroundColor: sc + '22', borderColor: sc }]}>
                    <Text style={[styles.scoreText, { color: sc }]}>{item.deal_score}</Text>
                  </View>
                )}
              </View>

              <View style={styles.metrics}>
                <MetricItem label="Purchase" value={fmt(item.purchase_price)} />
                <MetricItem label="ARV" value={fmt(item.arv)} />
                <MetricItem
                  label="Profit"
                  value={`${item.estimated_profit >= 0 ? '+' : ''}${fmt(item.estimated_profit)}`}
                  color={item.estimated_profit >= 0 ? Colors.success : Colors.danger}
                />
                <MetricItem
                  label="ROI"
                  value={`${item.roi_percent >= 0 ? '+' : ''}${item.roi_percent.toFixed(1)}%`}
                  color={item.roi_percent >= 0 ? Colors.success : Colors.danger}
                />
              </View>
            </TouchableOpacity>
          );
        }}
      />
    </SafeAreaView>
  );
}

function MetricItem({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <View style={styles.metric}>
      <Text style={styles.metricLabel}>{label}</Text>
      <Text style={[styles.metricValue, color ? { color } : {}]}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: Spacing.lg, paddingTop: Spacing.md, paddingBottom: Spacing.sm },
  title: { ...Typography.h2, color: Colors.textPrimary },
  subtitle: { ...Typography.bodySmall, color: Colors.textMuted },
  filterScroll: { flexGrow: 0 },
  filterRow: { paddingHorizontal: Spacing.lg, paddingBottom: Spacing.sm, gap: Spacing.sm },
  chip: { paddingHorizontal: Spacing.md, paddingVertical: 6, borderRadius: Radii.full, borderWidth: 1, borderColor: Colors.border, backgroundColor: Colors.surface },
  chipActive: { backgroundColor: Colors.blueprint, borderColor: Colors.blueprint },
  chipText: { ...Typography.caption, color: Colors.textMuted, fontWeight: '600' },
  chipTextActive: { color: Colors.white },
  list: { paddingHorizontal: Spacing.lg, paddingBottom: Spacing.xl },
  card: { backgroundColor: Colors.surface, borderRadius: Radii.md, padding: Spacing.md, marginBottom: Spacing.sm, borderWidth: 1, borderColor: Colors.border },
  cardTop: { flexDirection: 'row', alignItems: 'flex-start', gap: Spacing.sm, marginBottom: Spacing.sm },
  stratIcon: { width: 38, height: 38, borderRadius: Radii.sm, alignItems: 'center', justifyContent: 'center' },
  cardInfo: { flex: 1, minWidth: 0 },
  cardTitle: { ...Typography.bodySmall, color: Colors.textPrimary, fontWeight: '600' },
  cardLocation: { ...Typography.caption, color: Colors.textMuted, marginTop: 2 },
  badgeRow: { flexDirection: 'row', gap: 4, marginTop: 5, flexWrap: 'wrap' },
  badge: { borderWidth: 1, borderRadius: Radii.full, paddingHorizontal: 7, paddingVertical: 2 },
  badgeText: { fontSize: 9, fontWeight: '700', textTransform: 'uppercase' },
  scoreBox: { width: 38, height: 38, borderRadius: Radii.sm, borderWidth: 1.5, alignItems: 'center', justifyContent: 'center' },
  scoreText: { fontSize: 13, fontWeight: '800' },
  metrics: { flexDirection: 'row', justifyContent: 'space-between', paddingTop: Spacing.sm, borderTopWidth: 1, borderTopColor: Colors.border },
  metric: { alignItems: 'center' },
  metricLabel: { fontSize: 10, color: Colors.textMuted },
  metricValue: { ...Typography.caption, color: Colors.textPrimary, fontWeight: '700', marginTop: 2 },
  empty: { alignItems: 'center', paddingTop: 80, gap: Spacing.md },
  emptyText: { ...Typography.body, color: Colors.textMuted },
  searchBtn: { width: 38, height: 38, borderRadius: Radii.sm, borderWidth: 1, borderColor: Colors.border, backgroundColor: Colors.surface, alignItems: 'center', justifyContent: 'center' },
  searchBtnActive: { backgroundColor: Colors.blueprint, borderColor: Colors.blueprint },
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.6)', justifyContent: 'flex-start', paddingTop: 80 },
  searchModal: { marginHorizontal: Spacing.lg, backgroundColor: Colors.surfaceElevated, borderRadius: Radii.lg, padding: Spacing.lg, borderWidth: 1, borderColor: Colors.border },
  searchModalTitle: { ...Typography.h3, color: Colors.textPrimary, marginBottom: Spacing.md },
  searchInputRow: { flexDirection: 'row', alignItems: 'center', backgroundColor: Colors.surface, borderRadius: Radii.sm, borderWidth: 1, borderColor: Colors.border, paddingHorizontal: Spacing.md, paddingVertical: 10, marginBottom: Spacing.md },
  searchInput: { flex: 1, color: Colors.textPrimary, fontSize: 15 },
  searchActions: { flexDirection: 'row', gap: Spacing.sm },
  searchClearBtn: { flex: 1, paddingVertical: 10, borderRadius: Radii.sm, borderWidth: 1, borderColor: Colors.border, alignItems: 'center' },
  searchClearText: { ...Typography.label, color: Colors.textMuted },
  searchSubmitBtn: { flex: 2, paddingVertical: 10, borderRadius: Radii.sm, backgroundColor: Colors.blueprint, alignItems: 'center' },
  searchSubmitText: { ...Typography.label, color: Colors.white },
});
