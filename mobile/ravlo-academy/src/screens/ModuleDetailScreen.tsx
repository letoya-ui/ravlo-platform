import React, { useEffect } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radii, Typography } from '../theme';
import { useProgressStore } from '../store/progressStore';
import { MODULES } from '../data/modules';

export default function ModuleDetailScreen({ route, navigation }: any) {
  const { moduleId } = route.params;
  const module = MODULES.find(m => m.id === moduleId);
  const { isComplete, moduleProgress, load, loaded } = useProgressStore();

  useEffect(() => {
    if (!loaded) load();
  }, []);

  if (!module) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.centered}>
          <Text style={styles.errorText}>Module not found.</Text>
        </View>
      </SafeAreaView>
    );
  }

  const progress = moduleProgress(module.id, module.lessons.length);
  const doneLessons = Math.round((progress / 100) * module.lessons.length);

  const firstIncomplete = module.lessons.findIndex((_, i) => !isComplete(module.id, i));
  const continueIndex = firstIncomplete === -1 ? 0 : firstIncomplete;

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.nav}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Ionicons name="chevron-back" size={24} color={Colors.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.navTitle} numberOfLines={1}>{module.title}</Text>
        <View style={{ width: 40 }} />
      </View>

      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        {/* Module Header */}
        <View style={styles.headerCard}>
          <View style={[styles.moduleIcon, { backgroundColor: module.color + '22' }]}>
            <Ionicons name={module.icon as any} size={28} color={module.color} />
          </View>
          <Text style={styles.moduleTitle}>{module.title}</Text>
          <Text style={styles.moduleDesc}>{module.description}</Text>

          <View style={styles.statsRow}>
            <StatChip icon="book-outline" label={`${module.lessons.length} lessons`} color={module.color} />
            <StatChip icon="checkmark-circle-outline" label={`${doneLessons} complete`} color={Colors.success} />
            <StatChip icon="time-outline" label={getTotalDuration(module.lessons)} color={Colors.info} />
          </View>

          <View style={styles.progressSection}>
            <View style={styles.progressBar}>
              <View style={[styles.progressFill, { width: `${progress}%`, backgroundColor: module.color }]} />
            </View>
            <Text style={[styles.progressPct, { color: module.color }]}>{progress}%</Text>
          </View>
        </View>

        {/* Continue Button */}
        {progress < 100 && (
          <TouchableOpacity
            style={[styles.continueBtn, { backgroundColor: module.color }]}
            onPress={() => navigation.navigate('Lesson', { moduleId: module.id, lessonIndex: continueIndex })}
            activeOpacity={0.85}
          >
            <Ionicons name="play-circle-outline" size={20} color={Colors.white} />
            <Text style={styles.continueBtnText}>
              {doneLessons === 0 ? 'Start Module' : 'Continue Learning'}
            </Text>
          </TouchableOpacity>
        )}
        {progress === 100 && (
          <View style={[styles.completedBanner]}>
            <Ionicons name="trophy-outline" size={18} color={Colors.success} />
            <Text style={styles.completedText}>Module Complete!</Text>
          </View>
        )}

        {/* Lessons List */}
        <Text style={styles.sectionTitle}>Lessons</Text>
        {module.lessons.map((lesson, index) => {
          const complete = isComplete(module.id, index);
          return (
            <TouchableOpacity
              key={index}
              style={styles.lessonRow}
              onPress={() => navigation.navigate('Lesson', { moduleId: module.id, lessonIndex: index })}
              activeOpacity={0.75}
            >
              <View style={[styles.lessonNum, complete && { backgroundColor: Colors.success + '22', borderColor: Colors.success }]}>
                {complete
                  ? <Ionicons name="checkmark" size={14} color={Colors.success} />
                  : <Text style={styles.lessonNumText}>{index + 1}</Text>
                }
              </View>
              <View style={styles.lessonInfo}>
                <Text style={[styles.lessonTitle, complete && styles.lessonTitleDone]}>{lesson.title}</Text>
                <Text style={styles.lessonDuration}>{lesson.duration}</Text>
              </View>
              <Ionicons name="chevron-forward" size={16} color={Colors.textMuted} />
            </TouchableOpacity>
          );
        })}
      </ScrollView>
    </SafeAreaView>
  );
}

function StatChip({ icon, label, color }: { icon: any; label: string; color: string }) {
  return (
    <View style={[styles.statChip, { backgroundColor: color + '18' }]}>
      <Ionicons name={icon} size={12} color={color} />
      <Text style={[styles.statLabel, { color }]}>{label}</Text>
    </View>
  );
}

function getTotalDuration(lessons: { duration: string }[]): string {
  const total = lessons.reduce((acc, l) => {
    const n = parseInt(l.duration);
    return acc + (isNaN(n) ? 0 : n);
  }, 0);
  return total >= 60 ? `${Math.floor(total / 60)}h ${total % 60}m` : `${total} min`;
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  errorText: { ...Typography.body, color: Colors.danger },
  nav: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: Spacing.md, paddingVertical: Spacing.sm,
  },
  backBtn: { padding: 8, width: 40 },
  navTitle: { ...Typography.bodySmall, color: Colors.textPrimary, fontWeight: '700', flex: 1, textAlign: 'center' },
  scroll: { padding: Spacing.lg, paddingBottom: Spacing.xxl },
  headerCard: {
    backgroundColor: Colors.surface, borderRadius: Radii.lg, padding: Spacing.lg,
    borderWidth: 1, borderColor: Colors.border, marginBottom: Spacing.lg, alignItems: 'center',
  },
  moduleIcon: { width: 64, height: 64, borderRadius: Radii.lg, alignItems: 'center', justifyContent: 'center', marginBottom: Spacing.md },
  moduleTitle: { ...Typography.h3, color: Colors.textPrimary, textAlign: 'center', marginBottom: Spacing.sm },
  moduleDesc: { ...Typography.bodySmall, color: Colors.textMuted, textAlign: 'center', lineHeight: 20, marginBottom: Spacing.md },
  statsRow: { flexDirection: 'row', gap: Spacing.sm, marginBottom: Spacing.md, flexWrap: 'wrap', justifyContent: 'center' },
  statChip: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 5, borderRadius: Radii.full },
  statLabel: { fontSize: 11, fontWeight: '600' },
  progressSection: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm, width: '100%' },
  progressBar: { flex: 1, height: 6, backgroundColor: Colors.border, borderRadius: Radii.full, overflow: 'hidden' },
  progressFill: { height: '100%', borderRadius: Radii.full },
  progressPct: { fontSize: 12, fontWeight: '800', minWidth: 36, textAlign: 'right' },
  continueBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: Spacing.sm, borderRadius: Radii.md, paddingVertical: 14,
    marginBottom: Spacing.lg,
  },
  continueBtnText: { ...Typography.body, color: Colors.white, fontWeight: '700' },
  completedBanner: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: Spacing.sm,
    backgroundColor: Colors.success + '18', borderRadius: Radii.md, paddingVertical: 12,
    marginBottom: Spacing.lg, borderWidth: 1, borderColor: Colors.success + '44',
  },
  completedText: { ...Typography.body, color: Colors.success, fontWeight: '700' },
  sectionTitle: { ...Typography.label, color: Colors.textMuted, marginBottom: Spacing.md },
  lessonRow: {
    flexDirection: 'row', alignItems: 'center', gap: Spacing.sm,
    backgroundColor: Colors.surface, borderRadius: Radii.md, padding: Spacing.md,
    marginBottom: Spacing.sm, borderWidth: 1, borderColor: Colors.border,
  },
  lessonNum: {
    width: 30, height: 30, borderRadius: 15, alignItems: 'center', justifyContent: 'center',
    borderWidth: 1.5, borderColor: Colors.border, backgroundColor: Colors.border + '40',
  },
  lessonNumText: { fontSize: 12, fontWeight: '700', color: Colors.textMuted },
  lessonInfo: { flex: 1 },
  lessonTitle: { ...Typography.bodySmall, color: Colors.textPrimary, fontWeight: '600' },
  lessonTitleDone: { color: Colors.textMuted, textDecorationLine: 'line-through' },
  lessonDuration: { ...Typography.caption, color: Colors.textMuted, marginTop: 2 },
});
