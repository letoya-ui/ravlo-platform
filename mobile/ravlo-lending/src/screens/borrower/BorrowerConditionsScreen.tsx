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

type ConditionStatus = 'Open' | 'Cleared' | 'Waived';
type ConditionSeverity = 'Low' | 'Standard' | 'High';

interface Condition {
  id: number;
  condition_type: string;
  description: string;
  severity: ConditionSeverity;
  status: ConditionStatus;
}

type FilterOption = 'All' | 'Open' | 'Cleared';
const FILTER_OPTIONS: FilterOption[] = ['All', 'Open', 'Cleared'];

// ─── Constants ────────────────────────────────────────────────────────────────

const SEVERITY_COLORS: Record<ConditionSeverity, string> = {
  Low:      Colors.success,
  Standard: Colors.info,
  High:     Colors.danger,
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

function severityColor(sev: ConditionSeverity): string {
  return SEVERITY_COLORS[sev] ?? Colors.steel;
}

// ─── Progress Bar (Summary) ───────────────────────────────────────────────────

interface SummaryBarProps {
  cleared: number;
  total: number;
}

function SummaryBar({ cleared, total }: SummaryBarProps) {
  const pct = total > 0 ? Math.round((cleared / total) * 100) : 0;
  const allClear = cleared === total && total > 0;

  return (
    <View style={summaryStyles.container}>
      <View style={summaryStyles.textRow}>
        <View style={summaryStyles.textLeft}>
          {allClear ? (
            <Ionicons name="checkmark-done-circle" size={16} color={Colors.success} />
          ) : (
            <Ionicons name="shield-half-outline" size={16} color={Colors.blueprint} />
          )}
          <Text style={[summaryStyles.label, allClear && summaryStyles.labelClear]}>
            {cleared} of {total} conditions cleared
          </Text>
        </View>
        <Text style={[summaryStyles.pct, allClear && summaryStyles.pctClear]}>{pct}%</Text>
      </View>
      <View style={summaryStyles.track}>
        <View
          style={[
            summaryStyles.fill,
            { width: `${pct}%` as any },
            allClear && summaryStyles.fillClear,
          ]}
        />
      </View>
    </View>
  );
}

const summaryStyles = StyleSheet.create({
  container: {
    backgroundColor: Colors.surface,
    borderRadius: Radii.lg,
    borderWidth: 1,
    borderColor: Colors.border,
    padding: Spacing.md,
    marginHorizontal: Spacing.lg,
    marginBottom: Spacing.sm,
    gap: Spacing.sm,
  },
  textRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  textLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
    flex: 1,
  },
  label: {
    ...Typography.bodySmall,
    color: Colors.textSecondary,
    flex: 1,
  },
  labelClear: { color: Colors.success },
  pct: {
    ...Typography.label,
    color: Colors.blueprint,
  },
  pctClear: { color: Colors.success },
  track: {
    height: 8,
    backgroundColor: Colors.border,
    borderRadius: 4,
    overflow: 'hidden',
  },
  fill: {
    height: 8,
    backgroundColor: Colors.blueprint,
    borderRadius: 4,
  },
  fillClear: { backgroundColor: Colors.success },
});

// ─── Condition Card ───────────────────────────────────────────────────────────

interface ConditionCardProps {
  condition: Condition;
  onUpload: (conditionId: number) => void;
}

function ConditionCard({ condition, onUpload }: ConditionCardProps) {
  const sev       = condition.severity as ConditionSeverity;
  const sevColor  = severityColor(sev);
  const isOpen    = condition.status === 'Open';
  const isCleared = condition.status === 'Cleared';

  const statusColor = isOpen    ? Colors.warning
                    : isCleared ? Colors.success
                    : Colors.steel;

  return (
    <View style={[cardStyles.card, !isOpen && cardStyles.cardDimmed]}>
      {/* Top row: type + severity chip */}
      <View style={cardStyles.topRow}>
        <Text
          style={[cardStyles.type, !isOpen && cardStyles.typeCleared]}
          numberOfLines={1}
        >
          {condition.condition_type}
        </Text>
        <View style={[cardStyles.chip, { backgroundColor: sevColor + '22', borderColor: sevColor }]}>
          <Text style={[cardStyles.chipText, { color: sevColor }]}>
            {condition.severity}
          </Text>
        </View>
      </View>

      {/* Description */}
      <Text style={[cardStyles.desc, !isOpen && cardStyles.descCleared]}>
        {condition.description}
      </Text>

      {/* Status row */}
      <View style={cardStyles.statusRow}>
        {isOpen ? (
          <Ionicons name="alert-circle-outline" size={14} color={Colors.warning} />
        ) : (
          <Ionicons name="checkmark-circle" size={14} color={Colors.success} />
        )}
        <View style={[cardStyles.statusBadge, { backgroundColor: statusColor + '22', borderColor: statusColor }]}>
          <Text style={[cardStyles.statusText, { color: statusColor }]}>
            {condition.status}
          </Text>
        </View>
        <View style={{ flex: 1 }} />

        {/* Upload button for open conditions */}
        {isOpen && (
          <TouchableOpacity
            style={cardStyles.uploadBtn}
            onPress={() => onUpload(condition.id)}
            activeOpacity={0.75}
          >
            <Ionicons name="cloud-upload-outline" size={13} color={Colors.blueprint} />
            <Text style={cardStyles.uploadBtnText}>Upload Doc</Text>
          </TouchableOpacity>
        )}
      </View>
    </View>
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
    gap: Spacing.sm,
  },
  cardDimmed: {
    opacity: 0.7,
  },
  topRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: Spacing.sm,
  },
  type: {
    ...Typography.label,
    color: Colors.textPrimary,
    flex: 1,
  },
  typeCleared: {
    textDecorationLine: 'line-through',
    color: Colors.textMuted,
  },
  chip: {
    borderRadius: Radii.full,
    borderWidth: 1,
    paddingHorizontal: Spacing.sm,
    paddingVertical: 2,
    flexShrink: 0,
  },
  chipText: {
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 0.3,
  },
  desc: {
    ...Typography.bodySmall,
    color: Colors.textSecondary,
    lineHeight: 20,
  },
  descCleared: {
    color: Colors.textMuted,
    textDecorationLine: 'line-through',
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
  },
  statusBadge: {
    borderRadius: Radii.full,
    borderWidth: 1,
    paddingHorizontal: 7,
    paddingVertical: 2,
  },
  statusText: {
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 0.3,
  },
  uploadBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: Colors.blueprint + '22',
    borderWidth: 1,
    borderColor: Colors.blueprint,
    borderRadius: Radii.sm,
    paddingHorizontal: Spacing.sm,
    paddingVertical: 4,
  },
  uploadBtnText: {
    fontSize: 11,
    fontWeight: '700',
    color: Colors.blueprint,
    letterSpacing: 0.2,
  },
});

// ─── Empty State ──────────────────────────────────────────────────────────────

function EmptyState({ filter }: { filter: FilterOption }) {
  const messages: Record<FilterOption, { icon: any; title: string; sub: string }> = {
    All:     { icon: 'checkmark-done-circle-outline', title: 'No Conditions',          sub: 'You have no conditions on your loan.'            },
    Open:    { icon: 'checkmark-circle-outline',      title: 'All Conditions Cleared', sub: 'Great job — no open conditions remaining.'       },
    Cleared: { icon: 'time-outline',                  title: 'Nothing Cleared Yet',    sub: 'Cleared conditions will appear here.'            },
  };
  const { icon, title, sub } = messages[filter];

  return (
    <View style={emptyStyles.container}>
      <Ionicons name={icon} size={52} color={Colors.textMuted} />
      <Text style={emptyStyles.title}>{title}</Text>
      <Text style={emptyStyles.sub}>{sub}</Text>
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
    paddingHorizontal: Spacing.xl,
  },
  title: { ...Typography.body, color: Colors.textSecondary, fontWeight: '600', marginTop: Spacing.sm },
  sub:   { ...Typography.bodySmall, color: Colors.textMuted, textAlign: 'center' },
});

// ─── Screen ───────────────────────────────────────────────────────────────────

export default function BorrowerConditionsScreen({ navigation }: any) {
  const [conditions, setConditions]     = useState<Condition[]>([]);
  const [filter, setFilter]             = useState<FilterOption>('All');
  const [loading, setLoading]           = useState(true);
  const [refreshing, setRefreshing]     = useState(false);
  const [activeLoanId, setActiveLoanId] = useState<number | null>(null);

  // Fetch dashboard first to find the active loan, then load its conditions.
  const fetchConditions = useCallback(async () => {
    setLoading(true);
    try {
      // Step 1 — get loan IDs from dashboard
      const dashRes = await api.get('/mobile/lending/borrower/dashboard');
      const loans: Array<{ id: number }> = dashRes.data?.loans ?? [];

      if (loans.length === 0) {
        setConditions([]);
        setActiveLoanId(null);
        setLoading(false);
        return;
      }

      const loanId = loans[0].id;
      setActiveLoanId(loanId);

      // Step 2 — fetch full loan detail for conditions
      const loanRes = await api.get(`/mobile/lending/borrower/loan/${loanId}`);
      const allConditions: Condition[] = loanRes.data?.conditions ?? [];
      setConditions(allConditions);
    } catch {
      // fail silently — show empty state
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchConditions(); }, [fetchConditions]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchConditions();
    setRefreshing(false);
  }, [fetchConditions]);

  const handleUpload = useCallback((conditionId: number) => {
    navigation.navigate('DocumentUpload', {
      loanId: activeLoanId,
      loanNumber: activeLoanId,
      conditionId,
    });
  }, [navigation, activeLoanId]);

  // Derived values
  const totalCount   = conditions.length;
  const clearedCount = conditions.filter(c => c.status === 'Cleared' || c.status === 'Waived').length;
  const openCount    = conditions.filter(c => c.status === 'Open').length;

  const filtered = filter === 'All'
    ? conditions
    : filter === 'Open'
    ? conditions.filter(c => c.status === 'Open')
    : conditions.filter(c => c.status === 'Cleared' || c.status === 'Waived');

  // ── Loading ──
  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.centered}>
          <ActivityIndicator size="large" color={Colors.blueprint} />
          <Text style={styles.loadingText}>Loading conditions...</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <Text style={styles.headerTitle}>My Conditions</Text>
          <Text style={styles.headerSub}>
            {openCount > 0
              ? `${openCount} open · ${clearedCount} cleared`
              : totalCount > 0
              ? 'All conditions cleared'
              : 'No conditions'}
          </Text>
        </View>
        <View style={[
          styles.countBadge,
          openCount > 0 ? styles.countBadgeWarning : styles.countBadgeSuccess,
        ]}>
          <Text style={[
            styles.countBadgeText,
            openCount > 0 ? styles.countBadgeTextWarning : styles.countBadgeTextSuccess,
          ]}>
            {totalCount}
          </Text>
        </View>
      </View>

      {/* Summary progress bar */}
      {totalCount > 0 && (
        <SummaryBar cleared={clearedCount} total={totalCount} />
      )}

      {/* Filter chips */}
      <View style={styles.filterRow}>
        {FILTER_OPTIONS.map(opt => {
          const count =
            opt === 'All'     ? totalCount
            : opt === 'Open'  ? openCount
            : clearedCount;

          return (
            <TouchableOpacity
              key={opt}
              style={[styles.filterChip, filter === opt && styles.filterChipActive]}
              onPress={() => setFilter(opt)}
              activeOpacity={0.75}
            >
              <Text style={[styles.filterText, filter === opt && styles.filterTextActive]}>
                {opt}
              </Text>
              {count > 0 && (
                <View style={[styles.filterCount, filter === opt && styles.filterCountActive]}>
                  <Text style={[styles.filterCountText, filter === opt && styles.filterCountTextActive]}>
                    {count}
                  </Text>
                </View>
              )}
            </TouchableOpacity>
          );
        })}
      </View>

      {/* Conditions list */}
      <FlatList
        data={filtered}
        keyExtractor={c => String(c.id)}
        contentContainerStyle={[
          styles.listContent,
          filtered.length === 0 && styles.listEmpty,
        ]}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor={Colors.blueprint}
          />
        }
        ListEmptyComponent={!loading ? <EmptyState filter={filter} /> : null}
        renderItem={({ item }) => (
          <ConditionCard condition={item} onUpload={handleUpload} />
        )}
      />
    </SafeAreaView>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  centered: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.sm,
  },
  loadingText: { ...Typography.bodySmall, color: Colors.textMuted },

  // Header
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.md,
    paddingBottom: Spacing.sm,
  },
  headerLeft: { flex: 1 },
  headerTitle: { ...Typography.h2, color: Colors.textPrimary },
  headerSub:   { ...Typography.caption, color: Colors.textMuted, marginTop: 2 },

  countBadge: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
  },
  countBadgeWarning: {
    backgroundColor: Colors.warning + '22',
    borderColor: Colors.warning,
  },
  countBadgeSuccess: {
    backgroundColor: Colors.success + '22',
    borderColor: Colors.success,
  },
  countBadgeText: {
    fontSize: 16,
    fontWeight: '800',
  },
  countBadgeTextWarning: { color: Colors.warning },
  countBadgeTextSuccess: { color: Colors.success },

  // Filter
  filterRow: {
    flexDirection: 'row',
    paddingHorizontal: Spacing.lg,
    paddingBottom: Spacing.sm,
    gap: Spacing.sm,
  },
  filterChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: Spacing.md,
    paddingVertical: 7,
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
    fontWeight: '600',
  },
  filterTextActive: { color: Colors.white },
  filterCount: {
    minWidth: 18,
    height: 18,
    borderRadius: 9,
    backgroundColor: Colors.border,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 4,
  },
  filterCountActive: { backgroundColor: Colors.white + '33' },
  filterCountText: {
    fontSize: 9,
    fontWeight: '800',
    color: Colors.textMuted,
  },
  filterCountTextActive: { color: Colors.white },

  // List
  listContent: {
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.xs,
    paddingBottom: Spacing.xl,
  },
  listEmpty: { flexGrow: 1 },
});
