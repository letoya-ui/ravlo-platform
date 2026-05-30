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

interface Borrower {
  id: number;
  full_name: string;
  email: string;
  phone: string;
  loan_type: string;
  loan_amount: number;
  status: string;
  credit_score: number | null;
}

const STATUS_COLORS: Record<string, string> = {
  Active: Colors.success,
  Pending: Colors.warning,
  Closed: Colors.steel,
  Processing: Colors.info,
  'In Review': Colors.softGlow,
};

export default function BorrowersScreen({ navigation }: any) {
  const { token } = useAuthStore();
  const [borrowers, setBorrowers] = useState<Borrower[]>([]);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchBorrowers = useCallback(async (p = 1, q = search, reset = false) => {
    setLoading(true);
    try {
      const res = await api.get('/mobile/lending/borrowers', {
        params: { page: p, search: q },
        headers: { Authorization: `Bearer ${token}` },
      });
      const newItems = res.data.borrowers || [];
      setBorrowers(prev => (reset || p === 1) ? newItems : [...prev, ...newItems]);
      setTotal(res.data.total || 0);
      setPage(p);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [token, search]);

  useEffect(() => { fetchBorrowers(1, '', true); }, []);

  const onSearchChange = (text: string) => {
    setSearch(text);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => fetchBorrowers(1, text, true), 400);
  };

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchBorrowers(1, search, true);
    setRefreshing(false);
  }, [fetchBorrowers, search]);

  const onEndReached = () => {
    if (!loading && borrowers.length < total) fetchBorrowers(page + 1, search, false);
  };

  const initials = (name: string) =>
    (name || '?').split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Borrowers</Text>
        <Text style={styles.subtitle}>{total} total</Text>
      </View>

      <View style={styles.searchRow}>
        <Ionicons name="search-outline" size={16} color={Colors.textMuted} style={styles.searchIcon} />
        <TextInput
          style={styles.searchInput}
          placeholder="Search name or email…"
          placeholderTextColor={Colors.textMuted}
          value={search}
          onChangeText={onSearchChange}
        />
      </View>

      <FlatList
        data={borrowers}
        keyExtractor={b => String(b.id)}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.blueprint} />}
        onEndReached={onEndReached}
        onEndReachedThreshold={0.2}
        ListFooterComponent={loading && !refreshing ? <ActivityIndicator color={Colors.blueprint} style={{ margin: 16 }} /> : null}
        contentContainerStyle={styles.listContent}
        renderItem={({ item }) => {
          const color = STATUS_COLORS[item.status] || Colors.steel;
          return (
            <View style={styles.card}>
              <View style={[styles.avatar, { backgroundColor: Colors.success + '22' }]}>
                <Text style={styles.avatarText}>{initials(item.full_name)}</Text>
              </View>
              <View style={styles.cardBody}>
                <Text style={styles.cardName}>{item.full_name}</Text>
                <Text style={styles.cardEmail} numberOfLines={1}>{item.email}</Text>
                {item.loan_type ? (
                  <Text style={styles.loanType}>{item.loan_type}</Text>
                ) : null}
              </View>
              <View style={styles.cardRight}>
                {item.loan_amount > 0 ? (
                  <Text style={styles.amount}>
                    ${(item.loan_amount / 1000).toFixed(0)}k
                  </Text>
                ) : null}
                {item.status ? (
                  <View style={[styles.statusBadge, { backgroundColor: color + '22', borderColor: color }]}>
                    <Text style={[styles.statusText, { color }]}>{item.status}</Text>
                  </View>
                ) : null}
                {item.credit_score ? (
                  <Text style={styles.creditScore}>FICO {item.credit_score}</Text>
                ) : null}
              </View>
            </View>
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
  listContent: { paddingHorizontal: Spacing.lg, paddingBottom: Spacing.xl },
  card: { flexDirection: 'row', alignItems: 'center', backgroundColor: Colors.surface, borderRadius: Radii.md, padding: Spacing.md, marginBottom: Spacing.sm, borderWidth: 1, borderColor: Colors.border },
  avatar: { width: 42, height: 42, borderRadius: 21, alignItems: 'center', justifyContent: 'center', marginRight: Spacing.sm },
  avatarText: { ...Typography.label, color: Colors.success },
  cardBody: { flex: 1, minWidth: 0 },
  cardName: { ...Typography.bodySmall, color: Colors.textPrimary, fontWeight: '600' },
  cardEmail: { ...Typography.caption, color: Colors.textMuted, marginTop: 2 },
  loanType: { ...Typography.caption, color: Colors.blueprint, marginTop: 2 },
  cardRight: { alignItems: 'flex-end', gap: 4 },
  amount: { ...Typography.bodySmall, color: Colors.success, fontWeight: '700' },
  statusBadge: { borderRadius: Radii.full, borderWidth: 1, paddingHorizontal: 8, paddingVertical: 2 },
  statusText: { fontSize: 10, fontWeight: '700' },
  creditScore: { ...Typography.caption, color: Colors.textMuted },
});
