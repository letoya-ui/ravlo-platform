import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Animated,
  Linking,
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

interface Milestone {
  name: string;
  completed?: boolean;
  stage?: string;
}

type ConditionSeverity = 'Low' | 'Standard' | 'High';
type ConditionStatus = 'Open' | 'Cleared' | 'Waived';

interface Condition {
  id: number;
  condition_type: string;
  description: string;
  severity: ConditionSeverity;
  status: ConditionStatus;
}

interface LoanOfficer {
  name: string;
  email: string;
  phone: string;
}

interface LoanDetail {
  id: number;
  amount: number;
  loan_type: string;
  status: string;
  milestone_stage: string;
  milestone_index: number;
  milestones: Milestone[];
  progress_percent: number;
  property_address: string;
  property_value: number;
  rate: number;
  term_months: number;
  ltv: number;
  front_end_dti: number;
  back_end_dti: number;
  ai_summary?: string;
  updated_at: string;
  created_at: string;
}

interface LoanDetailResponse {
  loan: LoanDetail;
  loan_officer?: LoanOfficer;
  open_conditions: number;
  conditions: Condition[];
  documents: any[];
}

// ─── Constants ────────────────────────────────────────────────────────────────

const STATUS_COLORS: Record<string, string> = {
  submitted:    Colors.info,
  processing:   Colors.warning,
  underwriting: Colors.softGlow,
  approved:     Colors.success,
  closed:       Colors.steel,
  funded:       Colors.success,
  denied:       Colors.danger,
  cancelled:    Colors.danger,
  in_review:    Colors.info,
};

const SEVERITY_COLORS: Record<ConditionSeverity, string> = {
  Low:      Colors.success,
  Standard: Colors.info,
  High:     Colors.danger,
};

const COND_STATUS_COLORS: Record<ConditionStatus, string> = {
  Open:    Colors.warning,
  Cleared: Colors.success,
  Waived:  Colors.steel,
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatCurrency(val: number): string {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(val ?? 0);
}

function formatPct(val: number | undefined | null): string {
  if (val == null) return '—';
  return `${val.toFixed(2)}%`;
}

function capitalize(str: string): string {
  return (str || '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

// ─── Milestone Timeline ───────────────────────────────────────────────────────

interface MilestoneTimelineProps {
  milestones: Milestone[];
  currentIndex: number;
}

function MilestoneTimeline({ milestones, currentIndex }: MilestoneTimelineProps) {
  const pulseAnim = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    Animated.loop(
      Animated.sequence([
        Animated.timing(pulseAnim, { toValue: 1.18, duration: 800, useNativeDriver: true }),
        Animated.timing(pulseAnim, { toValue: 1, duration: 800, useNativeDriver: true }),
      ])
    ).start();
  }, [pulseAnim]);

  if (!milestones || milestones.length === 0) {
    return (
      <View style={tlStyles.empty}>
        <Text style={tlStyles.emptyText}>No milestone data available.</Text>
      </View>
    );
  }

  return (
    <View style={tlStyles.container}>
      {milestones.map((milestone, idx) => {
        const isCompleted = idx < currentIndex;
        const isCurrent   = idx === currentIndex;
        const isFuture    = idx > currentIndex;
        const isLast      = idx === milestones.length - 1;

        let circleStyle: any[] = [tlStyles.circle];
        let iconName: any = null;

        if (isCompleted) {
          circleStyle = [tlStyles.circle, tlStyles.circleCompleted];
          iconName = 'checkmark';
        } else if (isCurrent) {
          circleStyle = [tlStyles.circle, tlStyles.circleCurrent];
        } else {
          circleStyle = [tlStyles.circle, tlStyles.circleFuture];
        }

        return (
          <View key={idx} style={tlStyles.row}>
            {/* Left: line + circle column */}
            <View style={tlStyles.lineCol}>
              {/* Top connector line */}
              {idx > 0 ? (
                <View style={[tlStyles.lineSegment, isCompleted || isCurrent ? tlStyles.lineActive : tlStyles.lineInactive]} />
              ) : (
                <View style={tlStyles.lineSpacer} />
              )}

              {/* Circle */}
              {isCurrent ? (
                <Animated.View style={[circleStyle, { transform: [{ scale: pulseAnim }] }]}>
                  <View style={tlStyles.innerDotCurrent} />
                </Animated.View>
              ) : (
                <View style={circleStyle}>
                  {isCompleted && (
                    <Ionicons name={iconName} size={10} color={Colors.white} />
                  )}
                </View>
              )}

              {/* Bottom connector line */}
              {!isLast ? (
                <View style={[tlStyles.lineSegment, isCompleted ? tlStyles.lineActive : tlStyles.lineInactive]} />
              ) : (
                <View style={tlStyles.lineSpacer} />
              )}
            </View>

            {/* Right: label */}
            <View style={tlStyles.labelCol}>
              <Text
                style={[
                  tlStyles.milestoneName,
                  isCompleted && tlStyles.milestoneNameCompleted,
                  isCurrent  && tlStyles.milestoneNameCurrent,
                  isFuture   && tlStyles.milestoneNameFuture,
                ]}
              >
                {milestone.name || milestone.stage || `Step ${idx + 1}`}
              </Text>
              {isCurrent && (
                <View style={tlStyles.currentBadge}>
                  <Text style={tlStyles.currentBadgeText}>Current</Text>
                </View>
              )}
            </View>
          </View>
        );
      })}
    </View>
  );
}

const tlStyles = StyleSheet.create({
  container: { paddingLeft: Spacing.sm },
  empty: { paddingVertical: Spacing.md },
  emptyText: { ...Typography.bodySmall, color: Colors.textMuted },

  row: { flexDirection: 'row', alignItems: 'stretch', minHeight: 48 },

  lineCol: {
    width: 32,
    alignItems: 'center',
    flexShrink: 0,
  },
  lineSpacer: { flex: 1 },
  lineSegment: {
    flex: 1,
    width: 2,
    minHeight: 10,
  },
  lineActive:   { backgroundColor: Colors.blueprint },
  lineInactive: { backgroundColor: Colors.border },

  circle: {
    width: 22,
    height: 22,
    borderRadius: 11,
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  circleCompleted: {
    backgroundColor: Colors.success,
  },
  circleCurrent: {
    backgroundColor: Colors.blueprint,
    borderWidth: 3,
    borderColor: Colors.blueprint + '55',
    width: 26,
    height: 26,
    borderRadius: 13,
  },
  circleFuture: {
    borderWidth: 2,
    borderColor: Colors.border,
    backgroundColor: 'transparent',
  },
  innerDotCurrent: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: Colors.white,
  },

  labelCol: {
    flex: 1,
    paddingLeft: Spacing.sm,
    paddingVertical: 4,
    justifyContent: 'center',
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
  },
  milestoneName: {
    ...Typography.bodySmall,
    color: Colors.textSecondary,
    flex: 1,
  },
  milestoneNameCompleted: { color: Colors.textSecondary, textDecorationLine: 'none' },
  milestoneNameCurrent:   { color: Colors.textPrimary, fontWeight: '700' },
  milestoneNameFuture:    { color: Colors.textMuted },

  currentBadge: {
    backgroundColor: Colors.blueprint + '33',
    borderWidth: 1,
    borderColor: Colors.blueprint,
    borderRadius: Radii.full,
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  currentBadgeText: {
    fontSize: 9,
    fontWeight: '700',
    color: Colors.blueprint,
    letterSpacing: 0.4,
    textTransform: 'uppercase',
  },
});

// ─── Metric Cell ──────────────────────────────────────────────────────────────

function MetricCell({ label, value }: { label: string; value: string }) {
  return (
    <View style={metricStyles.cell}>
      <Text style={metricStyles.label}>{label}</Text>
      <Text style={metricStyles.value}>{value}</Text>
    </View>
  );
}

const metricStyles = StyleSheet.create({
  cell: {
    flex: 1,
    backgroundColor: Colors.surface,
    borderRadius: Radii.md,
    borderWidth: 1,
    borderColor: Colors.border,
    padding: Spacing.md,
    alignItems: 'center',
    gap: 4,
  },
  label: { ...Typography.caption, color: Colors.textMuted, textAlign: 'center' },
  value: { fontSize: 18, fontWeight: '800', color: Colors.textPrimary, textAlign: 'center' },
});

// ─── Condition Row ────────────────────────────────────────────────────────────

function ConditionRow({ condition }: { condition: Condition }) {
  const sevColor    = SEVERITY_COLORS[condition.severity] ?? Colors.steel;
  const statusColor = COND_STATUS_COLORS[condition.status] ?? Colors.steel;
  const isCleared   = condition.status !== 'Open';

  return (
    <View style={condStyles.row}>
      <View style={condStyles.topRow}>
        <Text style={condStyles.type}>{condition.condition_type}</Text>
        <View style={[condStyles.chip, { backgroundColor: sevColor + '22', borderColor: sevColor }]}>
          <Text style={[condStyles.chipText, { color: sevColor }]}>{condition.severity}</Text>
        </View>
      </View>
      <Text style={[condStyles.desc, isCleared && condStyles.descCleared]}>
        {condition.description}
      </Text>
      <View style={condStyles.statusRow}>
        {isCleared ? (
          <Ionicons name="checkmark-circle" size={14} color={Colors.success} />
        ) : (
          <Ionicons name="alert-circle-outline" size={14} color={Colors.warning} />
        )}
        <View style={[condStyles.statusBadge, { backgroundColor: statusColor + '22', borderColor: statusColor }]}>
          <Text style={[condStyles.statusText, { color: statusColor }]}>{condition.status}</Text>
        </View>
      </View>
    </View>
  );
}

const condStyles = StyleSheet.create({
  row: {
    paddingVertical: Spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: Colors.border,
    gap: 5,
  },
  topRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: Spacing.sm,
  },
  type: {
    ...Typography.label,
    color: Colors.textPrimary,
    flex: 1,
  },
  chip: {
    borderRadius: Radii.full,
    borderWidth: 1,
    paddingHorizontal: Spacing.sm,
    paddingVertical: 2,
  },
  chipText: { fontSize: 10, fontWeight: '700', letterSpacing: 0.3 },
  desc: { ...Typography.bodySmall, color: Colors.textSecondary },
  descCleared: { color: Colors.textMuted, textDecorationLine: 'line-through' },
  statusRow: { flexDirection: 'row', alignItems: 'center', gap: 5, marginTop: 2 },
  statusBadge: {
    borderRadius: Radii.full,
    borderWidth: 1,
    paddingHorizontal: 7,
    paddingVertical: 2,
  },
  statusText: { fontSize: 10, fontWeight: '700', letterSpacing: 0.3 },
});

// ─── Screen ───────────────────────────────────────────────────────────────────

export default function BorrowerLoanDetailScreen({ route, navigation }: any) {
  const { loanId } = route.params as { loanId: number };

  const [data, setData]         = useState<LoanDetailResponse | null>(null);
  const [loading, setLoading]   = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const res = await api.get<LoanDetailResponse>(`/mobile/lending/borrower/loan/${loanId}`);
      setData(res.data);
    } catch {
      // show error state below
    } finally {
      setLoading(false);
    }
  }, [loanId]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchData();
    setRefreshing(false);
  }, [fetchData]);

  // ── Loading ──
  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.centered}>
          <ActivityIndicator size="large" color={Colors.blueprint} />
        </View>
      </SafeAreaView>
    );
  }

  // ── Error / not found ──
  if (!data || !data.loan) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.navBar}>
          <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
            <Ionicons name="chevron-back" size={24} color={Colors.textPrimary} />
            <Text style={styles.backText}>Back</Text>
          </TouchableOpacity>
        </View>
        <View style={styles.centered}>
          <Ionicons name="alert-circle-outline" size={48} color={Colors.danger} />
          <Text style={styles.errorText}>Unable to load loan details.</Text>
        </View>
      </SafeAreaView>
    );
  }

  const { loan, loan_officer, open_conditions, conditions } = data;
  const statusColor  = STATUS_COLORS[loan.status] ?? Colors.steel;
  const milestoneIdx = loan.milestone_index ?? 0;
  const milestones   = loan.milestones ?? [];

  return (
    <SafeAreaView style={styles.container}>
      {/* Nav bar */}
      <View style={styles.navBar}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn} activeOpacity={0.7}>
          <Ionicons name="chevron-back" size={24} color={Colors.textPrimary} />
          <Text style={styles.backText}>Back</Text>
        </TouchableOpacity>
      </View>

      <ScrollView
        contentContainerStyle={styles.scroll}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.blueprint} />
        }
      >
        {/* ── Loan Header Card ── */}
        <View style={styles.headerCard}>
          <View style={styles.headerCardTop}>
            <Text style={styles.propertyAddress} numberOfLines={2}>
              {loan.property_address || 'Property Address'}
            </Text>
            <View style={[styles.statusBadge, { backgroundColor: statusColor + '22', borderColor: statusColor }]}>
              <Text style={[styles.statusText, { color: statusColor }]}>
                {capitalize(loan.status)}
              </Text>
            </View>
          </View>

          <Text style={styles.loanAmount}>{formatCurrency(loan.amount)}</Text>

          <View style={styles.headerMetaRow}>
            <View style={styles.headerMetaItem}>
              <Ionicons name="document-text-outline" size={14} color={Colors.textMuted} />
              <Text style={styles.headerMetaText}>{loan.loan_type || '—'}</Text>
            </View>
            <View style={styles.headerMetaDot} />
            <View style={styles.headerMetaItem}>
              <Ionicons name="trending-up-outline" size={14} color={Colors.textMuted} />
              <Text style={styles.headerMetaText}>{formatPct(loan.rate)} rate</Text>
            </View>
            <View style={styles.headerMetaDot} />
            <View style={styles.headerMetaItem}>
              <Ionicons name="time-outline" size={14} color={Colors.textMuted} />
              <Text style={styles.headerMetaText}>
                {loan.term_months ? `${loan.term_months / 12} yr` : '—'}
              </Text>
            </View>
          </View>

          {/* Progress */}
          <View style={styles.progressSection}>
            <View style={styles.progressLabelRow}>
              <Text style={styles.progressLabel}>{loan.milestone_stage || 'In Progress'}</Text>
              <Text style={styles.progressPct}>{(loan.progress_percent ?? 0).toFixed(0)}%</Text>
            </View>
            <View style={styles.progressTrack}>
              <View style={[styles.progressFill, { width: `${Math.min(loan.progress_percent ?? 0, 100)}%` as any }]} />
            </View>
          </View>
        </View>

        {/* ── Conditions warning banner ── */}
        {(open_conditions ?? 0) > 0 && (
          <View style={styles.conditionsBanner}>
            <Ionicons name="warning" size={16} color={Colors.warning} />
            <Text style={styles.conditionsBannerText}>
              {open_conditions} open condition{open_conditions !== 1 ? 's' : ''} require your attention
            </Text>
          </View>
        )}

        {/* ── Milestone Timeline ── */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Ionicons name="git-branch-outline" size={16} color={Colors.blueprint} />
            <Text style={styles.sectionTitle}>Loan Milestones</Text>
          </View>
          <MilestoneTimeline milestones={milestones} currentIndex={milestoneIdx} />
        </View>

        {/* ── Key Metrics 2x2 grid ── */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Ionicons name="stats-chart-outline" size={16} color={Colors.blueprint} />
            <Text style={styles.sectionTitle}>Key Metrics</Text>
          </View>
          <View style={styles.metricsGrid}>
            <View style={styles.metricsRow}>
              <MetricCell label="LTV" value={formatPct(loan.ltv)} />
              <MetricCell label="Front DTI" value={formatPct(loan.front_end_dti)} />
            </View>
            <View style={styles.metricsRow}>
              <MetricCell label="Back DTI" value={formatPct(loan.back_end_dti)} />
              <MetricCell label="Property Value" value={loan.property_value ? formatCurrency(loan.property_value) : '—'} />
            </View>
          </View>
        </View>

        {/* ── AI Summary ── */}
        {!!loan.ai_summary && (
          <View style={styles.aiCard}>
            <View style={styles.aiCardHeader}>
              <Ionicons name="sparkles" size={16} color={Colors.info} />
              <Text style={styles.aiCardTitle}>AI Summary</Text>
            </View>
            <Text style={styles.aiCardText}>{loan.ai_summary}</Text>
          </View>
        )}

        {/* ── Conditions ── */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Ionicons name="shield-checkmark-outline" size={16} color={Colors.blueprint} />
            <Text style={styles.sectionTitle}>Conditions</Text>
            {(open_conditions ?? 0) > 0 && (
              <View style={styles.condCountBadge}>
                <Text style={styles.condCountText}>{open_conditions} open</Text>
              </View>
            )}
          </View>

          {!conditions || conditions.length === 0 ? (
            <View style={styles.emptyInline}>
              <Ionicons name="checkmark-done-circle-outline" size={28} color={Colors.success} />
              <Text style={styles.emptyInlineText}>All conditions cleared</Text>
            </View>
          ) : (
            <View>
              {conditions.map(c => (
                <ConditionRow key={c.id} condition={c} />
              ))}
            </View>
          )}
        </View>

        {/* ── Loan Officer ── */}
        {!!loan_officer && (
          <View style={styles.section}>
            <View style={styles.sectionHeader}>
              <Ionicons name="person-circle-outline" size={16} color={Colors.blueprint} />
              <Text style={styles.sectionTitle}>Your Loan Officer</Text>
            </View>

            <View style={styles.loCard}>
              <View style={styles.loAvatar}>
                <Ionicons name="person" size={24} color={Colors.blueprint} />
              </View>
              <View style={styles.loInfo}>
                <Text style={styles.loName}>{loan_officer.name}</Text>
                {!!loan_officer.email && (
                  <Text style={styles.loContact}>{loan_officer.email}</Text>
                )}
                {!!loan_officer.phone && (
                  <Text style={styles.loContact}>{loan_officer.phone}</Text>
                )}
              </View>
            </View>

            <View style={styles.loActions}>
              {!!loan_officer.phone && (
                <TouchableOpacity
                  style={[styles.loActionBtn, styles.loActionBtnCall]}
                  onPress={() => Linking.openURL(`tel:${loan_officer.phone}`)}
                  activeOpacity={0.75}
                >
                  <Ionicons name="call-outline" size={16} color={Colors.success} />
                  <Text style={[styles.loActionText, { color: Colors.success }]}>Call</Text>
                </TouchableOpacity>
              )}
              {!!loan_officer.email && (
                <TouchableOpacity
                  style={[styles.loActionBtn, styles.loActionBtnEmail]}
                  onPress={() => Linking.openURL(`mailto:${loan_officer.email}`)}
                  activeOpacity={0.75}
                >
                  <Ionicons name="mail-outline" size={16} color={Colors.info} />
                  <Text style={[styles.loActionText, { color: Colors.info }]}>Email</Text>
                </TouchableOpacity>
              )}
              <TouchableOpacity
                style={[styles.loActionBtn, styles.loActionBtnMsg]}
                onPress={() => navigation.navigate('Messages')}
                activeOpacity={0.75}
              >
                <Ionicons name="chatbubble-outline" size={16} color={Colors.blueprint} />
                <Text style={[styles.loActionText, { color: Colors.blueprint }]}>Message</Text>
              </TouchableOpacity>
            </View>
          </View>
        )}

        {/* Upload docs FAB-style footer button */}
        <TouchableOpacity
          style={styles.uploadBtn}
          onPress={() => navigation.navigate('DocumentUpload', { loanId: loan.id, loanNumber: loan.id })}
          activeOpacity={0.85}
        >
          <Ionicons name="cloud-upload-outline" size={18} color={Colors.white} />
          <Text style={styles.uploadBtnText}>Upload Documents</Text>
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  centered:  { flex: 1, alignItems: 'center', justifyContent: 'center', gap: Spacing.md },
  errorText: { ...Typography.body, color: Colors.danger },

  // Nav
  navBar: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
  },
  backBtn: { flexDirection: 'row', alignItems: 'center', gap: 2 },
  backText: { ...Typography.body, color: Colors.textPrimary },

  // Scroll
  scroll: { padding: Spacing.lg, paddingBottom: Spacing.xxl },

  // Header card
  headerCard: {
    backgroundColor: Colors.surface,
    borderRadius: Radii.lg,
    borderWidth: 1,
    borderColor: Colors.border,
    padding: Spacing.md,
    marginBottom: Spacing.md,
    gap: Spacing.sm,
  },
  headerCardTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: Spacing.sm,
  },
  propertyAddress: {
    ...Typography.h3,
    color: Colors.textPrimary,
    flex: 1,
  },
  statusBadge: {
    borderWidth: 1,
    borderRadius: Radii.full,
    paddingHorizontal: Spacing.sm,
    paddingVertical: 3,
    flexShrink: 0,
  },
  statusText: { ...Typography.caption, fontWeight: '700', textTransform: 'uppercase' },
  loanAmount: {
    fontSize: 32,
    fontWeight: '800',
    color: Colors.blueprint,
  },
  headerMetaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: Spacing.xs,
  },
  headerMetaItem: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  headerMetaText: { ...Typography.caption, color: Colors.textSecondary },
  headerMetaDot: {
    width: 3,
    height: 3,
    borderRadius: 1.5,
    backgroundColor: Colors.border,
  },

  // Progress
  progressSection: { gap: 5 },
  progressLabelRow: { flexDirection: 'row', justifyContent: 'space-between' },
  progressLabel:    { ...Typography.caption, color: Colors.textSecondary },
  progressPct:      { ...Typography.caption, color: Colors.blueprint, fontWeight: '700' },
  progressTrack: {
    height: 6,
    backgroundColor: Colors.border,
    borderRadius: 3,
    overflow: 'hidden',
  },
  progressFill: { height: 6, backgroundColor: Colors.blueprint, borderRadius: 3 },

  // Conditions banner
  conditionsBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
    backgroundColor: Colors.warning + '18',
    borderWidth: 1,
    borderColor: Colors.warning + '55',
    borderRadius: Radii.md,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    marginBottom: Spacing.md,
  },
  conditionsBannerText: {
    ...Typography.bodySmall,
    color: Colors.warning,
    fontWeight: '600',
    flex: 1,
  },

  // Section
  section: {
    backgroundColor: Colors.surface,
    borderRadius: Radii.lg,
    borderWidth: 1,
    borderColor: Colors.border,
    padding: Spacing.md,
    marginBottom: Spacing.md,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
    marginBottom: Spacing.md,
  },
  sectionTitle: {
    ...Typography.label,
    color: Colors.textMuted,
    flex: 1,
  },
  condCountBadge: {
    backgroundColor: Colors.warning + '22',
    borderWidth: 1,
    borderColor: Colors.warning,
    borderRadius: Radii.full,
    paddingHorizontal: Spacing.sm,
    paddingVertical: 2,
  },
  condCountText: { fontSize: 10, fontWeight: '700', color: Colors.warning },

  // Metrics grid
  metricsGrid: { gap: Spacing.sm },
  metricsRow:  { flexDirection: 'row', gap: Spacing.sm },

  // AI summary card
  aiCard: {
    backgroundColor: Colors.info + '18',
    borderWidth: 1,
    borderColor: Colors.info + '44',
    borderRadius: Radii.lg,
    padding: Spacing.md,
    marginBottom: Spacing.md,
    gap: Spacing.sm,
  },
  aiCardHeader: { flexDirection: 'row', alignItems: 'center', gap: Spacing.xs },
  aiCardTitle:  { ...Typography.label, color: Colors.info },
  aiCardText:   { ...Typography.bodySmall, color: Colors.textSecondary, lineHeight: 22 },

  // Empty inline
  emptyInline: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    paddingVertical: Spacing.sm,
  },
  emptyInlineText: { ...Typography.bodySmall, color: Colors.success },

  // Loan officer
  loCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
    marginBottom: Spacing.md,
  },
  loAvatar: {
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: Colors.blueprint + '22',
    borderWidth: 1,
    borderColor: Colors.blueprint,
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  loInfo: { flex: 1, gap: 3 },
  loName: { ...Typography.body, fontWeight: '700', color: Colors.textPrimary },
  loContact: { ...Typography.caption, color: Colors.textSecondary },
  loActions: { flexDirection: 'row', gap: Spacing.sm },
  loActionBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.xs,
    paddingVertical: Spacing.sm,
    borderRadius: Radii.md,
    borderWidth: 1,
  },
  loActionBtnCall:  { borderColor: Colors.success,   backgroundColor: Colors.success  + '18' },
  loActionBtnEmail: { borderColor: Colors.info,      backgroundColor: Colors.info     + '18' },
  loActionBtnMsg:   { borderColor: Colors.blueprint, backgroundColor: Colors.blueprint + '18' },
  loActionText: { ...Typography.caption, fontWeight: '700' },

  // Upload button
  uploadBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.sm,
    backgroundColor: Colors.blueprint,
    borderRadius: Radii.md,
    paddingVertical: Spacing.md,
    marginTop: Spacing.sm,
  },
  uploadBtnText: {
    ...Typography.label,
    color: Colors.white,
    fontSize: 15,
  },
});
