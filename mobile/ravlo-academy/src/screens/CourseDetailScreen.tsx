import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radii, Typography } from '../theme';
import { api } from '../services/api';

interface Course {
  id: number;
  title: string;
  description: string;
  duration: string;
  level: string;
  category: string;
}

interface CourseProgress {
  percent_complete: number;
  completed: boolean;
}

const LEVEL_COLORS: Record<string, string> = {
  Beginner: Colors.success,
  Intermediate: Colors.warning,
  Advanced: Colors.danger,
};

export default function CourseDetailScreen({ route, navigation }: any) {
  const { courseId } = route.params;
  const [course, setCourse] = useState<Course | null>(null);
  const [progress, setProgress] = useState<CourseProgress | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [starting, setStarting] = useState(false);

  const fetchCourse = useCallback(async () => {
    try {
      const [courseRes, progressRes] = await Promise.all([
        api.get(`/mobile/academy/courses/${courseId}`),
        api.get('/mobile/academy/progress'),
      ]);
      setCourse(courseRes.data.course);
      const myProgress = (progressRes.data.progress || []).find(
        (p: any) => p.course_id === courseId
      );
      setProgress(myProgress || null);
    } catch (err: any) {
      Alert.alert('Error', err.response?.data?.error || 'Could not load course.');
    } finally {
      setLoading(false);
    }
  }, [courseId]);

  useEffect(() => { fetchCourse(); }, [fetchCourse]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchCourse();
    setRefreshing(false);
  }, [fetchCourse]);

  const handleStart = async () => {
    setStarting(true);
    try {
      const currentPercent = progress?.percent_complete ?? 0;
      const newPercent = Math.max(currentPercent, 10);
      const res = await api.post(`/mobile/academy/progress/${courseId}`, {
        percent_complete: newPercent,
        completed: false,
      });
      setProgress(res.data.progress);
      Alert.alert('Progress Saved', 'Your progress has been recorded. Keep learning!');
    } catch (err: any) {
      Alert.alert('Error', err.response?.data?.error || 'Could not save progress.');
    } finally {
      setStarting(false);
    }
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.centered}><ActivityIndicator size="large" color={Colors.blueprint} /></View>
      </SafeAreaView>
    );
  }

  if (!course) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.centered}><Text style={styles.errorText}>Course not found.</Text></View>
      </SafeAreaView>
    );
  }

  const levelColor = LEVEL_COLORS[course.level] || Colors.blueprint;
  const pct = progress?.percent_complete ?? 0;
  const isCompleted = progress?.completed ?? false;
  const hasStarted = pct > 0;

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.navBar}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Ionicons name="chevron-back" size={24} color={Colors.textPrimary} />
          <Text style={styles.backText}>Courses</Text>
        </TouchableOpacity>
      </View>
      <ScrollView
        contentContainerStyle={styles.scroll}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.blueprint} />}
      >
        <View style={styles.heroIcon}>
          <Ionicons name="book" size={36} color={Colors.blueprint} />
        </View>

        <View style={styles.badges}>
          <View style={[styles.badge, { backgroundColor: levelColor + '22', borderColor: levelColor }]}>
            <Text style={[styles.badgeText, { color: levelColor }]}>{course.level}</Text>
          </View>
          {course.category ? (
            <View style={styles.categoryBadge}>
              <Text style={styles.categoryText}>{course.category}</Text>
            </View>
          ) : null}
        </View>

        <Text style={styles.title}>{course.title}</Text>

        {course.duration ? (
          <View style={styles.durationRow}>
            <Ionicons name="time-outline" size={16} color={Colors.textMuted} />
            <Text style={styles.duration}>{course.duration}</Text>
          </View>
        ) : null}

        {pct > 0 && (
          <View style={styles.progressSection}>
            <View style={styles.progressRow}>
              <Text style={styles.progressLabel}>{isCompleted ? 'Completed' : 'Progress'}</Text>
              <Text style={styles.progressPct}>{pct.toFixed(0)}%</Text>
            </View>
            <View style={styles.progressBarBg}>
              <View style={[styles.progressBarFill, { width: `${Math.min(pct, 100)}%`, backgroundColor: isCompleted ? Colors.success : Colors.blueprint }]} />
            </View>
          </View>
        )}

        {course.description ? (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>About this Course</Text>
            <Text style={styles.description}>{course.description}</Text>
          </View>
        ) : null}

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Details</Text>
          <DetailRow label="Level" value={course.level || '—'} />
          {course.category ? <DetailRow label="Category" value={course.category} /> : null}
          {course.duration ? <DetailRow label="Duration" value={course.duration} /> : null}
        </View>

        <TouchableOpacity
          style={[styles.ctaButton, isCompleted && styles.ctaCompleted, starting && styles.ctaDisabled]}
          onPress={handleStart}
          disabled={starting || isCompleted}
          activeOpacity={0.8}
        >
          {starting ? (
            <ActivityIndicator color={Colors.white} />
          ) : (
            <Text style={styles.ctaText}>
              {isCompleted ? 'Completed' : hasStarted ? 'Continue' : 'Start Course'}
            </Text>
          )}
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.detailRow}>
      <Text style={styles.detailLabel}>{label}</Text>
      <Text style={styles.detailValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  errorText: { ...Typography.body, color: Colors.danger },
  navBar: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: Spacing.md, paddingVertical: Spacing.sm },
  backBtn: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  backText: { ...Typography.body, color: Colors.textPrimary },
  scroll: { padding: Spacing.lg },
  heroIcon: {
    width: 80,
    height: 80,
    borderRadius: Radii.lg,
    backgroundColor: Colors.blueprint + '22',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: Spacing.md,
  },
  badges: { flexDirection: 'row', gap: Spacing.sm, marginBottom: Spacing.sm },
  badge: { borderWidth: 1, borderRadius: Radii.full, paddingHorizontal: Spacing.sm, paddingVertical: 3 },
  badgeText: { ...Typography.caption, fontWeight: '700' },
  categoryBadge: {
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: Radii.full,
    paddingHorizontal: Spacing.sm,
    paddingVertical: 3,
    backgroundColor: Colors.surface,
  },
  categoryText: { ...Typography.caption, color: Colors.textMuted, fontWeight: '600' },
  title: { ...Typography.h2, color: Colors.textPrimary, marginBottom: Spacing.sm },
  durationRow: { flexDirection: 'row', alignItems: 'center', gap: 4, marginBottom: Spacing.lg },
  duration: { ...Typography.bodySmall, color: Colors.textMuted },
  progressSection: { marginBottom: Spacing.lg },
  progressRow: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 6 },
  progressLabel: { ...Typography.bodySmall, color: Colors.textMuted },
  progressPct: { ...Typography.bodySmall, color: Colors.blueprint, fontWeight: '700' },
  progressBarBg: { height: 8, backgroundColor: Colors.border, borderRadius: Radii.full, overflow: 'hidden' },
  progressBarFill: { height: '100%', borderRadius: Radii.full },
  section: {
    backgroundColor: Colors.surface,
    borderRadius: Radii.md,
    padding: Spacing.md,
    marginBottom: Spacing.md,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  sectionTitle: { ...Typography.label, color: Colors.textMuted, marginBottom: Spacing.sm },
  description: { ...Typography.body, color: Colors.textSecondary, lineHeight: 24 },
  detailRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: Spacing.xs },
  detailLabel: { ...Typography.bodySmall, color: Colors.textMuted },
  detailValue: { ...Typography.bodySmall, color: Colors.textPrimary, fontWeight: '600' },
  ctaButton: {
    backgroundColor: Colors.blueprint,
    borderRadius: Radii.md,
    paddingVertical: Spacing.md,
    alignItems: 'center',
    marginTop: Spacing.sm,
  },
  ctaCompleted: { backgroundColor: Colors.success },
  ctaDisabled: { opacity: 0.6 },
  ctaText: { ...Typography.label, color: Colors.white, fontSize: 16 },
});
