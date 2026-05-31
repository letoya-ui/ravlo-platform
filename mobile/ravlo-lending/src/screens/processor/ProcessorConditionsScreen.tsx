import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
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
type Severity = 'Low' | 'Standard' | 'High';

interface Condition {
  id: number;
  condition_type: string;
  description: string;
  severity: Severity;
  loan_address: string;
  status: ConditionStatus;
  cleared_at?: string | null;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const FILTER_OPTIONS = ['Open', 'Cleared', 'Waived', 'All'] as const;
type FilterOption = (typeof FILTER_OPTIONS)[number];

const SEVERITY_COLORS: Record<Severity, string> = {
  Low:      Colors.success,
  Standard: Colors.info,
  High:     Colors.danger,
};

const STATUS_COLORS: Record<ConditionStatus, string> = {
  Open:    Colors.warning,
  Cleared: Colors.success,
  Waived:  Colors.steel,
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatDate(dateStr: string): string {
  if (!dateStr) return '';
  return new Date(dateStr).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

// ─── Condition Card ───────────────────────────────────────────────────────────

interface ConditionCardProps {
  condition: Condition;
  onAction: (id: number, action: 'Clear' | 'Waive') => void;
  actionPending: boolean;
}

function ConditionCard({ condition, onAction, actionPending }: ConditionCardProps) {
  const severityColor = SEVERITY_COLORS[condition.severity] ?? Colors.steel;
  const statusColor   = STATUS_COLORS[condition.status]   ?? Colors.steel;
  const isOpen        = condition.status === 'Open';

  return (
    <View style={cardStyles.card}>
      {/* Top row — type + severity chip */}
      <View style={cardStyles.topRow}>
        <Text style={cardStyles.conditionType} numberOfLines={1}>
          {condition.condition_type}
        </Text>
        <View style={[cardStyles.chip, { backgroundColor: severityColor + '22', borderColor: severityColor }]}>
          <Text style={[cardStyles.chipText, { color: severityColor }]}>
            {condition.severity}
          </Text>
        </View>
      </View>

      {/* Description */}
      <Text style={cardStyles.description} numberOfLines={2}>
        {condition.description}
      </Text>

      {/* Address row */}
      <View style={cardStyles.addressRow}>
        <Ionicons name="location-outline" size={12} color={Colors.textMuted} />
        <Text style={cardStyles.addressText} numberOfLines={1}>
          {condition.loan_address}
        </Text>
      </View>

      {/* Divider */}
      <View style={cardStyles.divider} />

      {/* Bottom row — status badge + cleared date + actions */}
      <View style={cardStyles.bottomRow}>
        {/* Status badge */}
        <View style={[cardStyles.statusBadge, { backgroundColor: statusColor + '22', borderColor: statusColor }]}>
          <Text style={[cardStyles.statusText, { color: statusColor }]}>
            {condition.status}
          </Text>
        </View>

        {/* Cleared date */}
        {condition.cleared_at ? (
          <View style={cardStyles.clearedBlock}>
            <Ionicons name="checkmark-circle-outline" size={12} color={Colors.success} />
            <Text style={cardStyles.clearedDate}>{formatDate(condition.cleared_at)}</Text>
          </View>
        ) : null}

        <View style={{ flex: 1 }} />

        {/* Action buttons (Open conditions only) */}
        {isOpen && (
          <View style={cardStyles.actionRow}>
            <TouchableOpacity
              style={[cardStyles.actionBtn, cardStyles.clearBtn]}
              onPress={() => onAction(condition.id, 'Clear')}
              disabled={actionPending}
              activeOpacity={0.75}
            >
              {actionPending ? (
                <ActivityIndicator size="small" color={Colors.success} />
              ) : (
                <Text style={[cardStyles.actionBtnText, { color: Colors.success }]}>Clear</Text>
              )}
            </TouchableOpacity>
            <TouchableOpacity
              style={[cardStyles.actionBtn, cardStyles.waiveBtn]}
              onPress={() => onAction(condition.id, 'Waive')}
              disabled={actionPending}
              activeOpacity={0.75}
            >
              <Text style={[cardStyles.actionBtnText, { color: Colors.textSecondary }]}>Waive</Text>
            </TouchableOpacity>
          </View>
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
  },
  topRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: Spacing.sm,
  },
  conditionType: {
    ...Typography.label,
    color: Colors.textPrimary,
    flex: 1,
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
  description: {
    ...Typography.bodySmall,
    color: Colors.textSecondary,
    marginTop: Spacing.xs,
    lineHeight: 20,
  },
  addressRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: Spacing.sm,
    gap: 3,
  },
  addressText: {
    ...Typography.caption,
    color: Colors.textMuted,
    flex: 1,
  },
  divider: {
    height: 1,
    backgroundColor: Colors.border,
    marginVertical: Spacing.sm,
  },
  bottomRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
  },
  statusBadge: {
    borderRadius: Radii.full,
    borderWidth: 1,
    paddingHorizontal: Spacing.sm,
    paddingVertical: 2,
  },
  statusText: {
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 0.3,
  },
  clearedBlock: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 3,
  },
  clearedDate: {
    ...Typography.caption,
    color: Colors.success,
  },
  actionRow: {
    flexDirection: 'row',
    gap: Spacing.sm,
  },
  actionBtn: {
    paddingHorizontal: Spacing.sm,
    paddingVertical: 5,
    borderRadius: Radii.sm,
    borderWidth: 1,
    minWidth: 54,
    alignItems: 'center',
  },
  clearBtn: {
    borderColor: Colors.success,
    backgroundColor: Colors.success + '1A',
  },
  waiveBtn: {
    borderColor: Colors.border,
    backgroundColor: Colors.surfaceElevated,
  },
  actionBtnText: {
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 0.3,
  },
});

// ─── Empty State ──────────────────────────────────────────────────────────────

interface EmptyStateProps {
  filter: FilterOption;
}

function EmptyState({ filter }: EmptyStateProps) {
  const label = filter === 'All' ? 'conditions' : `${filter.toLowerCase()} conditions`;
  return (
    <View style={emptyStyles.container}>
      <Ionicons name="checkmark-done-circle-outline" size={52} color={Colors.textMuted} />
      <Text style={emptyStyles.title}>No {label}</Text>
      <Text style={emptyStyles.subtitle}>
        {filter === 'Open'
          ? 'All conditions have been addressed.'
          : `No ${label} found for current loans.`}
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

export default function ProcessorConditionsScreen() {
  const [conditions, setConditions]   = useState<Condition[]>([]);
  const [filter, setFilter]           = useState<FilterOption>('Open');
  const [loading, setLoading]         = useState(false);
  const [refreshing, setRefreshing]   = useState(false);
  const [pendingId, setPendingId]     = useState<number | null>(null);

  const fetchConditions = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (filter !== 'All') params.status = filter;

      const res = await api.get('/mobile/lending/processor/conditions', { params });
      const data: Condition[] = res.data.conditions ?? res.data ?? [];
      setConditions(data);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    fetchConditions();
  }, [fetchConditions]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchConditions();
    setRefreshing(false);
  }, [fetchConditions]);

  const handleAction = useCallback(
    (id: number, action: 'Clear' | 'Waive') => {
      const newStatus = action === 'Clear' ? 'Cleared' : 'Waived';

      Alert.prompt(
        `${action} Condition`,
        `Add notes for ${newStatus.toLowerCase()} this condition (optional):`,
        async (notes: string | undefined) => {
          setPendingId(id);
          try {
            await api.post(`/mobile/lending/processor/conditions/${id}`, {
              status: newStatus,
              notes: notes ?? '',
            });
            // Optimistically update local state
            setConditions(prev =>
              prev.map(c =>
                c.id === id
                  ? {
                      ...c,
                      status: newStatus as ConditionStatus,
                      cleared_at: new Date().toISOString(),
                    }
                  : c
              )
            );
          } catch {
            Alert.alert(
              'Error',
              `Failed to ${action.toLowerCase()} condition. Please try again.`
            );
          } finally {
            setPendingId(null);
          }
        },
        'plain-text',
        '',
        'default'
      );
    },
    []
  );

  const openCount = conditions.filter(c => c.status === 'Open').length;

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <View>
          <Text style={styles.title}>Conditions</Text>
          <Text style={styles.subtitle}>
            {conditions.length} total
            {filter === 'Open' && openCount > 0
              ? ` · ${openCount} open`
              : ''}
          </Text>
        </View>
        <View style={styles.headerIcon}>
          <Ionicons name="shield-checkmark-outline" size={22} color={Colors.blueprint} />
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

      {/* Conditions list */}
      <FlatList
        data={conditions}
        keyExtractor={c => String(c.id)}
        contentContainerStyle={[
          styles.listContent,
          conditions.length === 0 && styles.listEmpty,
        ]}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor={Colors.blueprint}
          />
        }
        ListEmptyComponent={!loading ? <EmptyState filter={filter} /> : null}
        ListFooterComponent={
          loading && !refreshing
            ? <ActivityIndicator color={Colors.blueprint} style={styles.loader} />
            : null
        }
        renderItem={({ item }) => (
          <ConditionCard
            condition={item}
            onAction={handleAction}
            actionPending={pendingId === item.id}
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
