import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  RefreshControl,
  ScrollView,
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

type ConditionStatus = 'Open' | 'Cleared' | 'Waived';
type Severity = 'Low' | 'Standard' | 'High';

interface Condition {
  id: number;
  condition_type: string;
  description: string;
  severity: Severity;
  status: ConditionStatus;
  cleared_at?: string | null;
}

interface LoanDetail {
  id: number;
  borrower_name: string;
  loan_amount: number;
  loan_type: string;
  status: string;
  milestone_stage: string;
  milestone_index: number;
  progress_percent: number;
  property_address: string;
  risk_level: string;
  risk_score?: number;
  processor_notes?: string;
  conditions: Condition[];
  updated_at: string;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const MILESTONES = [
  'Application Started', 'Documents Collected', 'Processing',
  'Underwriting', 'Conditionally Approved', 'Clear to Close', 'Funded',
];

const STATUS_COLORS: Record<string, string> = {
  submitted: Colors.info,
  processing: Colors.warning,
  underwriting: Colors.softGlow,
  approved: Colors.success,
  conditionally_approved: Colors.warning,
  clear_to_close: Colors.success,
  funded: Colors.success,
  denied: Colors.danger,
  cancelled: Colors.danger,
};

const SEVERITY_COLORS: Record<string, string> = {
  Low: Colors.success,
  Standard: Colors.info,
  High: Colors.danger,
};

const STATUS_BADGE_COLORS: Record<ConditionStatus, string> = {
  Open: Colors.warning,
  Cleared: Colors.success,
  Waived: Colors.steel,
};

const RISK_COLORS: Record<string, string> = {
  Low: Colors.success,
  Medium: Colors.warning,
  High: Colors.danger,
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

function fmt(v: number) {
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(2)}M`;
  if (v >= 1_000) return `$${(v / 1_000).toFixed(0)}K`;
  return `$${v}`;
}

// ─── Main Screen ──────────────────────────────────────────────────────────────

export default function ProcessorLoanDetailScreen({ route, navigation }: any) {
  const { loanId } = route.params as { loanId: number };
  const [loan, setLoan] = useState<LoanDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [actionPending, setActionPending] = useState<number | null>(null);

  const fetchLoan = useCallback(async () => {
    try {
      const res = await api.get(`/mobile/lending/processor/loan/${loanId}`);
      setLoan(res.data);
    } catch {
      // silent
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

  const handleConditionAction = (conditionId: number, action: 'Clear' | 'Waive') => {
    Alert.prompt(
      `${action} Condition`,
      'Add a note (optional):',
      async (notes) => {
        setActionPending(conditionId);
        try {
          await api.post(`/mobile/lending/processor/conditions/${conditionId}`, {
            action: action.toLowerCase(),
            notes: notes || '',
          });
          await fetchLoan();
        } catch (e: any) {
          Alert.alert('Error', e.response?.data?.error || 'Could not update condition.');
        } finally {
          setActionPending(null);
        }
      },
      'plain-text',
    );
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <ActivityIndicator color={Colors.blueprint} style={{ flex: 1 }} />
      </SafeAreaView>
    );
  }

  if (!loan) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.errorState}>
          <Ionicons name="alert-circle-outline" size={40} color={Colors.danger} />
          <Text style={styles.errorText}>Loan not found</Text>
          <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
            <Text style={styles.backBtnText}>Go Back</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  const milestoneIdx = loan.milestone_index ?? 0;
  const statusColor = STATUS_COLORS[loan.status] || Colors.steel;
  const riskColor = RISK_COLORS[loan.risk_level] || Colors.steel;
  const openConditions = loan.conditions.filter(c => c.status === 'Open').length;
  const clearedConditions = loan.conditions.filter(c => c.status === 'Cleared').length;

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn} activeOpacity={0.7}>
          <Ionicons name="chevron-back" size={22} color={Colors.textPrimary} />
        </TouchableOpacity>
        <View style={styles.headerCenter}>
          <Text style={styles.headerTitle}>Loan Review</Text>
          <Text style={styles.headerSub} numberOfLines={1}>{loan.property_address}</Text>
        </View>
        <View style={[styles.riskBadge, { backgroundColor: riskColor + '22', borderColor: riskColor }]}>
          <Text style={[styles.riskBadgeText, { color: riskColor }]}>{loan.risk_level} Risk</Text>
        </View>
      </View>

      <ScrollView
        contentContainerStyle={styles.scroll}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.blueprint} />}
        showsVerticalScrollIndicator={false}
      >
        {/* Overview card */}
        <View style={styles.overviewCard}>
          <View style={styles.overviewRow}>
            <View style={styles.overviewMain}>
              <Text style={styles.borrowerName}>{loan.borrower_name}</Text>
              <Text style={styles.loanAmount}>{fmt(loan.loan_amount)}</Text>
              <Text style={styles.loanType}>{loan.loan_type}</Text>
            </View>
            <View style={[styles.statusBadge, { backgroundColor: statusColor + '22', borderColor: statusColor }]}>
              <Text style={[styles.statusText, { color: statusColor }]}>
                {loan.status.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
              </Text>
            </View>
          </View>

          {/* Milestone progress */}
          <View style={styles.milestoneSection}>
            <View style={styles.milestoneTrack}>
              {MILESTONES.map((m, i) => (
                <View key={i} style={styles.milestoneDot}>
                  <View style={[
                    styles.dot,
                    i < milestoneIdx && styles.dotDone,
                    i === milestoneIdx && styles.dotActive,
                  ]} />
                  {i < MILESTONES.length - 1 && (
                    <View style={[styles.dotLine, i < milestoneIdx && styles.dotLineDone]} />
                  )}
                </View>
              ))}
            </View>
            <Text style={styles.milestoneLabel}>{loan.milestone_stage}</Text>
          </View>
        </View>

        {/* Conditions summary chips */}
        <View style={styles.conditionSummary}>
          <View style={[styles.summaryChip, { backgroundColor: Colors.warning + '18', borderColor: Colors.warning + '44' }]}>
            <Text style={[styles.summaryCount, { color: Colors.warning }]}>{openConditions}</Text>
            <Text style={[styles.summaryLabel, { color: Colors.warning }]}>Open</Text>
          </View>
          <View style={[styles.summaryChip, { backgroundColor: Colors.success + '18', borderColor: Colors.success + '44' }]}>
            <Text style={[styles.summaryCount, { color: Colors.success }]}>{clearedConditions}</Text>
            <Text style={[styles.summaryLabel, { color: Colors.success }]}>Cleared</Text>
          </View>
          <View style={[styles.summaryChip, { backgroundColor: Colors.info + '18', borderColor: Colors.info + '44' }]}>
            <Text style={[styles.summaryCount, { color: Colors.info }]}>{loan.conditions.length}</Text>
            <Text style={[styles.summaryLabel, { color: Colors.info }]}>Total</Text>
          </View>
        </View>

        {/* Conditions */}
        {loan.conditions.length > 0 && (
          <>
            <Text style={styles.sectionTitle}>CONDITIONS</Text>
            {loan.conditions.map(cond => {
              const sevColor = SEVERITY_COLORS[cond.severity] || Colors.steel;
              const statColor = STATUS_BADGE_COLORS[cond.status] || Colors.steel;
              const isOpen = cond.status === 'Open';

              return (
                <View key={cond.id} style={[styles.condCard, { borderLeftColor: sevColor }]}>
                  <View style={styles.condTop}>
                    <Text style={styles.condType} numberOfLines={1}>{cond.condition_type}</Text>
                    <View style={styles.condChips}>
                      <View style={[styles.chip, { backgroundColor: sevColor + '22', borderColor: sevColor }]}>
                        <Text style={[styles.chipText, { color: sevColor }]}>{cond.severity}</Text>
                      </View>
                      <View style={[styles.chip, { backgroundColor: statColor + '22', borderColor: statColor }]}>
                        <Text style={[styles.chipText, { color: statColor }]}>{cond.status}</Text>
                      </View>
                    </View>
                  </View>
                  <Text style={styles.condDesc} numberOfLines={3}>{cond.description}</Text>
                  {cond.cleared_at && (
                    <Text style={styles.condDate}>
                      Cleared {new Date(cond.cleared_at).toLocaleDateString()}
                    </Text>
                  )}
                  {isOpen && (
                    <View style={styles.condActions}>
                      <TouchableOpacity
                        style={styles.clearBtn}
                        onPress={() => handleConditionAction(cond.id, 'Clear')}
                        disabled={actionPending === cond.id}
                        activeOpacity={0.75}
                      >
                        {actionPending === cond.id ? (
                          <ActivityIndicator size="small" color={Colors.success} />
                        ) : (
                          <>
                            <Ionicons name="checkmark-circle-outline" size={14} color={Colors.success} />
                            <Text style={styles.clearBtnText}>Clear</Text>
                          </>
                        )}
                      </TouchableOpacity>
                      <TouchableOpacity
                        style={styles.waiveBtn}
                        onPress={() => handleConditionAction(cond.id, 'Waive')}
                        disabled={actionPending === cond.id}
                        activeOpacity={0.75}
                      >
                        <Ionicons name="remove-circle-outline" size={14} color={Colors.steel} />
                        <Text style={styles.waiveBtnText}>Waive</Text>
                      </TouchableOpacity>
                    </View>
                  )}
                </View>
              );
            })}
          </>
        )}

        {/* Processor notes */}
        {loan.processor_notes ? (
          <>
            <Text style={styles.sectionTitle}>PROCESSOR NOTES</Text>
            <View style={styles.notesCard}>
              <Text style={styles.notesText}>{loan.processor_notes}</Text>
            </View>
          </>
        ) : null}

        {loan.conditions.length === 0 && (
          <View style={styles.emptyConditions}>
            <Ionicons name="checkmark-circle-outline" size={40} color={Colors.success} />
            <Text style={styles.emptyText}>No conditions on file</Text>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },

  header: {
    flexDirection: 'row', alignItems: 'center', gap: Spacing.sm,
    paddingHorizontal: Spacing.md, paddingTop: Spacing.md, paddingBottom: Spacing.sm,
    borderBottomWidth: 1, borderBottomColor: Colors.border,
  },
  backBtn: { padding: 4 },
  headerCenter: { flex: 1 },
  headerTitle: { ...Typography.h3, color: Colors.textPrimary },
  headerSub: { ...Typography.caption, color: Colors.textMuted, marginTop: 1 },
  riskBadge: { borderWidth: 1, borderRadius: Radii.full, paddingHorizontal: 8, paddingVertical: 3 },
  riskBadgeText: { fontSize: 10, fontWeight: '700', textTransform: 'uppercase' },

  scroll: { padding: Spacing.lg, paddingBottom: Spacing.xxl },

  overviewCard: {
    backgroundColor: Colors.surface, borderRadius: Radii.lg, padding: Spacing.lg,
    borderWidth: 1, borderColor: Colors.border, marginBottom: Spacing.md,
  },
  overviewRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: Spacing.md },
  overviewMain: { flex: 1 },
  borrowerName: { ...Typography.h3, color: Colors.textPrimary, marginBottom: 2 },
  loanAmount: { fontSize: 22, fontWeight: '800', color: Colors.blueprint, marginBottom: 2 },
  loanType: { ...Typography.caption, color: Colors.textMuted },
  statusBadge: { borderWidth: 1, borderRadius: Radii.full, paddingHorizontal: 10, paddingVertical: 4, marginLeft: Spacing.sm },
  statusText: { fontSize: 10, fontWeight: '700', textTransform: 'uppercase' },

  milestoneSection: { marginTop: Spacing.sm },
  milestoneTrack: { flexDirection: 'row', alignItems: 'center', marginBottom: 6 },
  milestoneDot: { flexDirection: 'row', alignItems: 'center', flex: 1 },
  dot: { width: 8, height: 8, borderRadius: 4, backgroundColor: Colors.border },
  dotDone: { backgroundColor: Colors.blueprint },
  dotActive: { backgroundColor: Colors.success, width: 10, height: 10, borderRadius: 5 },
  dotLine: { flex: 1, height: 2, backgroundColor: Colors.border },
  dotLineDone: { backgroundColor: Colors.blueprint },
  milestoneLabel: { ...Typography.caption, color: Colors.textMuted, textAlign: 'center' },

  conditionSummary: { flexDirection: 'row', gap: Spacing.sm, marginBottom: Spacing.lg },
  summaryChip: {
    flex: 1, borderWidth: 1, borderRadius: Radii.md, paddingVertical: Spacing.sm,
    alignItems: 'center', justifyContent: 'center',
  },
  summaryCount: { fontSize: 20, fontWeight: '800' },
  summaryLabel: { fontSize: 10, fontWeight: '600', marginTop: 2 },

  sectionTitle: { ...Typography.label, color: Colors.textMuted, marginBottom: Spacing.sm, marginTop: Spacing.xs },

  condCard: {
    backgroundColor: Colors.surface, borderRadius: Radii.md, padding: Spacing.md,
    marginBottom: Spacing.sm, borderWidth: 1, borderColor: Colors.border, borderLeftWidth: 3,
  },
  condTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: Spacing.sm },
  condType: { ...Typography.bodySmall, color: Colors.textPrimary, fontWeight: '700', flex: 1, marginRight: Spacing.sm },
  condChips: { flexDirection: 'row', gap: 4 },
  chip: { borderWidth: 1, borderRadius: Radii.full, paddingHorizontal: 7, paddingVertical: 2 },
  chipText: { fontSize: 9, fontWeight: '700', textTransform: 'uppercase' },
  condDesc: { ...Typography.bodySmall, color: Colors.textSecondary, lineHeight: 20 },
  condDate: { ...Typography.caption, color: Colors.textMuted, marginTop: Spacing.xs },
  condActions: { flexDirection: 'row', gap: Spacing.sm, marginTop: Spacing.md },
  clearBtn: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 5,
    paddingVertical: 8, borderRadius: Radii.md, backgroundColor: Colors.success + '18',
    borderWidth: 1, borderColor: Colors.success + '44',
  },
  clearBtnText: { ...Typography.caption, color: Colors.success, fontWeight: '700' },
  waiveBtn: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 5,
    paddingVertical: 8, borderRadius: Radii.md, backgroundColor: Colors.border,
    borderWidth: 1, borderColor: Colors.border,
  },
  waiveBtnText: { ...Typography.caption, color: Colors.textMuted, fontWeight: '700' },

  notesCard: {
    backgroundColor: Colors.surface, borderRadius: Radii.md, padding: Spacing.md,
    borderWidth: 1, borderColor: Colors.border, marginBottom: Spacing.md,
  },
  notesText: { ...Typography.bodySmall, color: Colors.textSecondary, lineHeight: 22 },

  emptyConditions: { alignItems: 'center', paddingTop: Spacing.xl, gap: Spacing.md },
  emptyText: { ...Typography.body, color: Colors.textMuted },

  errorState: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: Spacing.md },
  errorText: { ...Typography.body, color: Colors.textMuted },
  backBtnText: { ...Typography.body, color: Colors.blueprint },
});
