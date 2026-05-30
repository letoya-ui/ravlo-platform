import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
  TouchableOpacity,
  Alert,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radii, Typography } from '../../theme';
import { useAuthStore } from '../../store/authStore';
import { api } from '../../services/api';

interface BorrowerLoanSummary {
  id: number;
  amount: number;
  loan_type: string;
  status: string;
  milestone_stage: string;
  milestone_index: number;
  progress_percent: number;
  property_address: string;
  open_conditions: number;
}

interface BorrowerDashboard {
  loans: BorrowerLoanSummary[];
  total_loans: number;
  open_conditions: number;
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

function getTimeOfDay(): string {
  const h = new Date().getHours();
  if (h < 12) return 'morning';
  if (h < 17) return 'afternoon';
  return 'evening';
}

function formatCurrency(val: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(val);
}

export default function BorrowerDashboardScreen({ navigation }: any) {
  const { user } = useAuthStore();
  const [data, setData] = useState<BorrowerDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const res = await api.get('/mobile/lending/borrower/dashboard');
      setData(res.data);
    } catch (err: any) {
      // fall through — show empty/error state below
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchData();
    setRefreshing(false);
  }, [fetchData]);

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.centered}>
          <ActivityIndicator size="large" color={Colors.blueprint} />
        </View>
      </SafeAreaView>
    );
  }

  const loans = data?.loans ?? [];
  const hasLoans = loans.length > 0;

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView
        contentContainerStyle={styles.scroll}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor={Colors.blueprint}
          />
        }
        showsVerticalScrollIndicator={false}
      >
        {/* Header */}
        <View style={styles.header}>
          <View style={styles.headerLeft}>
            <Text style={styles.greeting}>Good {getTimeOfDay()},</Text>
            <Text style={styles.userName}>{user?.first_name || 'there'}</Text>
          </View>
          <View style={styles.roleBadge}>
            <Text style={styles.roleText}>Borrower</Text>
          </View>
        </View>

        {/* Loan section */}
        <Text style={styles.sectionTitle}>Your Loans</Text>

        {!hasLoans ? (
          <View style={styles.emptyState}>
            <View style={styles.emptyIcon}>
              <Ionicons name="home-outline" size={40} color={Colors.textMuted} />
            </View>
            <Text style={styles.emptyTitle}>No Active Loans</Text>
            <Text style={styles.emptySubtitle}>
              Start your homeownership journey today.
            </Text>
            <TouchableOpacity
              style={styles.prequalBtn}
              onPress={() => Alert.alert('Get Pre-Qualified', 'This feature is coming soon.')}
              activeOpacity={0.8}
            >
              <Ionicons name="checkmark-circle-outline" size={18} color={Colors.white} />
              <Text style={styles.prequalBtnText}>Get Pre-Qualified</Text>
            </TouchableOpacity>
          </View>
        ) : (
          <View style={styles.loanList}>
            {loans.map((loan) => (
              <LoanCard
                key={loan.id}
                loan={loan}
                onPress={() =>
                  navigation.navigate('BorrowerLoanDetail', { loanId: loan.id })
                }
              />
            ))}
          </View>
        )}

        {/* Quick Actions */}
        <Text style={styles.sectionTitle}>Quick Actions</Text>
        <View style={styles.quickRow}>
          <QuickActionCard
            icon="chatbubbles-outline"
            label="Need Help?"
            subtitle="Message your team"
            color={Colors.info}
            onPress={() => navigation.navigate('Messages')}
          />
          <QuickActionCard
            icon="cloud-upload-outline"
            label="Upload Docs"
            subtitle="Submit documents"
            color={Colors.blueprint}
            onPress={() =>
              navigation.navigate('DocumentUpload', {
                loanId: loans[0]?.id,
                loanNumber: loans[0]?.id,
              })
            }
          />
          <QuickActionCard
            icon="person-outline"
            label="Contact Your LO"
            subtitle="Talk to your officer"
            color={Colors.success}
            onPress={() => navigation.navigate('Messages')}
          />
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

function LoanCard({
  loan,
  onPress,
}: {
  loan: BorrowerLoanSummary;
  onPress: () => void;
}) {
  const statusColor = STATUS_COLORS[loan.status] || Colors.steel;
  const statusLabel = (loan.status || '').replace(/_/g, ' ');
  const progress = Math.min(Math.max(loan.progress_percent ?? 0, 0), 100);

  return (
    <TouchableOpacity
      style={styles.loanCard}
      onPress={onPress}
      activeOpacity={0.8}
    >
      {/* Address + status */}
      <View style={styles.loanCardHeader}>
        <Text style={styles.loanAddress} numberOfLines={1}>
          {loan.property_address || 'Property Address'}
        </Text>
        <View
          style={[
            styles.statusBadge,
            { backgroundColor: statusColor + '22', borderColor: statusColor },
          ]}
        >
          <Text style={[styles.statusText, { color: statusColor }]}>
            {statusLabel}
          </Text>
        </View>
      </View>

      {/* Amount + type */}
      <View style={styles.loanMeta}>
        <Text style={styles.loanAmount}>{formatCurrency(loan.amount)}</Text>
        <Text style={styles.loanType}>{loan.loan_type || '—'}</Text>
      </View>

      {/* Progress bar */}
      <View style={styles.progressSection}>
        <View style={styles.progressLabelRow}>
          <Text style={styles.progressLabel}>{loan.milestone_stage || 'In Progress'}</Text>
          <Text style={styles.progressPct}>{progress.toFixed(0)}%</Text>
        </View>
        <View style={styles.progressTrack}>
          <View
            style={[styles.progressFill, { width: `${progress}%` as any }]}
          />
        </View>
      </View>

      {/* Conditions warning */}
      {(loan.open_conditions ?? 0) > 0 && (
        <View style={styles.conditionsBanner}>
          <Ionicons name="warning-outline" size={14} color={Colors.warning} />
          <Text style={styles.conditionsBannerText}>
            {loan.open_conditions} condition{loan.open_conditions !== 1 ? 's' : ''} need attention
          </Text>
        </View>
      )}

      {/* Tap hint */}
      <View style={styles.loanCardFooter}>
        <Text style={styles.viewDetails}>View Details</Text>
        <Ionicons name="chevron-forward" size={14} color={Colors.textMuted} />
      </View>
    </TouchableOpacity>
  );
}

function QuickActionCard({
  icon,
  label,
  subtitle,
  color,
  onPress,
}: {
  icon: any;
  label: string;
  subtitle: string;
  color: string;
  onPress: () => void;
}) {
  return (
    <TouchableOpacity style={styles.quickCard} onPress={onPress} activeOpacity={0.75}>
      <View style={[styles.quickIcon, { backgroundColor: color + '22' }]}>
        <Ionicons name={icon} size={22} color={color} />
      </View>
      <Text style={styles.quickLabel}>{label}</Text>
      <Text style={styles.quickSubtitle}>{subtitle}</Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  scroll: { padding: Spacing.lg, paddingBottom: Spacing.xxl },

  // Header
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: Spacing.lg,
  },
  headerLeft: { flex: 1 },
  greeting: { ...Typography.bodySmall, color: Colors.textMuted },
  userName: { ...Typography.h2, color: Colors.textPrimary, marginTop: 2 },
  roleBadge: {
    backgroundColor: Colors.success + '22',
    borderWidth: 1,
    borderColor: Colors.success,
    borderRadius: Radii.full,
    paddingHorizontal: Spacing.sm,
    paddingVertical: 4,
  },
  roleText: {
    ...Typography.caption,
    fontWeight: '600',
    color: Colors.success,
  },

  // Section title
  sectionTitle: {
    ...Typography.label,
    color: Colors.textMuted,
    marginBottom: Spacing.md,
    marginTop: Spacing.xs,
  },

  // Empty state
  emptyState: {
    backgroundColor: Colors.surface,
    borderRadius: Radii.lg,
    borderWidth: 1,
    borderColor: Colors.border,
    padding: Spacing.xl,
    alignItems: 'center',
    marginBottom: Spacing.lg,
    gap: Spacing.sm,
  },
  emptyIcon: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: Colors.border,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: Spacing.xs,
  },
  emptyTitle: { ...Typography.h3, color: Colors.textPrimary },
  emptySubtitle: {
    ...Typography.bodySmall,
    color: Colors.textSecondary,
    textAlign: 'center',
  },
  prequalBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
    backgroundColor: Colors.blueprint,
    borderRadius: Radii.md,
    paddingVertical: Spacing.md,
    paddingHorizontal: Spacing.xl,
    marginTop: Spacing.sm,
  },
  prequalBtnText: {
    ...Typography.label,
    color: Colors.white,
    fontSize: 15,
  },

  // Loan list
  loanList: { gap: Spacing.md, marginBottom: Spacing.lg },

  // Loan card
  loanCard: {
    backgroundColor: Colors.surface,
    borderRadius: Radii.lg,
    borderWidth: 1,
    borderColor: Colors.border,
    padding: Spacing.md,
    gap: Spacing.sm,
  },
  loanCardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: Spacing.sm,
  },
  loanAddress: {
    ...Typography.body,
    fontWeight: '700',
    color: Colors.textPrimary,
    flex: 1,
  },
  statusBadge: {
    borderWidth: 1,
    borderRadius: Radii.full,
    paddingHorizontal: Spacing.sm,
    paddingVertical: 3,
  },
  statusText: {
    ...Typography.caption,
    fontWeight: '700',
    textTransform: 'uppercase',
  },
  loanMeta: {
    flexDirection: 'row',
    alignItems: 'baseline',
    gap: Spacing.sm,
  },
  loanAmount: {
    fontSize: 22,
    fontWeight: '800',
    color: Colors.blueprint,
  },
  loanType: {
    ...Typography.bodySmall,
    color: Colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  progressSection: { gap: 6 },
  progressLabelRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  progressLabel: { ...Typography.caption, color: Colors.textSecondary },
  progressPct: { ...Typography.caption, color: Colors.blueprint, fontWeight: '700' },
  progressTrack: {
    height: 6,
    backgroundColor: Colors.border,
    borderRadius: 3,
    overflow: 'hidden',
  },
  progressFill: {
    height: 6,
    backgroundColor: Colors.blueprint,
    borderRadius: 3,
  },
  conditionsBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
    backgroundColor: Colors.warning + '18',
    borderWidth: 1,
    borderColor: Colors.warning + '55',
    borderRadius: Radii.sm,
    paddingHorizontal: Spacing.sm,
    paddingVertical: 6,
  },
  conditionsBannerText: {
    ...Typography.caption,
    color: Colors.warning,
    fontWeight: '600',
  },
  loanCardFooter: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'flex-end',
    gap: 2,
    marginTop: Spacing.xs,
  },
  viewDetails: { ...Typography.caption, color: Colors.textMuted },

  // Quick actions
  quickRow: { flexDirection: 'row', gap: Spacing.sm },
  quickCard: {
    flex: 1,
    backgroundColor: Colors.surface,
    borderRadius: Radii.md,
    padding: Spacing.md,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: Colors.border,
    gap: Spacing.xs,
  },
  quickIcon: {
    width: 44,
    height: 44,
    borderRadius: Radii.md,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 2,
  },
  quickLabel: {
    ...Typography.caption,
    fontWeight: '700',
    color: Colors.textPrimary,
    textAlign: 'center',
  },
  quickSubtitle: {
    fontSize: 10,
    color: Colors.textMuted,
    textAlign: 'center',
    lineHeight: 13,
  },
});
