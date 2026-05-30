import React, { useEffect, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, RefreshControl, TouchableOpacity,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radii, Typography } from '../theme';
import { useAuthStore } from '../store/authStore';
import { useProgressStore } from '../store/progressStore';
import { MODULES, canAccessModule } from '../data/modules';

export default function ProgressScreen({ navigation }: any) {
  const { user } = useAuthStore();
  const { load, loaded, completed, moduleProgress } = useProgressStore();
  const [refreshing, setRefreshing] = React.useState(false);
  const tier = user?.university_tier || null;

  useEffect(() => {
    if (!loaded) load();
  }, []);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  }, []);

  const accessibleModules = MODULES.filter(m => canAccessModule(tier, m.id));
  const totalLessons = accessibleModules.reduce((a, m) => a + m.lessons.length, 0);
  const totalCompleted = completed.filter(c =>
    accessibleModules.some(m => m.id === c.module_id)
  ).length;
  const overallPct = totalLessons > 0 ? Math.round((totalCompleted / totalLessons) * 100) : 0;

  const completedModules = accessibleModules.filter(m => moduleProgress(m.id, m.lessons.length) === 100).length;
  const inProgressModules = accessibleModules.filter(m => {
    const p = moduleProgress(m.id, m.lessons.length);
    return p > 0 && p < 100;
  }).length;

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>My Progress</Text>
      </View>

      <ScrollView
        contentContainerStyle={styles.scroll}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.blueprint} />}
        showsVerticalScrollIndicator={false}
      >
        {/* Summary stats */}
        <View style={styles.statsRow}>
          <StatCard value={totalCompleted} label={'Lessons\nDone'} color={Colors.success} icon="checkmark-circle-outline" />
          <StatCard value={completedModules} label={'Modules\nComplete'} color={Colors.blueprint} icon="trophy-outline" />
          <StatCard value={inProgressModules} label={'In\nProgress'} color={Colors.warning} icon="time-outline" />
        </View>

        {/* Overall */}
        <View style={styles.overallCard}>
          <View style={styles.overallTop}>
            <Text style={styles.overallTitle}>Overall Completion</Text>
            <Text style={styles.overallPct}>{overallPct}%</Text>
          </View>
          <View style={styles.progressBarBg}>
            <View style={[styles.progressBarFill, { width: `${overallPct}%` }]} />
          </View>
          <Text style={styles.overallSub}>{totalCompleted} of {totalLessons} lessons across {accessibleModules.length} modules</Text>
        </View>

        {/* Per-module breakdown */}
        <Text style={styles.sectionTitle}>Module Breakdown</Text>
        {MODULES.map(m => {
          const accessible = canAccessModule(tier, m.id);
          const p = moduleProgress(m.id, m.lessons.length);
          const doneLessons = Math.round((p / 100) * m.lessons.length);

          return (
            <TouchableOpacity
              key={m.id}
              style={[styles.moduleCard, !accessible && styles.moduleCardLocked]}
              onPress={() => accessible && navigation.navigate('Learn', { screen: 'ModuleDetail', params: { moduleId: m.id } })}
              activeOpacity={accessible ? 0.75 : 1}
            >
              <View style={styles.moduleTop}>
                <View style={[styles.moduleIcon, { backgroundColor: m.color + (accessible ? '22' : '11') }]}>
                  <Ionicons name={m.icon as any} size={18} color={accessible ? m.color : Colors.textMuted} />
                </View>
                <View style={styles.moduleInfo}>
                  <Text style={[styles.moduleTitle, !accessible && styles.lockedTitle]}>{m.title}</Text>
                  <Text style={styles.moduleSub}>
                    {accessible ? `${doneLessons}/${m.lessons.length} lessons` : 'Locked — upgrade to access'}
                  </Text>
                </View>
                {accessible ? (
                  p === 100 ? (
                    <Ionicons name="trophy" size={18} color={Colors.success} />
                  ) : (
                    <Text style={[styles.modulePct, { color: m.color }]}>{p}%</Text>
                  )
                ) : (
                  <Ionicons name="lock-closed-outline" size={16} color={Colors.textMuted} />
                )}
              </View>

              {accessible && (
                <View style={styles.moduleProgressRow}>
                  <View style={[styles.progressBarBg, { flex: 1 }]}>
                    <View style={[styles.progressBarFill, { width: `${p}%`, backgroundColor: m.color }]} />
                  </View>
                  {p === 100 && (
                    <View style={styles.completeBadge}>
                      <Text style={styles.completeBadgeText}>Complete</Text>
                    </View>
                  )}
                </View>
              )}

              {accessible && p > 0 && p < 100 && (
                <Text style={styles.resumeHint}>Tap to continue →</Text>
              )}
            </TouchableOpacity>
          );
        })}
      </ScrollView>
    </SafeAreaView>
  );
}

function StatCard({ value, label, color, icon }: { value: number; label: string; color: string; icon: any }) {
  return (
    <View style={[styles.statCard, { borderColor: color + '44' }]}>
      <View style={[styles.statIcon, { backgroundColor: color + '18' }]}>
        <Ionicons name={icon} size={16} color={color} />
      </View>
      <Text style={[styles.statValue, { color }]}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  header: { paddingHorizontal: Spacing.lg, paddingTop: Spacing.md, paddingBottom: Spacing.sm },
  title: { ...Typography.h2, color: Colors.textPrimary },
  scroll: { padding: Spacing.lg, paddingTop: Spacing.sm, paddingBottom: Spacing.xxl },
  statsRow: { flexDirection: 'row', gap: Spacing.sm, marginBottom: Spacing.lg },
  statCard: {
    flex: 1, backgroundColor: Colors.surface, borderRadius: Radii.md, padding: Spacing.md,
    alignItems: 'center', gap: 4, borderWidth: 1,
  },
  statIcon: { width: 32, height: 32, borderRadius: Radii.sm, alignItems: 'center', justifyContent: 'center', marginBottom: 2 },
  statValue: { fontSize: 22, fontWeight: '800' },
  statLabel: { fontSize: 9, color: Colors.textMuted, fontWeight: '600', textAlign: 'center' },
  overallCard: {
    backgroundColor: Colors.surface, borderRadius: Radii.md, padding: Spacing.lg,
    borderWidth: 1, borderColor: Colors.border, marginBottom: Spacing.lg,
  },
  overallTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: Spacing.sm },
  overallTitle: { ...Typography.body, color: Colors.textPrimary, fontWeight: '700' },
  overallPct: { fontSize: 22, fontWeight: '800', color: Colors.blueprint },
  progressBarBg: { height: 6, backgroundColor: Colors.border, borderRadius: Radii.full, overflow: 'hidden' },
  progressBarFill: { height: '100%', backgroundColor: Colors.blueprint, borderRadius: Radii.full },
  overallSub: { ...Typography.caption, color: Colors.textMuted, marginTop: Spacing.sm },
  sectionTitle: { ...Typography.label, color: Colors.textMuted, marginBottom: Spacing.md },
  moduleCard: {
    backgroundColor: Colors.surface, borderRadius: Radii.md, padding: Spacing.md,
    marginBottom: Spacing.sm, borderWidth: 1, borderColor: Colors.border,
  },
  moduleCardLocked: { opacity: 0.6 },
  moduleTop: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm, marginBottom: Spacing.sm },
  moduleIcon: { width: 36, height: 36, borderRadius: Radii.sm, alignItems: 'center', justifyContent: 'center' },
  moduleInfo: { flex: 1 },
  moduleTitle: { ...Typography.bodySmall, color: Colors.textPrimary, fontWeight: '700' },
  lockedTitle: { color: Colors.textMuted },
  moduleSub: { ...Typography.caption, color: Colors.textMuted, marginTop: 2 },
  modulePct: { fontSize: 14, fontWeight: '800' },
  moduleProgressRow: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm },
  completeBadge: { backgroundColor: Colors.success + '22', borderRadius: Radii.full, paddingHorizontal: 8, paddingVertical: 2 },
  completeBadgeText: { fontSize: 9, fontWeight: '700', color: Colors.success },
  resumeHint: { ...Typography.caption, color: Colors.blueprint, marginTop: Spacing.xs },
});
