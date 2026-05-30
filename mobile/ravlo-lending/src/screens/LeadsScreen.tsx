import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
  View, Text, StyleSheet, FlatList, TextInput,
  TouchableOpacity, RefreshControl, ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radii, Typography } from '../theme';
import { useAuthStore } from '../store/authStore';
import { api } from '../services/api';

const STATUSES = ['All', 'New', 'Contacted', 'Active', 'Pending', 'Closed'];

const STATUS_COLORS: Record<string, string> = {
  New: Colors.info,
  Contacted: Colors.softGlow,
  Active: Colors.success,
  Pending: Colors.warning,
  Qualified: Colors.blueprint,
  Closed: Colors.steel,
  Unqualified: Colors.danger,
};

function relativeDate(dateStr: string) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
  return d.toLocaleDateString();
}

interface Lead {
  id: number;
  name: string;
  email: string;
  phone: string;
  status: string;
  created_at: string;
}

export default function LeadsScreen({ navigation }: any) {
  const { token } = useAuthStore();
  const [leads, setLeads] = useState<Lead[]>([]);
  const [search, setSearch] = useState('');
  const [activeStatus, setActiveStatus] = useState('All');
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchLeads = useCallback(async (p = 1, q = search, s = activeStatus, reset = false) => {
    setLoading(true);
    try {
      const res = await api.get('/mobile/lending/leads', {
        params: { page: p, search: q, status: s },
        headers: { Authorization: `Bearer ${token}` },
      });
      const newLeads = res.data.leads || [];
      setLeads(prev => (reset || p === 1) ? newLeads : [...prev, ...newLeads]);
      setTotal(res.data.total || 0);
      setPage(p);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [token, search, activeStatus]);

  useEffect(() => {
    fetchLeads(1, search, activeStatus, true);
  }, [activeStatus]);

  const onSearchChange = (text: string) => {
    setSearch(text);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => fetchLeads(1, text, activeStatus, true), 400);
  };

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchLeads(1, search, activeStatus, true);
    setRefreshing(false);
  }, [fetchLeads, search, activeStatus]);

  const onEndReached = () => {
    if (!loading && leads.length < total) {
      fetchLeads(page + 1, search, activeStatus, false);
    }
  };

  const initials = (name: string) =>
    name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Leads</Text>
        <Text style={styles.subtitle}>{total} total</Text>
      </View>

      <View style={styles.searchRow}>
        <Ionicons name="search-outline" size={16} color={Colors.textMuted} style={styles.searchIcon} />
        <TextInput
          style={styles.searchInput}
          placeholder="Search name, email, phone…"
          placeholderTextColor={Colors.textMuted}
          value={search}
          onChangeText={onSearchChange}
        />
      </View>

      <FlatList
        horizontal
        data={STATUSES}
        keyExtractor={s => s}
        showsHorizontalScrollIndicator={false}
        style={styles.filterList}
        contentContainerStyle={styles.filterContent}
        renderItem={({ item }) => (
          <TouchableOpacity
            style={[styles.filterChip, activeStatus === item && styles.filterChipActive]}
            onPress={() => setActiveStatus(item)}
          >
            <Text style={[styles.filterText, activeStatus === item && styles.filterTextActive]}>
              {item}
            </Text>
          </TouchableOpacity>
        )}
      />

      <FlatList
        data={leads}
        keyExtractor={l => String(l.id)}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.blueprint} />}
        onEndReached={onEndReached}
        onEndReachedThreshold={0.2}
        ListFooterComponent={loading && !refreshing ? <ActivityIndicator color={Colors.blueprint} style={{ margin: 16 }} /> : null}
        contentContainerStyle={styles.listContent}
        renderItem={({ item }) => {
          const color = STATUS_COLORS[item.status] || Colors.steel;
          return (
            <TouchableOpacity
              style={styles.card}
              onPress={() => navigation.navigate('LeadDetail', { leadId: item.id, name: item.name })}
              activeOpacity={0.75}
            >
              <View style={[styles.avatar, { backgroundColor: Colors.blueprint + '33' }]}>
                <Text style={styles.avatarText}>{initials(item.name || '?')}</Text>
              </View>
              <View style={styles.cardBody}>
                <Text style={styles.cardName}>{item.name}</Text>
                <Text style={styles.cardEmail} numberOfLines={1}>{item.email}</Text>
              </View>
              <View style={styles.cardRight}>
                <View style={[styles.statusBadge, { backgroundColor: color + '22', borderColor: color }]}>
                  <Text style={[styles.statusText, { color }]}>{item.status}</Text>
                </View>
                <Text style={styles.cardDate}>{relativeDate(item.created_at)}</Text>
              </View>
            </TouchableOpacity>
          );
        }}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: Spacing.lg, paddingTop: Spacing.md, paddingBottom: Spacing.sm },
  title: { ...Typography.h2, color: Colors.textPrimary },
  subtitle: { ...Typography.bodySmall, color: Colors.textMuted },
  searchRow: { flexDirection: 'row', alignItems: 'center', marginHorizontal: Spacing.lg, marginBottom: Spacing.sm, backgroundColor: Colors.surface, borderRadius: Radii.md, borderWidth: 1, borderColor: Colors.border, paddingHorizontal: Spacing.sm },
  searchIcon: { marginRight: Spacing.xs },
  searchInput: { flex: 1, height: 40, color: Colors.textPrimary, ...Typography.bodySmall },
  filterList: { maxHeight: 44 },
  filterContent: { paddingHorizontal: Spacing.lg, gap: Spacing.sm },
  filterChip: { paddingHorizontal: Spacing.md, paddingVertical: 6, borderRadius: Radii.full, backgroundColor: Colors.surface, borderWidth: 1, borderColor: Colors.border },
  filterChipActive: { backgroundColor: Colors.blueprint, borderColor: Colors.blueprint },
  filterText: { ...Typography.caption, color: Colors.textMuted },
  filterTextActive: { color: Colors.white, fontWeight: '600' },
  listContent: { paddingHorizontal: Spacing.lg, paddingTop: Spacing.sm, paddingBottom: Spacing.xl },
  card: { flexDirection: 'row', alignItems: 'center', backgroundColor: Colors.surface, borderRadius: Radii.md, padding: Spacing.md, marginBottom: Spacing.sm, borderWidth: 1, borderColor: Colors.border },
  avatar: { width: 42, height: 42, borderRadius: 21, alignItems: 'center', justifyContent: 'center', marginRight: Spacing.sm },
  avatarText: { ...Typography.label, color: Colors.blueprint },
  cardBody: { flex: 1, minWidth: 0 },
  cardName: { ...Typography.bodySmall, color: Colors.textPrimary, fontWeight: '600' },
  cardEmail: { ...Typography.caption, color: Colors.textMuted, marginTop: 2 },
  cardRight: { alignItems: 'flex-end', gap: 4 },
  statusBadge: { borderRadius: Radii.full, borderWidth: 1, paddingHorizontal: 8, paddingVertical: 2 },
  statusText: { fontSize: 10, fontWeight: '700' },
  cardDate: { ...Typography.caption, color: Colors.textMuted },
});
