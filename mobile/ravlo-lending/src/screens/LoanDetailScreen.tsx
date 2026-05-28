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

interface Loan {
  id: number;
  borrower_name: string;
  loan_amount: number;
  loan_type: string;
  status: string;
  ltv: number;
  interest_rate: number;
  property_address: string;
  created_at: string;
  updated_at: string;
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

export default function LoanDetailScreen({ route, navigation }: any) {
  const { loanId } = route.params;
  const [loan, setLoan] = useState<Loan | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchLoan = useCallback(async () => {
    try {
      const res = await api.get(`/mobile/lending/loans/${loanId}`);
      setLoan(res.data.loan);
    } catch (err: any) {
      Alert.alert('Error', err.response?.data?.error || 'Could not load loan details.');
    } finally {
      setLoading(false);
    }
  }, [loanId]);

  useEffect(() => { fetchLoan(); }, [fetchLoan]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchLoan();
    setRefreshing(false);
  }, [fetchLoan]);

  const formatCurrency = (val: number) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(val);

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.centered}><ActivityIndicator size="large" color={Colors.blueprint} /></View>
      </SafeAreaView>
    );
  }

  if (!loan) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.centered}>
          <Text style={styles.errorText}>Loan not found.</Text>
        </View>
      </SafeAreaView>
    );
  }

  const statusColor = STATUS_COLORS[loan.status] || Colors.steel;

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.navBar}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Ionicons name="chevron-back" size={24} color={Colors.textPrimary} />
          <Text style={styles.backText}>Loans</Text>
        </TouchableOpacity>
      </View>
      <ScrollView
        contentContainerStyle={styles.scroll}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.blueprint} />}
      >
        <View style={styles.titleRow}>
          <Text style={styles.title}>{loan.borrower_name || 'Unknown Borrower'}</Text>
          <View style={[styles.statusBadge, { backgroundColor: statusColor + '22', borderColor: statusColor }]}>
            <Text style={[styles.statusText, { color: statusColor }]}>{loan.status.replace('_', ' ')}</Text>
          </View>
        </View>
        <Text style={styles.address}>{loan.property_address || 'No address on file'}</Text>

        <View style={styles.amountCard}>
          <Text style={styles.amountLabel}>Loan Amount</Text>
          <Text style={styles.amountValue}>{formatCurrency(loan.loan_amount)}</Text>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Loan Details</Text>
          <DetailRow label="Loan Type" value={loan.loan_type || '—'} />
          <DetailRow label="Interest Rate" value={loan.interest_rate ? `${loan.interest_rate.toFixed(3)}%` : '—'} />
          <DetailRow label="LTV" value={loan.ltv ? `${loan.ltv.toFixed(1)}%` : '—'} />
          <DetailRow label="Status" value={loan.status.replace('_', ' ')} />
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Timeline</Text>
          <DetailRow label="Created" value={loan.created_at ? new Date(loan.created_at).toLocaleDateString() : '—'} />
          <DetailRow label="Last Updated" value={loan.updated_at ? new Date(loan.updated_at).toLocaleDateString() : '—'} />
        </View>
      </ScrollView>

      <TouchableOpacity
        style={styles.fab}
        onPress={() =>
          navigation.navigate('DocumentUpload', {
            loanId: loan.id,
            loanNumber: loan.id,
          })
        }
        activeOpacity={0.85}
      >
        <Ionicons name="add" size={28} color={Colors.white} />
      </TouchableOpacity>
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
  scroll: { padding: Spacing.lg, paddingBottom: 100 },
  titleRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: Spacing.xs },
  title: { ...Typography.h2, color: Colors.textPrimary, flex: 1, marginRight: Spacing.sm },
  statusBadge: { borderWidth: 1, borderRadius: Radii.full, paddingHorizontal: Spacing.sm, paddingVertical: 3 },
  statusText: { ...Typography.caption, fontWeight: '700', textTransform: 'uppercase' },
  address: { ...Typography.bodySmall, color: Colors.textMuted, marginBottom: Spacing.lg },
  amountCard: {
    backgroundColor: Colors.blueprint + '22',
    borderRadius: Radii.md,
    padding: Spacing.lg,
    alignItems: 'center',
    marginBottom: Spacing.lg,
    borderWidth: 1,
    borderColor: Colors.blueprint,
  },
  amountLabel: { ...Typography.caption, color: Colors.textMuted, marginBottom: 4 },
  amountValue: { fontSize: 32, fontWeight: '800', color: Colors.blueprint },
  section: {
    backgroundColor: Colors.surface,
    borderRadius: Radii.md,
    padding: Spacing.md,
    marginBottom: Spacing.md,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  sectionTitle: { ...Typography.label, color: Colors.textMuted, marginBottom: Spacing.sm },
  detailRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: Spacing.xs },
  detailLabel: { ...Typography.bodySmall, color: Colors.textMuted },
  detailValue: { ...Typography.bodySmall, color: Colors.textPrimary, fontWeight: '600' },
  fab: {
    position: 'absolute',
    bottom: Spacing.xl,
    right: Spacing.lg,
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: Colors.blueprint,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 6,
    elevation: 8,
  },
});
