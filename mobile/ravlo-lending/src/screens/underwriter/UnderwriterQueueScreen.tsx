import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  RefreshControl,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radii, Typography } from '../../theme';
import { api } from '../../services/api';

// ─── Types ────────────────────────────────────────────────────────────────────

interface QueueLoan {
  id: number;
  borrower_name: string;
  loan_amount: number;
  loan_type: string;
  milestone_stage: string;
  property_address: string;
  risk_score: number;
  risk_level: 'Low' | 'Medium' | 'High';
  ltv: number;
  dti: number;
  ai_summary: string;
  updated_at: string;
}

type SortKey = 'risk_score' | 'loan_amount' | 'updated_at';

// ─── Helpers ──────────────────────────────────────────────────────────────────

const formatCurrency = (val: number): string =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(val);

const formatDate = (iso: string): string => {
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
};

const riskScoreColor = (score: number): string => {
  if (score >= 7) return Colors.danger;
  if (score >= 4) return Colors.warning;
  return Colors.success;
};

const riskLevelColor = (level: string): string => {
  if (level === 'High') return Colors.danger;
  if (level === 'Medium') return Colors.warning;
  return Colors.success;
};

const sortLoans = (loans: QueueLoan[], key: SortKey): QueueLoan[] => {
  return [...loans].sort((a, b) => {
    if (key === 'risk_score') return b.risk_score - a.risk_score;
    if (key === 'loan_amount') return b.loan_amount - a.loan_amount;
    if (key === 'updated_at') return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
    return 0;
  });
};

// ─── Sort Chip ────────────────────────────────────────────────────────────────

interface SortChipProps {
  label: string;
  active: boolean;
  onPress: () => void;
}

function SortChip({ label, active, onPress }: SortChipProps) {
  return (
    <TouchableOpacity
      onPress={onPress}
      activeOpacity={0.75}
      style={[styles.sortChip, active && styles.sortChipActive]}
    >
      <Text style={[styles.sortChipText, active && styles.sortChipTextActive]}>{label}</Text>
    </TouchableOpacity>
  );
}

// ─── Loan Card ────────────────────────────────────────────────────────────────

interface LoanCardProps {
  loan: QueueLoan;
  onPress: () => void;
}

function LoanCard({ loan, onPress }: LoanCardProps) {
  const scoreColor = riskScoreColor(loan.risk_score);
  const levelColor = riskLevelColor(loan.risk_level);

  return (
    <TouchableOpacity onPress={onPress} activeOpacity={0.8} style={styles.card}>
      {/* Top row: borrower + risk score badge */}
      <View style={styles.cardTopRow}>
        <View style={styles.cardBorrowerBlock}>
          <Text style={styles.cardBorrowerName} numberOfLines={1}>{loan.borrower_name}</Text>
          <Text style={styles.cardAmount}>{formatCurrency(loan.loan_amount)}</Text>
        </View>
        <View style={[styles.riskScoreBadge, { backgroundColor: scoreColor + '22', borderColor: scoreColor }]}>
          <Text style={[styles.riskScoreText, { color: scoreColor }]}>{loan.risk_score}</Text>
          <Text style={[styles.riskScoreDenom, { color: scoreColor }]}>/10</Text>
        </View>
      </View>

      {/* Risk level + LTV/DTI pills row */}
      <View style={styles.pillRow}>
        <View style={[styles.riskLevelChip, { backgroundColor: levelColor + '1A', borderColor: levelColor }]}>
          <Text style={[styles.riskLevelText, { color: levelColor }]}>{loan.risk_level}</Text>
        </View>
        <View style={styles.metricPill}>
          <Text style={styles.metricPillLabel}>LTV</Text>
          <Text style={styles.metricPillValue}>{loan.ltv.toFixed(1)}%</Text>
        </View>
        <View style={styles.metricPill}>
          <Text style={styles.metricPillLabel}>DTI</Text>
          <Text style={styles.metricPillValue}>{loan.dti.toFixed(1)}%</Text>
        </View>
      </View>

      {/* Loan type + milestone */}
      <View style={styles.cardMetaRow}>
        <View style={styles.tagChip}>
          <Text style={styles.tagChipText}>{loan.loan_type}</Text>
        </View>
        <View style={[styles.tagChip, styles.tagChipBlue]}>
          <Text style={[styles.tagChipText, styles.tagChipTextBlue]}>{loan.milestone_stage.replace(/_/g, ' ')}</Text>
        </View>
      </View>

      {/* Address */}
      <Text style={styles.cardAddress} numberOfLines={1}>{loan.property_address}</Text>

      {/* AI summary snippet */}
      {!!loan.ai_summary && (
        <Text style={styles.cardAiSummary} numberOfLines={2}>{loan.ai_summary}</Text>
      )}

      {/* Footer: updated date */}
      <View style={styles.cardFooter}>
        <Ionicons name="time-outline" size={12} color={Colors.textMuted} />
        <Text style={styles.cardUpdated}> Updated {formatDate(loan.updated_at)}</Text>
      </View>
    </TouchableOpacity>
  );
}

// ─── Empty State ──────────────────────────────────────────────────────────────

function EmptyState() {
  return (
    <View style={styles.emptyState}>
      <Ionicons name="checkmark-circle-outline" size={56} color={Colors.textMuted} />
      <Text style={styles.emptyTitle}>Queue is clear</Text>
      <Text style={styles.emptySubtitle}>No loans are currently awaiting underwriting review.</Text>
    </View>
  );
}

// ─── Screen ───────────────────────────────────────────────────────────────────

export default function UnderwriterQueueScreen({ navigation }: any) {
  const [loans, setLoans] = useState<QueueLoan[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [sortKey, setSortKey] = useState<SortKey>('risk_score');

  const fetchQueue = useCallback(async () => {
    try {
      const res = await api.get('/mobile/lending/underwriter/queue');
      setLoans(res.data.loans ?? []);
    } catch (err: any) {
      Alert.alert('Error', err.response?.data?.error || 'Could not load UW queue.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchQueue(); }, [fetchQueue]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchQueue();
    setRefreshing(false);
  }, [fetchQueue]);

  const sortedLoans = sortLoans(loans, sortKey);

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
      {/* Header */}
      <View style={styles.header}>
        <View>
          <Text style={styles.headerTitle}>UW Queue</Text>
          <Text style={styles.headerCount}>
            {loans.length} loan{loans.length !== 1 ? 's' : ''} pending review
          </Text>
        </View>
        <View style={styles.headerIconWrap}>
          <Ionicons name="layers-outline" size={24} color={Colors.blueprint} />
        </View>
      </View>

      {/* Sort chips */}
      <View style={styles.sortBar}>
        <SortChip label="Risk Score" active={sortKey === 'risk_score'} onPress={() => setSortKey('risk_score')} />
        <SortChip label="Amount" active={sortKey === 'loan_amount'} onPress={() => setSortKey('loan_amount')} />
        <SortChip label="Updated" active={sortKey === 'updated_at'} onPress={() => setSortKey('updated_at')} />
      </View>

      {/* List */}
      <FlatList
        data={sortedLoans}
        keyExtractor={(item) => String(item.id)}
        contentContainerStyle={[styles.listContent, sortedLoans.length === 0 && styles.listContentEmpty]}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.blueprint} />
        }
        ListEmptyComponent={<EmptyState />}
        renderItem={({ item }) => (
          <LoanCard
            loan={item}
            onPress={() => navigation.navigate('UnderwriterLoanReview', { loanId: item.id })}
          />
        )}
        showsVerticalScrollIndicator={false}
      />
    </SafeAreaView>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  centered: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },

  // Header
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.md,
    paddingBottom: Spacing.sm,
  },
  headerTitle: {
    ...Typography.h2,
    color: Colors.textPrimary,
  },
  headerCount: {
    ...Typography.caption,
    color: Colors.textMuted,
    marginTop: 2,
  },
  headerIconWrap: {
    width: 44,
    height: 44,
    borderRadius: Radii.md,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },

  // Sort bar
  sortBar: {
    flexDirection: 'row',
    paddingHorizontal: Spacing.lg,
    paddingBottom: Spacing.md,
    gap: Spacing.sm,
  },
  sortChip: {
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.xs + 2,
    borderRadius: Radii.full,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  sortChipActive: {
    backgroundColor: Colors.blueprint + '33',
    borderColor: Colors.blueprint,
  },
  sortChipText: {
    ...Typography.caption,
    color: Colors.textMuted,
    fontWeight: '600',
  },
  sortChipTextActive: {
    color: Colors.blueprint,
  },

  // List
  listContent: {
    paddingHorizontal: Spacing.lg,
    paddingBottom: Spacing.xl,
  },
  listContentEmpty: {
    flexGrow: 1,
  },

  // Card
  card: {
    backgroundColor: Colors.surface,
    borderRadius: Radii.lg,
    borderWidth: 1,
    borderColor: Colors.border,
    padding: Spacing.md,
    marginBottom: Spacing.md,
  },
  cardTopRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: Spacing.sm,
  },
  cardBorrowerBlock: {
    flex: 1,
    marginRight: Spacing.sm,
  },
  cardBorrowerName: {
    ...Typography.h3,
    color: Colors.textPrimary,
    marginBottom: 2,
  },
  cardAmount: {
    ...Typography.body,
    color: Colors.textSecondary,
    fontWeight: '600',
  },

  // Risk score badge (circle-like)
  riskScoreBadge: {
    flexDirection: 'row',
    alignItems: 'baseline',
    borderRadius: Radii.md,
    borderWidth: 1.5,
    paddingHorizontal: Spacing.sm,
    paddingVertical: Spacing.xs,
    minWidth: 56,
    justifyContent: 'center',
  },
  riskScoreText: {
    fontSize: 20,
    fontWeight: '800',
    lineHeight: 24,
  },
  riskScoreDenom: {
    fontSize: 11,
    fontWeight: '600',
    lineHeight: 16,
  },

  // Pills row
  pillRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
    marginBottom: Spacing.sm,
  },
  riskLevelChip: {
    borderRadius: Radii.full,
    borderWidth: 1,
    paddingHorizontal: Spacing.sm,
    paddingVertical: 3,
  },
  riskLevelText: {
    ...Typography.caption,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  metricPill: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.surfaceElevated,
    borderRadius: Radii.full,
    borderWidth: 1,
    borderColor: Colors.border,
    paddingHorizontal: Spacing.sm,
    paddingVertical: 3,
    gap: 3,
  },
  metricPillLabel: {
    ...Typography.caption,
    color: Colors.textMuted,
    fontWeight: '700',
    letterSpacing: 0.4,
  },
  metricPillValue: {
    ...Typography.caption,
    color: Colors.textPrimary,
    fontWeight: '600',
  },

  // Tags
  cardMetaRow: {
    flexDirection: 'row',
    gap: Spacing.xs,
    marginBottom: Spacing.xs,
  },
  tagChip: {
    backgroundColor: Colors.surfaceElevated,
    borderRadius: Radii.sm,
    paddingHorizontal: Spacing.sm,
    paddingVertical: 3,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  tagChipBlue: {
    backgroundColor: Colors.blueprint + '1A',
    borderColor: Colors.blueprint + '55',
  },
  tagChipText: {
    ...Typography.caption,
    color: Colors.textSecondary,
    fontWeight: '600',
    textTransform: 'capitalize',
  },
  tagChipTextBlue: {
    color: Colors.blueprint,
  },

  // Address + summary
  cardAddress: {
    ...Typography.caption,
    color: Colors.textMuted,
    marginBottom: Spacing.xs,
  },
  cardAiSummary: {
    ...Typography.caption,
    color: Colors.textMuted,
    lineHeight: 18,
    marginBottom: Spacing.xs,
    fontStyle: 'italic',
  },

  // Footer
  cardFooter: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: Spacing.xs,
  },
  cardUpdated: {
    ...Typography.caption,
    color: Colors.textMuted,
  },

  // Empty state
  emptyState: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: Spacing.xxl,
    gap: Spacing.sm,
  },
  emptyTitle: {
    ...Typography.h3,
    color: Colors.textSecondary,
    marginTop: Spacing.sm,
  },
  emptySubtitle: {
    ...Typography.bodySmall,
    color: Colors.textMuted,
    textAlign: 'center',
    maxWidth: 260,
  },
});
