import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  RefreshControl,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Radii, Spacing, Typography } from '../../theme';
import { api } from '../../services/api';

// ─── Types ────────────────────────────────────────────────────────────────────

type LoanStatus = 'Processing' | 'Submitted' | 'In Review';
type RiskLevel = 'Low' | 'Medium' | 'High';

interface QueueLoan {
  id: number;
  borrower_name: string;
  loan_amount: number;
  loan_type: string;
  status: LoanStatus;
  milestone_stage: string;
  progress_percent: number;
  risk_level: RiskLevel;
  property_address: string;
  updated_at: string;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const FILTER_OPTIONS = ['All', 'Processing', 'Submitted', 'In Review'] as const;
type FilterOption = (typeof FILTER_OPTIONS)[number];

const STATUS_COLORS: Record<string, string> = {
  Processing: Colors.info,
  Submitted:  Colors.blueprint,
  'In Review': Colors.warning,
};

const RISK_COLORS: Record<RiskLevel, string> = {
  Low:    Colors.success,
  Medium: Colors.warning,
  High:   Colors.danger,
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatCurrency(amount: number): string {
  if (amount >= 1_000_000) return `$${(amount / 1_000_000).toFixed(2)}M`;
  if (amount >= 1_000)    return `$${(amount / 1_000).toFixed(0)}K`;
  return `$${amount}`;
}

function relativeDate(dateStr: string): string {
  if (!dateStr) return '';
  const diff = (Date.now() - new Date(dateStr).getTime()) / 1000;
  if (diff < 60)     return 'just now';
  if (diff < 3600)   return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400)  return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
  return new Date(dateStr).toLocaleDateString();
}

// ─── Sub-components ───────────────────────────────────────────────────────────

interface ProgressBarProps {
  percent: number;
}

function ProgressBar({ percent }: ProgressBarProps) {
  const clamped = Math.max(0, Math.min(100, percent));
  return (
    <View style={progressStyles.track}>
      <View style={[progressStyles.fill, { width: `${clamped}%` as any }]} />
    </View>
  );
}

const progressStyles = StyleSheet.create({
  track: {
    height: 4,
    backgroundColor: Colors.border,
    borderRadius: Radii.full,
    overflow: 'hidden',
    flex: 1,
  },
  fill: {
    height: '100%',
    backgroundColor: Colors.blueprint,
    borderRadius: Radii.full,
  },
});

// ─── Loan Card ────────────────────────────────────────────────────────────────

interface LoanCardProps {
  loan: QueueLoan;
  onPress: () => void;
}

function LoanCard({ loan, onPress }: LoanCardProps) {
  const statusColor = STATUS_COLORS[loan.status] ?? Colors.steel;
  const riskColor   = RISK_COLORS[loan.risk_level] ?? Colors.steel;

  return (
    <TouchableOpacity style={cardStyles.card} onPress={onPress} activeOpacity={0.75}>
      {/* Row 1 — borrower + amount */}
      <View style={cardStyles.row}>
        <Text style={cardStyles.borrowerName} numberOfLines={1}>
          {loan.borrower_name}
        </Text>
        <Text style={cardStyles.loanAmount}>{formatCurrency(loan.loan_amount)}</Text>
      </View>

      {/* Row 2 — loan type + status badge */}
      <View style={[cardStyles.row, { marginTop: Spacing.xs }]}>
        <Text style={cardStyles.loanType}>{loan.loan_type}</Text>
        <View style={[cardStyles.badge, { backgroundColor: statusColor + '22', borderColor: statusColor }]}>
          <Text style={[cardStyles.badgeText, { color: statusColor }]}>{loan.status}</Text>
        </View>
      </View>

      {/* Divider */}
      <View style={cardStyles.divider} />

      {/* Row 3 — milestone + progress */}
      <View style={cardStyles.milestoneRow}>
        <Text style={cardStyles.milestoneLabel} numberOfLines={1}>
          {loan.milestone_stage}
        </Text>
        <Text style={cardStyles.progressPercent}>{loan.progress_percent}%</Text>
      </View>
      <View style={{ marginTop: Spacing.xs }}>
        <ProgressBar percent={loan.progress_percent} />
      </View>

      {/* Row 4 — risk chip + address + date */}
      <View style={[cardStyles.row, { marginTop: Spacing.sm }]}>
        <View style={[cardStyles.chip, { backgroundColor: riskColor + '22', borderColor: riskColor }]}>
          <Text style={[cardStyles.chipText, { color: riskColor }]}>{loan.risk_level} Risk</Text>
        </View>
        <View style={cardStyles.addressBlock}>
          <Ionicons name="location-outline" size={12} color={Colors.textMuted} />
          <Text style={cardStyles.addressText} numberOfLines={1}>
            {loan.property_address}
          </Text>
        </View>
        <Text style={cardStyles.dateText}>{relativeDate(loan.updated_at)}</Text>
      </View>
    </TouchableOpacity>
  );
}

const cardStyles = StyleSheet.create({
  card: {
    backgroundColor: Colors.surface,
    borderRadius: Radii.md,
    borderWidth: 1,
    borderColor: Colors.border,
    padding: Spacing.md,
    marginBottom: Spacing.sm,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  borrowerName: {
    ...Typography.bodySmall,
    color: Colors.textPrimary,
    fontWeight: '600',
    flex: 1,
    marginRight: Spacing.sm,
  },
  loanAmount: {
    ...Typography.bodySmall,
    color: Colors.textPrimary,
    fontWeight: '700',
  },
  loanType: {
    ...Typography.caption,
    color: Colors.textSecondary,
  },
  badge: {
    borderRadius: Radii.full,
    borderWidth: 1,
    paddingHorizontal: Spacing.sm,
    paddingVertical: 2,
  },
  badgeText: {
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 0.3,
  },
  divider: {
    height: 1,
    backgroundColor: Colors.border,
    marginVertical: Spacing.sm,
  },
  milestoneRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  milestoneLabel: {
    ...Typography.caption,
    color: Colors.textSecondary,
    flex: 1,
    marginRight: Spacing.sm,
  },
  progressPercent: {
    ...Typography.caption,
    color: Colors.blueprint,
    fontWeight: '700',
  },
  chip: {
    borderRadius: Radii.full,
    borderWidth: 1,
    paddingHorizontal: Spacing.sm,
    paddingVertical: 2,
  },
  chipText: {
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 0.3,
  },
  addressBlock: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
    marginHorizontal: Spacing.sm,
    gap: 3,
  },
  addressText: {
    ...Typography.caption,
    color: Colors.textMuted,
    flex: 1,
  },
  dateText: {
    ...Typography.caption,
    color: Colors.textMuted,
    flexShrink: 0,
  },
});

// ─── Empty State ──────────────────────────────────────────────────────────────

function EmptyState() {
  return (
    <View style={emptyStyles.container}>
      <Ionicons name="documents-outline" size={52} color={Colors.textMuted} />
      <Text style={emptyStyles.title}>No loans in queue</Text>
      <Text style={emptyStyles.subtitle}>
        Loans assigned to you will appear here.
      </Text>
    </View>
  );
}

const emptyStyles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: Spacing.xxl,
    gap: Spacing.sm,
  },
  title: {
    ...Typography.body,
    color: Colors.textSecondary,
    fontWeight: '600',
    marginTop: Spacing.sm,
  },
  subtitle: {
    ...Typography.bodySmall,
    color: Colors.textMuted,
    textAlign: 'center',
    paddingHorizontal: Spacing.xl,
  },
});

// ─── Screen ───────────────────────────────────────────────────────────────────

export default function ProcessorQueueScreen({ navigation }: any) {
  const [loans, setLoans]         = useState<QueueLoan[]>([]);
  const [filter, setFilter]       = useState<FilterOption>('All');
  const [loading, setLoading]     = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const fetchQueue = useCallback(async (reset = false) => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (filter !== 'All') params.status = filter;

      const res = await api.get('/mobile/lending/processor/queue', { params });
      const data: QueueLoan[] = res.data.loans ?? res.data ?? [];
      setLoans(reset ? data : data);
    } catch {
      // silent — network errors handled globally or via empty state
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    fetchQueue(true);
  }, [fetchQueue]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchQueue(true);
    setRefreshing(false);
  }, [fetchQueue]);

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <View>
          <Text style={styles.title}>Loan Queue</Text>
          <Text style={styles.subtitle}>{loans.length} loan{loans.length !== 1 ? 's' : ''}</Text>
        </View>
        <View style={styles.headerIcon}>
          <Ionicons name="layers-outline" size={22} color={Colors.blueprint} />
        </View>
      </View>

      {/* Filter chips */}
      <FlatList
        horizontal
        data={FILTER_OPTIONS as unknown as FilterOption[]}
        keyExtractor={f => f}
        showsHorizontalScrollIndicator={false}
        style={styles.filterList}
        contentContainerStyle={styles.filterContent}
        renderItem={({ item }) => (
          <TouchableOpacity
            style={[styles.filterChip, filter === item && styles.filterChipActive]}
            onPress={() => setFilter(item)}
          >
            <Text style={[styles.filterText, filter === item && styles.filterTextActive]}>
              {item}
            </Text>
          </TouchableOpacity>
        )}
      />

      {/* Loan list */}
      <FlatList
        data={loans}
        keyExtractor={l => String(l.id)}
        contentContainerStyle={[
          styles.listContent,
          loans.length === 0 && styles.listEmpty,
        ]}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor={Colors.blueprint}
          />
        }
        ListEmptyComponent={!loading ? <EmptyState /> : null}
        ListFooterComponent={
          loading && !refreshing
            ? <ActivityIndicator color={Colors.blueprint} style={styles.loader} />
            : null
        }
        renderItem={({ item }) => (
          <LoanCard
            loan={item}
            onPress={() =>
              navigation.navigate('ProcessorLoanDetail', { loanId: item.id })
            }
          />
        )}
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
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.md,
    paddingBottom: Spacing.sm,
  },
  title: {
    ...Typography.h2,
    color: Colors.textPrimary,
  },
  subtitle: {
    ...Typography.caption,
    color: Colors.textMuted,
    marginTop: 2,
  },
  headerIcon: {
    width: 42,
    height: 42,
    borderRadius: Radii.md,
    backgroundColor: Colors.surfaceElevated,
    borderWidth: 1,
    borderColor: Colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  filterList: {
    maxHeight: 44,
  },
  filterContent: {
    paddingHorizontal: Spacing.lg,
    gap: Spacing.sm,
  },
  filterChip: {
    paddingHorizontal: Spacing.md,
    paddingVertical: 6,
    borderRadius: Radii.full,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  filterChipActive: {
    backgroundColor: Colors.blueprint,
    borderColor: Colors.blueprint,
  },
  filterText: {
    ...Typography.caption,
    color: Colors.textMuted,
  },
  filterTextActive: {
    color: Colors.white,
    fontWeight: '600',
  },
  listContent: {
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.sm,
    paddingBottom: Spacing.xl,
  },
  listEmpty: {
    flexGrow: 1,
  },
  loader: {
    margin: Spacing.md,
  },
});
