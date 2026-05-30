import React, { useEffect, useState, useCallback, useRef } from 'react';
import { View, Text, StyleSheet, FlatList, TextInput, TouchableOpacity, RefreshControl, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radii, Typography } from '../theme';
import { api } from '../services/api';

const STATUS_COLORS: Record<string, string> = {
  approved: Colors.success, processing: Colors.info, submitted: Colors.softGlow,
  underwriting: Colors.warning, funded: Colors.success, denied: '#EF4444', closed: Colors.steel,
};

export default function BorrowersScreen({ navigation }: any) {
  const [borrowers, setBorrowers] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const timer = useRef<any>(null);

  const fetch = useCallback(async (p: number, s: string, replace: boolean) => {
    setLoading(true);
    try {
      const res = await api.get('/mobile/lending/borrowers', { params: { page: p, per_page: 25, search: s } });
      const { borrowers: items, total: t, pages: pg } = res.data;
      setBorrowers(prev => replace ? items : [...prev, ...items]);
      setTotal(t); setPages(pg); setPage(p);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, []);

  useEffect(() => { fetch(1, '', true); }, [fetch]);

  const onSearch = (val: string) => {
    setSearch(val);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => fetch(1, val, true), 400);
  };

  const onRefresh = useCallback(async () => {
    setRefreshing(true); await fetch(1, search, true); setRefreshing(false);
  }, [fetch, search]);

  const fmt = (n: number) => n > 0 ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', notation: 'compact', maximumFractionDigits: 1 }).format(n) : '—';

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Borrowers</Text>
        <Text style={styles.count}>{total} total</Text>
      </View>
      <View style={styles.searchBar}>
        <Ionicons name="search-outline" size={18} color={Colors.textMuted} />
        <TextInput style={styles.searchInput} placeholder="Search borrowers…" placeholderTextColor={Colors.textMuted}
          value={search} onChangeText={onSearch} autoCapitalize="none" autoCorrect={false} />
        {search.length > 0 && <TouchableOpacity onPress={() => onSearch('')}><Ionicons name="close-circle" size={18} color={Colors.textMuted} /></TouchableOpacity>}
      </View>
      <FlatList
        data={borrowers} keyExtractor={i => String(i.id)}
        contentContainerStyle={styles.list}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.blueprint} />}
        onEndReached={() => { if (!loading && page < pages) fetch(page + 1, search, false); }}
        onEndReachedThreshold={0.3}
        renderItem={({ item }) => {
          const statusColor = STATUS_COLORS[item.loan_status?.toLowerCase()] || Colors.steel;
          const initials = (item.full_name || '?').split(' ').map((w: string) => w[0]).join('').toUpperCase().slice(0, 2);
          return (
            <View style={styles.row}>
              <View style={[styles.avatar, { backgroundColor: Colors.blueprint + '33' }]}>
                <Text style={[styles.avatarText, { color: Colors.blueprint }]}>{initials}</Text>
              </View>
              <View style={styles.rowContent}>
                <Text style={styles.name} numberOfLines={1}>{item.full_name}</Text>
                <Text style={styles.email} numberOfLines={1}>{item.email || '—'}</Text>
                <View style={styles.metaRow}>
                  {item.loan_amount > 0 && <Text style={styles.amount}>{fmt(item.loan_amount)}</Text>}
                  {item.loan_status ? (
                    <View style={[styles.statusBadge, { backgroundColor: statusColor + '22', borderColor: statusColor }]}>
                      <Text style={[styles.statusText, { color: statusColor }]}>{item.loan_status}</Text>
                    </View>
                  ) : null}
                </View>
              </View>
            </View>
          );
        }}
        ListEmptyComponent={!loading ? (
          <View style={styles.empty}>
            <Ionicons name="person-outline" size={40} color={Colors.textMuted} />
            <Text style={styles.emptyText}>No borrowers found</Text>
          </View>
        ) : null}
        ListFooterComponent={loading && page > 1 ? <ActivityIndicator color={Colors.blueprint} style={{ margin: 16 }} /> : null}
      />
      {loading && page === 1 && <View style={styles.loadingOverlay}><ActivityIndicator color={Colors.blueprint} size="large" /></View>}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline', paddingHorizontal: Spacing.lg, paddingTop: Spacing.md, paddingBottom: Spacing.sm },
  title: { ...Typography.h2, color: Colors.textPrimary },
  count: { ...Typography.caption, color: Colors.textMuted },
  searchBar: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm, marginHorizontal: Spacing.lg, marginBottom: Spacing.sm, backgroundColor: Colors.surface, borderWidth: 1, borderColor: Colors.border, borderRadius: Radii.md, paddingHorizontal: Spacing.md, paddingVertical: Spacing.sm },
  searchInput: { flex: 1, ...Typography.body, color: Colors.textPrimary, padding: 0 } as any,
  list: { paddingHorizontal: Spacing.lg, paddingBottom: 100, gap: Spacing.sm },
  row: { flexDirection: 'row', gap: Spacing.md, backgroundColor: Colors.surface, borderRadius: Radii.md, borderWidth: 1, borderColor: Colors.border, padding: Spacing.md, alignItems: 'flex-start' },
  avatar: { width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center' },
  avatarText: { fontWeight: '700', fontSize: 16 },
  rowContent: { flex: 1, gap: 3 },
  name: { ...Typography.body, color: Colors.textPrimary, fontWeight: '600' },
  email: { ...Typography.caption, color: Colors.textMuted },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm, marginTop: 2 },
  amount: { ...Typography.caption, color: Colors.success, fontWeight: '700' },
  statusBadge: { borderRadius: Radii.full, borderWidth: 1, paddingHorizontal: 6, paddingVertical: 2 },
  statusText: { fontSize: 10, fontWeight: '600', textTransform: 'capitalize' },
  empty: { alignItems: 'center', justifyContent: 'center', paddingVertical: 60, gap: Spacing.sm },
  emptyText: { ...Typography.body, color: Colors.textMuted },
  loadingOverlay: { ...StyleSheet.absoluteFillObject, alignItems: 'center', justifyContent: 'center', backgroundColor: Colors.background + 'CC' },
});
