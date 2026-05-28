import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  FlatList,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  RefreshControl,
  Alert,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radii, Typography } from '../theme';
import { api } from '../services/api';

interface Loan {
  id: number;
  borrower_name: string;
  loan_amount: number;
  loan_type: string;
  status: string;
  ltv: number;
  interest_rate: number;
  property_address: string;
}

const STATUS_COLORS: Record<string, string> = {
  submitted: Colors.info,
  processing: Colors.warning,
  underwriting: Colors.softGlow,
  approved: Colors.success,
  closed: Colors.steel,
  funded: Colors.success,
  denied: Colors.danger,
  cancelled: Colors.danger,
  in_review: Colors.info,
};

export default function LoanListScreen({ navigation }: any) {
  const [loans, setLoans] = useState<Loan[]>([]);
  const [filtered, setFiltered] = useState<Loan[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchLoans = useCallback(async () => {
    try {
      const res = await api.get('/mobile/lending/loans');
      setLoans(res.data.loans || []);
      setFiltered(res.data.loans || []);
    } catch (err: any) {
      Alert.alert('Error', err.response?.data?.error || 'Could not load loans.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchLoans(); }, [fetchLoans]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchLoans();
    setRefreshing(false);
  }, [fetchLoans]);

  const handleSearch = (text: string) => {
    setSearch(text);
    const q = text.toLowerCase();
    setFiltered(
      loans.filter(
        (l) =>
          l.borrower_name.toLowerCase().includes(q) ||
          l.property_address.toLowerCase().includes(q) ||
          l.status.toLowerCase().includes(q) ||
          l.loan_type.toLowerCase().includes(q)
      )
    );
  };

  const formatCurrency = (val: number) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', notation: 'compact', maximumFractionDigits: 1 }).format(val);

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.centered}>
          <ActivityIndicator size="large" color={Colors.blueprint} />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Loans</Text>
      </View>
      <View style={styles.searchContainer}>
        <Ionicons name="search-outline" size={18} color={Colors.textMuted} style={styles.searchIcon} />
        <TextInput
          style={styles.searchInput}
          value={search}
          onChangeText={handleSearch}
          placeholder="Search borrower, address, status…"
          placeholderTextColor={Colors.textMuted}
        />
      </View>
      <FlatList
        data={filtered}
        keyExtractor={(item) => String(item.id)}
        contentContainerStyle={styles.list}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.blueprint} />}
        ListEmptyComponent={
          <View style={styles.empty}>
            <Ionicons name="documents-outline" size={48} color={Colors.textMuted} />
            <Text style={styles.emptyText}>No loans found</Text>
          </View>
        }
        renderItem={({ item }) => (
          <TouchableOpacity
            style={styles.card}
            onPress={() => navigation.navigate('LoanDetail', { loanId: item.id })}
            activeOpacity={0.75}
          >
            <View style={styles.cardHeader}>
              <Text style={styles.borrowerName}>{item.borrower_name || 'Unknown Borrower'}</Text>
              <View style={[styles.statusBadge, { backgroundColor: (STATUS_COLORS[item.status] || Colors.steel) + '22' }]}>
                <Text style={[styles.statusText, { color: STATUS_COLORS[item.status] || Colors.steel }]}>
                  {item.status.replace('_', ' ')}
                </Text>
              </View>
            </View>
            <Text style={styles.address} numberOfLines={1}>{item.property_address || 'No address'}</Text>
            <View style={styles.cardFooter}>
              <Text style={styles.amount}>{formatCurrency(item.loan_amount)}</Text>
              <Text style={styles.meta}>{item.loan_type} · LTV {item.ltv.toFixed(1)}%</Text>
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
  searchContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.surface,
    marginHorizontal: Spacing.lg,
    borderRadius: Radii.md,
    borderWidth: 1,
    borderColor: Colors.border,
    paddingHorizontal: Spacing.sm,
    marginBottom: Spacing.md,
  },
  searchIcon: { marginRight: Spacing.xs },
  searchInput: { flex: 1, color: Colors.textPrimary, paddingVertical: Spacing.sm, fontSize: 15 },
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
  borrowerName: { ...Typography.body, color: Colors.textPrimary, fontWeight: '600', flex: 1 },
  statusBadge: { borderRadius: Radii.full, paddingHorizontal: Spacing.sm, paddingVertical: 2 },
  statusText: { ...Typography.caption, fontWeight: '700', textTransform: 'uppercase' },
  address: { ...Typography.bodySmall, color: Colors.textMuted, marginBottom: Spacing.sm },
  cardFooter: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  amount: { ...Typography.body, color: Colors.blueprint, fontWeight: '700' },
  meta: { ...Typography.bodySmall, color: Colors.textMuted },
  empty: { alignItems: 'center', paddingTop: Spacing.xxl, gap: Spacing.md },
  emptyText: { ...Typography.body, color: Colors.textMuted },
});
