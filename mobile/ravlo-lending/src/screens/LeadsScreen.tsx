import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
  View, Text, StyleSheet, FlatList, TextInput,
  TouchableOpacity, RefreshControl, ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radii, Typography } from '../theme';
import { api } from '../services/api';

const STATUSES = ['All', 'New', 'Active', 'Contacted', 'Pending', 'Closed'];

const STATUS_COLORS: Record<string, string> = {
  New: Colors.info,
  Active: Colors.success,
  Contacted: Colors.softGlow,
  Pending: Colors.warning,
  Closed: Colors.steel,
  Lost: '#EF4444',
  Converted: Colors.success,
};

export default function LeadsScreen({ navigation }: any) {
  const [leads, setLeads] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('All');
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const timer = useRef<any>(null);

  const fetch = useCallback(async (p: number, s: string, st: string, replace: boolean) => {
    setLoading(true);
    try {
      const res = await api.get('/mobile/lending/leads', { params: { page: p, per_page: 25, search: s, status: st } });
      const { leads: newLeads, total: t, pages: pg } = res.data;
      setLeads(prev => replace ? newLeads : [...prev, ...newLeads]);
      setTotal(t); setPages(pg); setPage(p);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, []);

  useEffect(() => { fetch(1, '', 'All', true); }, [fetch]);

  const onSearch = (val: string) => {
    setSearch(val);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => fetch(1, val, status, true), 400);
  };

  const onStatus = (s: string) => {
    setStatus(s);
    fetch(1, search, s, true);
  };

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetch(1, search, status, true);
    setRefreshing(false);
  }, [fetch, search, status]);

  const loadMore = () => { if (!loading && page < pages) fetch(page + 1, search, status, false); };

  const fmtDate = (raw: string) => {
    if (!raw || raw === 'None') return '';
    try {
      const d = new Date(raw), now = new Date();
      const diff = Math.round((now.getTime() - d.getTime()) / 86400000);
      if (diff === 0) return 'Today';
      if (diff === 1) return 'Yesterday';
      if (diff < 7) return `${diff}d ago`;
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    } catch { return ''; }
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Leads</Text>
        <Text style={styles.count}>{total} total</Text>
      </View>

      <View style={styles.searchBar}>
        <Ionicons name="search-outline" size={18} color={Colors.textMuted} />
        <TextInput style={styles.searchInput} placeholder="Search leads…" placeholderTextColor={Colors.textMuted}
          value={search} onChangeText={onSearch} autoCapitalize="none" autoCorrect={false} />
        {search.length > 0 && <TouchableOpacity onPress={() => onSearch('')}><Ionicons name="close-circle" size={18} color={Colors.textMuted} /></TouchableOpacity>}
      </View>

      <FlatList horizontal data={STATUSES} keyExtractor={i => i} showsHorizontalScrollIndicator={false}
        style={styles.tabs} contentContainerStyle={{ gap: Spacing.sm, paddingHorizontal: Spacing.lg }}
        renderItem={({ item }) => (
          <TouchableOpacity style={[styles.tab, status === item && styles.tabActive]} onPress={() => onStatus(item)}>
            <Text style={[styles.tabText, status === item && styles.tabTextActive]}>{item}</Text>
          </TouchableOpacity>
        )}
      />

      <FlatList
        data={leads} keyExtractor={i => String(i.id)}
        contentContainerStyle={styles.list}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.blueprint} />}
        onEndReached={loadMore} onEndReachedThreshold={0.3}
        renderItem={({ item }) => {
          const color = STATUS_COLORS[item.status] || Colors.steel;
          const initials = (item.name || '?').split(' ').map((w: string) => w[0]).join('').toUpperCase().slice(0, 2);
          return (
            <TouchableOpacity style={styles.row} onPress={() => navigation.navigate('LeadDetail', { lead: item })} activeOpacity={0.75}>
              <View style={[styles.avatar, { backgroundColor: color + '33' }]}>
                <Text style={[styles.avatarText, { color }]}>{initials}</Text>
              </View>
              <View style={styles.rowContent}>
                <View style={styles.rowTop}>
                  <Text style={styles.name} numberOfLines={1}>{item.name || 'Unknown'}</Text>
                  <Text style={styles.dateText}>{fmtDate(item.updated_at)}</Text>
                </View>
                <Text style={styles.email} numberOfLines={1}>{item.email || item.phone || '—'}</Text>
                <View style={[styles.statusBadge, { backgroundColor: color + '22', borderColor: color }]}>
                  <Text style={[styles.statusText, { color }]}>{item.status}</Text>
                </View>
              </View>
              <Ionicons name="chevron-forward" size={16} color={Colors.textMuted} />
            </TouchableOpacity>
          );
        }}
        ListEmptyComponent={!loading ? (
          <View style={styles.empty}>
            <Ionicons name="people-outline" size={40} color={Colors.textMuted} />
            <Text style={styles.emptyText}>No leads found</Text>
          </View>
        ) : null}
        ListFooterComponent={loading && page > 1 ? <ActivityIndicator color={Colors.blueprint} style={{ margin: 16 }} /> : null}
      />
      {loading && page === 1 && (
        <View style={styles.loadingOverlay}><ActivityIndicator color={Colors.blueprint} size="large" /></View>
      )}
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
  tabs: { maxHeight: 40, marginBottom: Spacing.sm },
  tab: { paddingHorizontal: Spacing.md, paddingVertical: 6, borderRadius: Radii.full, backgroundColor: Colors.surface, borderWidth: 1, borderColor: Colors.border },
  tabActive: { backgroundColor: Colors.blueprint, borderColor: Colors.blueprint },
  tabText: { ...Typography.caption, color: Colors.textMuted, fontWeight: '600' },
  tabTextActive: { color: '#fff' },
  list: { paddingHorizontal: Spacing.lg, paddingBottom: 100, gap: Spacing.sm },
  row: { flexDirection: 'row', gap: Spacing.md, backgroundColor: Colors.surface, borderRadius: Radii.md, borderWidth: 1, borderColor: Colors.border, padding: Spacing.md, alignItems: 'center' },
  avatar: { width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center' },
  avatarText: { fontWeight: '700', fontSize: 16 },
  rowContent: { flex: 1, gap: 3 },
  rowTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  name: { ...Typography.body, color: Colors.textPrimary, fontWeight: '600', flex: 1 },
  email: { ...Typography.caption, color: Colors.textMuted },
  dateText: { ...Typography.caption, color: Colors.textMuted, fontSize: 10 },
  statusBadge: { alignSelf: 'flex-start', borderRadius: Radii.full, borderWidth: 1, paddingHorizontal: 6, paddingVertical: 2, marginTop: 2 },
  statusText: { fontSize: 10, fontWeight: '600' },
  empty: { alignItems: 'center', justifyContent: 'center', paddingVertical: 60, gap: Spacing.sm },
  emptyText: { ...Typography.body, color: Colors.textMuted },
  loadingOverlay: { ...StyleSheet.absoluteFillObject, alignItems: 'center', justifyContent: 'center', backgroundColor: Colors.background + 'CC' },
});
