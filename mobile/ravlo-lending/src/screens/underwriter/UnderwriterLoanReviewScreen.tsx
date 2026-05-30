import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Modal,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Radii, Spacing, Typography } from '../../theme';
import { api } from '../../services/api';

// ─── Types ────────────────────────────────────────────────────────────────────

type RiskLevel = 'Low' | 'Medium' | 'High';
type ConditionStatus = 'Open' | 'Cleared';
type ConditionSeverity = 'Low' | 'Standard' | 'High';
type DecisionValue = 'approved' | 'conditional' | 'suspended' | 'denied';

interface Condition {
  id: number;
  condition_type: string;
  description: string;
  severity: ConditionSeverity;
  status: ConditionStatus;
  cleared_at?: string | null;
}

interface LoanDetail {
  id: number;
  borrower_name: string;
  loan_amount: number;
  loan_type: string;
  milestone_stage: string;
  property_address: string;
  risk_score: number;
  risk_level: RiskLevel;
  ltv: number;
  dti_front: number;
  dti_back: number;
  ai_summary?: string;
  conditions: Condition[];
  processor_notes?: string;
  updated_at: string;
}

interface DecisionOption {
  value: DecisionValue;
  label: string;
  color: string;
  icon: React.ComponentProps<typeof Ionicons>['name'];
}

// ─── Constants ────────────────────────────────────────────────────────────────

const DECISION_OPTIONS: DecisionOption[] = [
  { value: 'approved',    label: 'Approve',     color: Colors.success, icon: 'checkmark-circle-outline' },
  { value: 'conditional', label: 'Conditional', color: Colors.warning, icon: 'alert-circle-outline'     },
  { value: 'suspended',   label: 'Suspend',     color: Colors.info,    icon: 'pause-circle-outline'     },
  { value: 'denied',      label: 'Deny',        color: Colors.danger,  icon: 'close-circle-outline'     },
];

const SEVERITY_COLORS: Record<ConditionSeverity, string> = {
  Low:      Colors.success,
  Standard: Colors.info,
  High:     Colors.danger,
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

const formatCurrency = (val: number): string =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(val);

const riskScoreColor = (score: number): string => {
  if (score >= 7) return Colors.danger;
  if (score >= 4) return Colors.warning;
  return Colors.success;
};

const riskLevelColor = (level: RiskLevel): string => {
  if (level === 'High')   return Colors.danger;
  if (level === 'Medium') return Colors.warning;
  return Colors.success;
};

// ─── Section Header ───────────────────────────────────────────────────────────

function SectionHeader({ title, icon }: { title: string; icon: React.ComponentProps<typeof Ionicons>['name'] }) {
  return (
    <View style={sectionHeaderStyles.row}>
      <Ionicons name={icon} size={15} color={Colors.textMuted} />
      <Text style={sectionHeaderStyles.text}>{title}</Text>
    </View>
  );
}

const sectionHeaderStyles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
    marginBottom: Spacing.sm,
  },
  text: {
    ...Typography.label,
    color: Colors.textMuted,
    textTransform: 'uppercase',
    letterSpacing: 0.8,
  },
});

// ─── Risk Header Card ─────────────────────────────────────────────────────────

interface RiskHeaderCardProps {
  loan: LoanDetail;
}

function RiskHeaderCard({ loan }: RiskHeaderCardProps) {
  const scoreColor = riskScoreColor(loan.risk_score);
  const levelColor = riskLevelColor(loan.risk_level);

  return (
    <View style={riskCardStyles.card}>
      {/* Score + level */}
      <View style={riskCardStyles.scoreRow}>
        <View style={[riskCardStyles.scoreBadge, { backgroundColor: scoreColor + '18', borderColor: scoreColor }]}>
          <Text style={[riskCardStyles.scoreValue, { color: scoreColor }]}>{loan.risk_score}</Text>
          <Text style={[riskCardStyles.scoreDenom, { color: scoreColor }]}>/10</Text>
        </View>
        <View style={riskCardStyles.scoreRight}>
          <View style={[riskCardStyles.levelBadge, { backgroundColor: levelColor + '1A', borderColor: levelColor }]}>
            <Text style={[riskCardStyles.levelText, { color: levelColor }]}>{loan.risk_level} Risk</Text>
          </View>
          <Text style={riskCardStyles.borrowerName} numberOfLines={1}>{loan.borrower_name}</Text>
          <Text style={riskCardStyles.loanAmount}>{formatCurrency(loan.loan_amount)}</Text>
        </View>
      </View>

      <View style={riskCardStyles.divider} />

      {/* Metrics row */}
      <View style={riskCardStyles.metricsRow}>
        <MetricBlock label="LTV"       value={`${loan.ltv.toFixed(1)}%`} />
        <View style={riskCardStyles.metricSep} />
        <MetricBlock label="DTI Front" value={`${loan.dti_front.toFixed(1)}%`} />
        <View style={riskCardStyles.metricSep} />
        <MetricBlock label="DTI Back"  value={`${loan.dti_back.toFixed(1)}%`} />
        <View style={riskCardStyles.metricSep} />
        <MetricBlock label="Type"      value={loan.loan_type} />
      </View>

      {/* Milestone */}
      <View style={riskCardStyles.milestoneRow}>
        <Ionicons name="flag-outline" size={13} color={Colors.textMuted} />
        <Text style={riskCardStyles.milestoneText}>
          {loan.milestone_stage.replace(/_/g, ' ')}
        </Text>
      </View>
    </View>
  );
}

function MetricBlock({ label, value }: { label: string; value: string }) {
  return (
    <View style={riskCardStyles.metricBlock}>
      <Text style={riskCardStyles.metricLabel}>{label}</Text>
      <Text style={riskCardStyles.metricValue}>{value}</Text>
    </View>
  );
}

const riskCardStyles = StyleSheet.create({
  card: {
    backgroundColor: Colors.surface,
    borderRadius: Radii.lg,
    borderWidth: 1,
    borderColor: Colors.border,
    padding: Spacing.md,
    marginBottom: Spacing.md,
  },
  scoreRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
    marginBottom: Spacing.sm,
  },
  scoreBadge: {
    width: 76,
    height: 76,
    borderRadius: 38,
    borderWidth: 2.5,
    alignItems: 'center',
    justifyContent: 'center',
    flexDirection: 'row',
  },
  scoreValue: {
    fontSize: 30,
    fontWeight: '800',
    lineHeight: 36,
  },
  scoreDenom: {
    fontSize: 13,
    fontWeight: '600',
    lineHeight: 20,
    alignSelf: 'flex-end',
    marginBottom: 4,
  },
  scoreRight: {
    flex: 1,
    gap: 4,
  },
  levelBadge: {
    alignSelf: 'flex-start',
    borderRadius: Radii.full,
    borderWidth: 1,
    paddingHorizontal: Spacing.sm,
    paddingVertical: 3,
  },
  levelText: {
    ...Typography.caption,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  borrowerName: {
    ...Typography.h3,
    color: Colors.textPrimary,
  },
  loanAmount: {
    ...Typography.body,
    color: Colors.textSecondary,
    fontWeight: '600',
  },
  divider: {
    height: 1,
    backgroundColor: Colors.border,
    marginVertical: Spacing.sm,
  },
  metricsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: Spacing.sm,
  },
  metricBlock: {
    flex: 1,
    alignItems: 'center',
  },
  metricLabel: {
    ...Typography.caption,
    color: Colors.textMuted,
    marginBottom: 2,
  },
  metricValue: {
    ...Typography.bodySmall,
    color: Colors.textPrimary,
    fontWeight: '700',
  },
  metricSep: {
    width: 1,
    height: 28,
    backgroundColor: Colors.border,
  },
  milestoneRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
  },
  milestoneText: {
    ...Typography.caption,
    color: Colors.textMuted,
    textTransform: 'capitalize',
  },
});

// ─── AI Summary Card ──────────────────────────────────────────────────────────

function AiSummaryCard({ summary }: { summary: string }) {
  return (
    <View style={aiCardStyles.card}>
      <SectionHeader title="AI Summary" icon="sparkles-outline" />
      <Text style={aiCardStyles.text}>{summary}</Text>
    </View>
  );
}

const aiCardStyles = StyleSheet.create({
  card: {
    backgroundColor: Colors.surface,
    borderRadius: Radii.lg,
    borderWidth: 1,
    borderColor: Colors.blueprint + '44',
    padding: Spacing.md,
    marginBottom: Spacing.md,
  },
  text: {
    ...Typography.bodySmall,
    color: Colors.textSecondary,
    lineHeight: 22,
  },
});

// ─── Conditions Section ───────────────────────────────────────────────────────

function ConditionsSection({ conditions }: { conditions: Condition[] }) {
  const openCount    = conditions.filter(c => c.status === 'Open').length;
  const clearedCount = conditions.filter(c => c.status === 'Cleared').length;

  return (
    <View style={condStyles.card}>
      <SectionHeader title="Conditions" icon="shield-outline" />

      {/* Summary row */}
      <View style={condStyles.summaryRow}>
        <View style={[condStyles.summaryChip, { backgroundColor: Colors.warning + '1A', borderColor: Colors.warning + '55' }]}>
          <Text style={[condStyles.summaryChipText, { color: Colors.warning }]}>{openCount} Open</Text>
        </View>
        <View style={[condStyles.summaryChip, { backgroundColor: Colors.success + '1A', borderColor: Colors.success + '55' }]}>
          <Text style={[condStyles.summaryChipText, { color: Colors.success }]}>{clearedCount} Cleared</Text>
        </View>
      </View>

      {conditions.length === 0 ? (
        <Text style={condStyles.emptyText}>No conditions on file.</Text>
      ) : (
        conditions.map((condition, idx) => (
          <ConditionRow key={condition.id} condition={condition} isLast={idx === conditions.length - 1} />
        ))
      )}
    </View>
  );
}

function ConditionRow({ condition, isLast }: { condition: Condition; isLast: boolean }) {
  const severityColor = SEVERITY_COLORS[condition.severity] ?? Colors.steel;
  const statusColor   = condition.status === 'Open' ? Colors.warning : Colors.success;

  return (
    <View style={[condStyles.conditionRow, !isLast && condStyles.conditionBorder]}>
      {/* Left color bar */}
      <View style={[condStyles.colorBar, { backgroundColor: severityColor }]} />

      <View style={condStyles.conditionContent}>
        {/* Type + badges */}
        <View style={condStyles.conditionTopRow}>
          <Text style={condStyles.conditionType} numberOfLines={1}>{condition.condition_type}</Text>
          <View style={condStyles.badgeGroup}>
            <View style={[condStyles.chip, { backgroundColor: severityColor + '22', borderColor: severityColor }]}>
              <Text style={[condStyles.chipText, { color: severityColor }]}>{condition.severity}</Text>
            </View>
            <View style={[condStyles.chip, { backgroundColor: statusColor + '1A', borderColor: statusColor }]}>
              <Text style={[condStyles.chipText, { color: statusColor }]}>{condition.status}</Text>
            </View>
          </View>
        </View>
        {/* Description */}
        <Text style={condStyles.conditionDesc} numberOfLines={3}>{condition.description}</Text>
        {/* Cleared date */}
        {condition.cleared_at && (
          <View style={condStyles.clearedRow}>
            <Ionicons name="checkmark-circle" size={12} color={Colors.success} />
            <Text style={condStyles.clearedText}>
              Cleared {new Date(condition.cleared_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
            </Text>
          </View>
        )}
      </View>
    </View>
  );
}

const condStyles = StyleSheet.create({
  card: {
    backgroundColor: Colors.surface,
    borderRadius: Radii.lg,
    borderWidth: 1,
    borderColor: Colors.border,
    padding: Spacing.md,
    marginBottom: Spacing.md,
  },
  summaryRow: {
    flexDirection: 'row',
    gap: Spacing.sm,
    marginBottom: Spacing.sm,
  },
  summaryChip: {
    borderRadius: Radii.full,
    borderWidth: 1,
    paddingHorizontal: Spacing.sm,
    paddingVertical: 3,
  },
  summaryChipText: {
    ...Typography.caption,
    fontWeight: '700',
  },
  emptyText: {
    ...Typography.bodySmall,
    color: Colors.textMuted,
    fontStyle: 'italic',
  },
  conditionRow: {
    flexDirection: 'row',
    paddingVertical: Spacing.sm,
  },
  conditionBorder: {
    borderBottomWidth: 1,
    borderBottomColor: Colors.border,
  },
  colorBar: {
    width: 3,
    borderRadius: 2,
    marginRight: Spacing.sm,
    alignSelf: 'stretch',
  },
  conditionContent: {
    flex: 1,
  },
  conditionTopRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: Spacing.sm,
    marginBottom: 4,
  },
  conditionType: {
    ...Typography.label,
    color: Colors.textPrimary,
    flex: 1,
  },
  badgeGroup: {
    flexDirection: 'row',
    gap: 4,
    flexShrink: 0,
  },
  chip: {
    borderRadius: Radii.sm,
    borderWidth: 1,
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  chipText: {
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 0.3,
  },
  conditionDesc: {
    ...Typography.bodySmall,
    color: Colors.textSecondary,
    lineHeight: 19,
  },
  clearedRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginTop: 4,
  },
  clearedText: {
    ...Typography.caption,
    color: Colors.success,
  },
});

// ─── Processor Notes Card ─────────────────────────────────────────────────────

function ProcessorNotesCard({ notes }: { notes: string }) {
  return (
    <View style={notesStyles.card}>
      <SectionHeader title="Processor Notes" icon="document-text-outline" />
      <Text style={notesStyles.text}>{notes}</Text>
    </View>
  );
}

const notesStyles = StyleSheet.create({
  card: {
    backgroundColor: Colors.surface,
    borderRadius: Radii.lg,
    borderWidth: 1,
    borderColor: Colors.border,
    padding: Spacing.md,
    marginBottom: Spacing.md,
  },
  text: {
    ...Typography.bodySmall,
    color: Colors.textSecondary,
    lineHeight: 22,
  },
});

// ─── Decision Modal ───────────────────────────────────────────────────────────

interface DecisionModalProps {
  visible: boolean;
  option: DecisionOption | null;
  onClose: () => void;
  onConfirm: (notes: string) => void;
  submitting: boolean;
}

function DecisionModal({ visible, option, onClose, onConfirm, submitting }: DecisionModalProps) {
  const [notes, setNotes] = useState('');
  const inputRef = useRef<TextInput>(null);

  // Reset notes each time the modal opens for a new decision
  useEffect(() => {
    if (visible) {
      setNotes('');
      setTimeout(() => inputRef.current?.focus(), 300);
    }
  }, [visible]);

  if (!option) return null;

  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      onRequestClose={onClose}
    >
      <View style={modalStyles.overlay}>
        <View style={modalStyles.sheet}>
          {/* Handle bar */}
          <View style={modalStyles.handle} />

          {/* Icon + title */}
          <View style={[modalStyles.iconWrap, { backgroundColor: option.color + '1A', borderColor: option.color + '44' }]}>
            <Ionicons name={option.icon} size={28} color={option.color} />
          </View>
          <Text style={modalStyles.title}>{option.label} Decision</Text>
          <Text style={modalStyles.subtitle}>
            Add notes explaining your {option.label.toLowerCase()} decision. Notes will be saved with the loan file.
          </Text>

          {/* Notes input */}
          <TextInput
            ref={inputRef}
            style={modalStyles.input}
            placeholder="Enter decision notes..."
            placeholderTextColor={Colors.textMuted}
            multiline
            numberOfLines={5}
            textAlignVertical="top"
            value={notes}
            onChangeText={setNotes}
            editable={!submitting}
          />

          {/* Buttons */}
          <View style={modalStyles.buttonRow}>
            <TouchableOpacity
              style={modalStyles.cancelBtn}
              onPress={onClose}
              disabled={submitting}
              activeOpacity={0.75}
            >
              <Text style={modalStyles.cancelText}>Cancel</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[modalStyles.confirmBtn, { backgroundColor: option.color, opacity: submitting ? 0.7 : 1 }]}
              onPress={() => onConfirm(notes)}
              disabled={submitting}
              activeOpacity={0.8}
            >
              {submitting ? (
                <ActivityIndicator size="small" color={Colors.white} />
              ) : (
                <>
                  <Ionicons name={option.icon} size={16} color={Colors.white} />
                  <Text style={modalStyles.confirmText}>{option.label}</Text>
                </>
              )}
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </Modal>
  );
}

const modalStyles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.6)',
    justifyContent: 'flex-end',
  },
  sheet: {
    backgroundColor: Colors.surfaceElevated,
    borderTopLeftRadius: Radii.xl,
    borderTopRightRadius: Radii.xl,
    borderWidth: 1,
    borderColor: Colors.border,
    padding: Spacing.lg,
    paddingBottom: Spacing.xl,
  },
  handle: {
    width: 36,
    height: 4,
    borderRadius: 2,
    backgroundColor: Colors.border,
    alignSelf: 'center',
    marginBottom: Spacing.lg,
  },
  iconWrap: {
    width: 60,
    height: 60,
    borderRadius: 30,
    borderWidth: 1.5,
    alignItems: 'center',
    justifyContent: 'center',
    alignSelf: 'center',
    marginBottom: Spacing.md,
  },
  title: {
    ...Typography.h3,
    color: Colors.textPrimary,
    textAlign: 'center',
    marginBottom: Spacing.xs,
  },
  subtitle: {
    ...Typography.bodySmall,
    color: Colors.textMuted,
    textAlign: 'center',
    marginBottom: Spacing.lg,
    lineHeight: 20,
  },
  input: {
    backgroundColor: Colors.surface,
    borderRadius: Radii.md,
    borderWidth: 1,
    borderColor: Colors.border,
    color: Colors.textPrimary,
    ...Typography.bodySmall,
    padding: Spacing.md,
    minHeight: 110,
    marginBottom: Spacing.lg,
  },
  buttonRow: {
    flexDirection: 'row',
    gap: Spacing.sm,
  },
  cancelBtn: {
    flex: 1,
    paddingVertical: Spacing.md,
    borderRadius: Radii.md,
    borderWidth: 1,
    borderColor: Colors.border,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.surface,
  },
  cancelText: {
    ...Typography.label,
    color: Colors.textSecondary,
  },
  confirmBtn: {
    flex: 2,
    paddingVertical: Spacing.md,
    borderRadius: Radii.md,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.xs,
  },
  confirmText: {
    ...Typography.label,
    color: Colors.white,
  },
});

// ─── Decision Section ─────────────────────────────────────────────────────────

interface DecisionSectionProps {
  onDecision: (option: DecisionOption) => void;
}

function DecisionSection({ onDecision }: DecisionSectionProps) {
  return (
    <View style={decisionStyles.card}>
      <SectionHeader title="Underwriting Decision" icon="scale-outline" />
      <Text style={decisionStyles.hint}>Select a decision to record your underwriting outcome.</Text>
      <View style={decisionStyles.grid}>
        {DECISION_OPTIONS.map((opt) => (
          <TouchableOpacity
            key={opt.value}
            style={[decisionStyles.decisionBtn, { borderColor: opt.color + '66', backgroundColor: opt.color + '12' }]}
            onPress={() => onDecision(opt)}
            activeOpacity={0.75}
          >
            <View style={[decisionStyles.decisionIconWrap, { backgroundColor: opt.color + '22' }]}>
              <Ionicons name={opt.icon} size={24} color={opt.color} />
            </View>
            <Text style={[decisionStyles.decisionLabel, { color: opt.color }]}>{opt.label}</Text>
          </TouchableOpacity>
        ))}
      </View>
    </View>
  );
}

const decisionStyles = StyleSheet.create({
  card: {
    backgroundColor: Colors.surface,
    borderRadius: Radii.lg,
    borderWidth: 1,
    borderColor: Colors.border,
    padding: Spacing.md,
    marginBottom: Spacing.md,
  },
  hint: {
    ...Typography.caption,
    color: Colors.textMuted,
    marginBottom: Spacing.md,
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.sm,
  },
  decisionBtn: {
    width: '47.5%',
    borderRadius: Radii.md,
    borderWidth: 1.5,
    paddingVertical: Spacing.md,
    alignItems: 'center',
    gap: Spacing.xs,
  },
  decisionIconWrap: {
    width: 48,
    height: 48,
    borderRadius: 24,
    alignItems: 'center',
    justifyContent: 'center',
  },
  decisionLabel: {
    ...Typography.label,
    fontSize: 15,
  },
});

// ─── Screen ───────────────────────────────────────────────────────────────────

export default function UnderwriterLoanReviewScreen({ route, navigation }: any) {
  const { loanId } = route.params;

  const [loan, setLoan]               = useState<LoanDetail | null>(null);
  const [loading, setLoading]         = useState(true);
  const [refreshing, setRefreshing]   = useState(false);
  const [modalOption, setModalOption] = useState<DecisionOption | null>(null);
  const [submitting, setSubmitting]   = useState(false);

  // ── Data fetching ──────────────────────────────────────────────────────────

  const fetchLoan = useCallback(async () => {
    try {
      const res = await api.get(`/mobile/lending/underwriter/loan/${loanId}`);
      setLoan(res.data.loan ?? res.data);
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

  // ── Decision submission ────────────────────────────────────────────────────

  const handleConfirmDecision = useCallback(
    async (notes: string) => {
      if (!modalOption) return;
      setSubmitting(true);
      try {
        await api.post(`/mobile/lending/underwriter/loan/${loanId}/decision`, {
          decision: modalOption.value,
          notes,
        });
        setModalOption(null);
        Alert.alert(
          'Decision Recorded',
          `Loan has been marked as ${modalOption.label.toLowerCase()}.`,
          [{ text: 'OK', onPress: () => navigation.goBack() }]
        );
      } catch (err: any) {
        Alert.alert('Error', err.response?.data?.error || 'Failed to submit decision. Please try again.');
      } finally {
        setSubmitting(false);
      }
    },
    [loanId, modalOption, navigation]
  );

  // ── Loading state ──────────────────────────────────────────────────────────

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.navBar}>
          <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
            <Ionicons name="chevron-back" size={24} color={Colors.textPrimary} />
            <Text style={styles.backText}>UW Queue</Text>
          </TouchableOpacity>
        </View>
        <View style={styles.centered}>
          <ActivityIndicator size="large" color={Colors.blueprint} />
        </View>
      </SafeAreaView>
    );
  }

  if (!loan) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.navBar}>
          <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
            <Ionicons name="chevron-back" size={24} color={Colors.textPrimary} />
            <Text style={styles.backText}>UW Queue</Text>
          </TouchableOpacity>
        </View>
        <View style={styles.centered}>
          <Ionicons name="alert-circle-outline" size={48} color={Colors.danger} />
          <Text style={styles.errorText}>Loan not found.</Text>
        </View>
      </SafeAreaView>
    );
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <SafeAreaView style={styles.container}>
      {/* Nav bar */}
      <View style={styles.navBar}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn} activeOpacity={0.75}>
          <Ionicons name="chevron-back" size={24} color={Colors.textPrimary} />
          <Text style={styles.backText}>UW Queue</Text>
        </TouchableOpacity>
        <Text style={styles.navTitle}>Loan Review</Text>
        <View style={styles.navSpacer} />
      </View>

      {/* Address sub-header */}
      <View style={styles.addressBar}>
        <Ionicons name="location-outline" size={13} color={Colors.textMuted} />
        <Text style={styles.addressText} numberOfLines={1}>{loan.property_address}</Text>
      </View>

      <ScrollView
        contentContainerStyle={styles.scroll}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.blueprint} />
        }
      >
        {/* Risk Header Card */}
        <RiskHeaderCard loan={loan} />

        {/* AI Summary */}
        {!!loan.ai_summary && (
          <AiSummaryCard summary={loan.ai_summary} />
        )}

        {/* Conditions */}
        <ConditionsSection conditions={loan.conditions ?? []} />

        {/* Processor Notes */}
        {!!loan.processor_notes && (
          <ProcessorNotesCard notes={loan.processor_notes} />
        )}

        {/* Decision Section */}
        <DecisionSection onDecision={(opt) => setModalOption(opt)} />
      </ScrollView>

      {/* Decision Modal */}
      <DecisionModal
        visible={modalOption !== null}
        option={modalOption}
        onClose={() => { if (!submitting) setModalOption(null); }}
        onConfirm={handleConfirmDecision}
        submitting={submitting}
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
    gap: Spacing.sm,
  },
  errorText: {
    ...Typography.body,
    color: Colors.danger,
  },

  // Nav
  navBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
  },
  backBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    flex: 1,
  },
  backText: {
    ...Typography.body,
    color: Colors.textPrimary,
  },
  navTitle: {
    ...Typography.label,
    color: Colors.textSecondary,
    fontSize: 15,
  },
  navSpacer: {
    flex: 1,
  },

  // Address bar
  addressBar: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: Spacing.lg,
    paddingBottom: Spacing.sm,
  },
  addressText: {
    ...Typography.caption,
    color: Colors.textMuted,
    flex: 1,
  },

  // Scroll
  scroll: {
    padding: Spacing.lg,
    paddingBottom: Spacing.xxl,
  },
});
