import React, { useEffect, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, RefreshControl, TouchableOpacity,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radii, Typography } from '../theme';
import { useAuthStore } from '../store/authStore';
import { useProgressStore } from '../store/progressStore';
import { COURSES, canAccessCourse } from '../data/modules';

const QUICK_PROMPTS = [
  'How do I analyze my first rental property?',
  'What is a DSCR loan?',
  'Explain the BRRRR strategy',
  'How do I build my SOI?',
  'What is a cap rate?',
];

export default function HomeScreen({ navigation }: any) {
  const { user } = useAuthStore();
  const { load, loaded, completed, moduleProgress } = useProgressStore();
  const [refreshing, setRefreshing] = React.useState(false);
  const chosenCourse = user?.chosen_course || null;
  const unlockedCourses = user?.unlocked_courses || [];
  const legacyTier = user?.university_tier || null;

  useEffect(() => {
    if (!loaded) load();
  }, []);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  }, []);

  const accessibleModules = COURSES.filter(m => canAccessCourse(chosenCourse, unlockedCourses, m.id, legacyTier));
  const totalLessons = accessibleModules.reduce((a, m) => a + m.lessons.length, 0);
  const totalCompleted = completed.filter(c =>
    accessibleModules.some(m => m.id === c.module_id)
  ).length;
  const overallPct = totalLessons > 0 ? Math.round((totalCompleted / totalLessons) * 100) : 0;

  // Find the in-progress module with the most recent activity
  const inProgressModules = accessibleModules.filter(m => {
    const p = moduleProgress(m.id, m.lessons.length);
    return p > 0 && p < 100;
  });

  // Most recently started module — find one with incomplete lessons
  const continueModule = inProgressModules[0] || accessibleModules[0];
  const continueLesson = continueModule
    ? continueModule.lessons.findIndex((_, i) => {
        const prog = useProgressStore.getState();
        return !prog.isComplete(continueModule.id, i);
      })
    : 0;

  const greeting = () => {
    const h = new Date().getHours();
    if (h < 12) return 'Good morning,';
    if (h < 17) return 'Good afternoon,';
    return 'Good evening,';
  };

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView
        contentContainerStyle={styles.scroll}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.blueprint} />}
        showsVerticalScrollIndicator={false}
      >
        {/* Header */}
        <View style={styles.header}>
          <View>
            <Text style={styles.greeting}>{greeting()}</Text>
            <Text style={styles.userName}>{user?.first_name || 'Learner'} 👋</Text>
          </View>
          <View style={styles.tierBadge}>
            <Text style={styles.tierText}>{(legacyTier || 'member').toUpperCase()}</Text>
          </View>
        </View>

        {/* Overall Progress Card */}
        <View style={styles.progressCard}>
          <View style={styles.progressTop}>
            <View>
              <Text style={styles.progressTitle}>Overall Progress</Text>
              <Text style={styles.progressStat}>{totalCompleted} of {totalLessons} lessons</Text>
            </View>
            <View style={styles.progressCircle}>
              <Text style={styles.progressPct}>{overallPct}%</Text>
            </View>
          </View>
          <View style={styles.progressBarBg}>
            <View style={[styles.progressBarFill, { width: `${overallPct}%` }]} />
          </View>
          <View style={styles.progressModules}>
            {accessibleModules.slice(0, 4).map(m => {
              const p = moduleProgress(m.id, m.lessons.length);
              return (
                <View key={m.id} style={styles.miniModuleBar}>
                  <View style={[styles.miniDot, { backgroundColor: m.color }]} />
                  <View style={styles.miniBarBg}>
                    <View style={[styles.miniBarFill, { width: `${p}%`, backgroundColor: m.color }]} />
                  </View>
                </View>
              );
            })}
          </View>
        </View>

        {/* Continue Learning */}
        {continueModule && (
          <>
            <Text style={styles.sectionTitle}>Continue Learning</Text>
            <TouchableOpacity
              style={styles.continueCard}
              onPress={() => navigation.navigate('Learn', {
                screen: 'ModuleDetail',
                params: { moduleId: continueModule.id },
              })}
              activeOpacity={0.8}
            >
              <View style={[styles.continueIcon, { backgroundColor: continueModule.color + '22' }]}>
                <Ionicons name={continueModule.icon as any} size={22} color={continueModule.color} />
              </View>
              <View style={styles.continueInfo}>
                <Text style={styles.continueModule}>{continueModule.title}</Text>
                {continueLesson >= 0 && (
                  <Text style={styles.continueLesson} numberOfLines={1}>
                    {continueLesson < continueModule.lessons.length
                      ? continueModule.lessons[continueLesson].title
                      : 'Completed!'}
                  </Text>
                )}
                <View style={styles.continueProgress}>
                  <View style={styles.miniBarBg}>
                    <View style={[
                      styles.miniBarFill,
                      { width: `${moduleProgress(continueModule.id, continueModule.lessons.length)}%`, backgroundColor: continueModule.color }
                    ]} />
                  </View>
                  <Text style={[styles.continuePct, { color: continueModule.color }]}>
                    {moduleProgress(continueModule.id, continueModule.lessons.length)}%
                  </Text>
                </View>
              </View>
              <View style={[styles.playBtn, { backgroundColor: continueModule.color }]}>
                <Ionicons name="play" size={16} color={Colors.white} />
              </View>
            </TouchableOpacity>
          </>
        )}

        {/* All Modules Preview */}
        <View style={styles.sectionRow}>
          <Text style={styles.sectionTitle}>Modules</Text>
          <TouchableOpacity onPress={() => navigation.navigate('Learn', { screen: 'LearnHome' })}>
            <Text style={styles.seeAll}>See all →</Text>
          </TouchableOpacity>
        </View>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.modulesScroll} contentContainerStyle={styles.modulesRow}>
          {COURSES.map(m => {
            const accessible = canAccessCourse(chosenCourse, unlockedCourses, m.id, legacyTier);
            const p = moduleProgress(m.id, m.lessons.length);
            return (
              <TouchableOpacity
                key={m.id}
                style={[styles.moduleChip, !accessible && styles.moduleChipLocked]}
                onPress={() => accessible && navigation.navigate('Learn', { screen: 'ModuleDetail', params: { moduleId: m.id } })}
                activeOpacity={accessible ? 0.75 : 1}
              >
                <View style={[styles.moduleChipIcon, { backgroundColor: m.color + (accessible ? '22' : '11') }]}>
                  <Ionicons name={m.icon as any} size={18} color={accessible ? m.color : Colors.textMuted} />
                </View>
                <Text style={[styles.moduleChipTitle, !accessible && styles.lockedTitle]} numberOfLines={2}>{m.title}</Text>
                {accessible ? (
                  <Text style={[styles.moduleChipPct, { color: m.color }]}>{p}%</Text>
                ) : (
                  <Ionicons name="lock-closed-outline" size={12} color={Colors.textMuted} />
                )}
              </TouchableOpacity>
            );
          })}
        </ScrollView>

        {/* Quick AI Prompts */}
        <Text style={styles.sectionTitle}>Ask Ravlo AI</Text>
        <View style={styles.promptsCard}>
          {QUICK_PROMPTS.map((p, i) => (
            <TouchableOpacity
              key={i}
              style={[styles.promptRow, i < QUICK_PROMPTS.length - 1 && styles.promptBorder]}
              onPress={() => navigation.navigate('Coach', { initialPrompt: p })}
              activeOpacity={0.75}
            >
              <Ionicons name="sparkles-outline" size={14} color={Colors.blueprint} />
              <Text style={styles.promptText}>{p}</Text>
              <Ionicons name="chevron-forward" size={14} color={Colors.textMuted} />
            </TouchableOpacity>
          ))}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  scroll: { padding: Spacing.lg, paddingBottom: Spacing.xxl },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: Spacing.lg },
  greeting: { ...Typography.bodySmall, color: Colors.textMuted },
  userName: { ...Typography.h2, color: Colors.textPrimary, marginTop: 2 },
  tierBadge: { backgroundColor: Colors.blueprint + '22', borderRadius: Radii.full, paddingHorizontal: 10, paddingVertical: 4, marginTop: 4 },
  tierText: { fontSize: 10, fontWeight: '800', color: Colors.blueprint, letterSpacing: 1 },
  progressCard: {
    backgroundColor: Colors.surface, borderRadius: Radii.lg, padding: Spacing.lg,
    borderWidth: 1, borderColor: Colors.border, marginBottom: Spacing.lg,
  },
  progressTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: Spacing.md },
  progressTitle: { ...Typography.body, color: Colors.textPrimary, fontWeight: '700' },
  progressStat: { ...Typography.caption, color: Colors.textMuted, marginTop: 3 },
  progressCircle: {
    width: 56, height: 56, borderRadius: 28, borderWidth: 3, borderColor: Colors.blueprint,
    alignItems: 'center', justifyContent: 'center', backgroundColor: Colors.blueprint + '18',
  },
  progressPct: { fontSize: 16, fontWeight: '800', color: Colors.blueprint },
  progressBarBg: { height: 6, backgroundColor: Colors.border, borderRadius: Radii.full, overflow: 'hidden', marginBottom: Spacing.md },
  progressBarFill: { height: '100%', backgroundColor: Colors.blueprint, borderRadius: Radii.full },
  progressModules: { gap: 6 },
  miniModuleBar: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  miniDot: { width: 7, height: 7, borderRadius: 3.5 },
  miniBarBg: { flex: 1, height: 3, backgroundColor: Colors.border, borderRadius: Radii.full, overflow: 'hidden' },
  miniBarFill: { height: '100%', borderRadius: Radii.full },
  sectionTitle: { ...Typography.label, color: Colors.textMuted, marginBottom: Spacing.md, marginTop: Spacing.sm },
  sectionRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: Spacing.sm, marginBottom: Spacing.md },
  seeAll: { ...Typography.caption, color: Colors.blueprint, fontWeight: '600' },
  continueCard: {
    backgroundColor: Colors.surface, borderRadius: Radii.md, padding: Spacing.md,
    flexDirection: 'row', alignItems: 'center', gap: Spacing.sm,
    borderWidth: 1, borderColor: Colors.border, marginBottom: Spacing.lg,
  },
  continueIcon: { width: 48, height: 48, borderRadius: Radii.sm, alignItems: 'center', justifyContent: 'center' },
  continueInfo: { flex: 1 },
  continueModule: { ...Typography.bodySmall, color: Colors.textPrimary, fontWeight: '700' },
  continueLesson: { ...Typography.caption, color: Colors.textMuted, marginTop: 2 },
  continueProgress: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm, marginTop: 6 },
  continuePct: { fontSize: 11, fontWeight: '700' },
  playBtn: { width: 36, height: 36, borderRadius: 18, alignItems: 'center', justifyContent: 'center' },
  modulesScroll: { flexGrow: 0, marginBottom: Spacing.lg },
  modulesRow: { gap: Spacing.sm, paddingBottom: 4 },
  moduleChip: {
    width: 110, backgroundColor: Colors.surface, borderRadius: Radii.md, padding: Spacing.sm,
    borderWidth: 1, borderColor: Colors.border, alignItems: 'center', gap: 6,
  },
  moduleChipLocked: { opacity: 0.55 },
  moduleChipIcon: { width: 38, height: 38, borderRadius: Radii.sm, alignItems: 'center', justifyContent: 'center' },
  moduleChipTitle: { ...Typography.caption, color: Colors.textPrimary, textAlign: 'center', fontWeight: '600' },
  lockedTitle: { color: Colors.textMuted },
  moduleChipPct: { fontSize: 11, fontWeight: '700' },
  promptsCard: {
    backgroundColor: Colors.surface, borderRadius: Radii.md,
    borderWidth: 1, borderColor: Colors.border, overflow: 'hidden',
  },
  promptRow: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm, padding: Spacing.md },
  promptBorder: { borderBottomWidth: 1, borderBottomColor: Colors.border },
  promptText: { ...Typography.bodySmall, color: Colors.textSecondary, flex: 1 },
});
