import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
  TouchableOpacity,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radii, Typography } from '../theme';
import { useAuthStore } from '../store/authStore';
import { api } from '../services/api';

interface ProgressData {
  courses_completed: number;
  completion_rate: number;
  progress: Array<{ course_id: number; percent_complete: number; completed: boolean }>;
}

interface Course {
  id: number;
  title: string;
  description: string;
  level: string;
  category: string;
  duration: string;
}

export default function HomeScreen({ navigation }: any) {
  const { user } = useAuthStore();
  const [progressData, setProgressData] = useState<ProgressData | null>(null);
  const [featuredCourses, setFeaturedCourses] = useState<Course[]>([]);
  const [inProgressCourses, setInProgressCourses] = useState<Course[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [progressRes, coursesRes] = await Promise.all([
        api.get('/mobile/academy/progress'),
        api.get('/mobile/academy/courses'),
      ]);
      const pd: ProgressData = progressRes.data;
      const allCourses: Course[] = coursesRes.data.courses || [];
      setProgressData(pd);

      // Featured: first 4 courses
      setFeaturedCourses(allCourses.slice(0, 4));

      // In-progress: courses that have started but not completed
      const inProgressIds = new Set(
        pd.progress
          .filter((p) => !p.completed && p.percent_complete > 0)
          .map((p) => p.course_id)
      );
      setInProgressCourses(allCourses.filter((c) => inProgressIds.has(c.id)).slice(0, 3));
    } catch (err: any) {
      Alert.alert('Error', err.response?.data?.error || 'Could not load data.');
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchData();
    setRefreshing(false);
  }, [fetchData]);

  const totalCourses = featuredCourses.length;
  const completed = progressData?.courses_completed ?? 0;
  const completionRate = progressData?.completion_rate ?? 0;

  // Simple progress ring using border radius hack
  const RING_SIZE = 100;

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView
        contentContainerStyle={styles.scroll}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.blueprint} />}
      >
        <View style={styles.header}>
          <Text style={styles.greeting}>Welcome back,</Text>
          <Text style={styles.userName}>{user?.first_name || 'Learner'}</Text>
        </View>

        <View style={styles.progressCard}>
          <View style={styles.ringContainer}>
            <View style={[styles.ringOuter, { borderColor: Colors.border }]}>
              <View
                style={[
                  styles.ringInner,
                  { borderColor: Colors.blueprint, borderTopColor: completionRate > 25 ? Colors.blueprint : Colors.border },
                ]}
              />
              <View style={styles.ringCenter}>
                <Text style={styles.ringValue}>{completed}</Text>
                <Text style={styles.ringLabel}>done</Text>
              </View>
            </View>
          </View>
          <View style={styles.progressInfo}>
            <Text style={styles.progressTitle}>Your Progress</Text>
            <Text style={styles.progressStat}>
              {completed} of {totalCourses} courses completed
            </Text>
            <View style={styles.progressBarBg}>
              <View style={[styles.progressBarFill, { width: `${Math.min(completionRate, 100)}%` }]} />
            </View>
            <Text style={styles.progressPercent}>{completionRate.toFixed(0)}% complete</Text>
          </View>
        </View>

        {inProgressCourses.length > 0 && (
          <>
            <Text style={styles.sectionTitle}>Continue Learning</Text>
            {inProgressCourses.map((course) => {
              const prog = progressData?.progress.find((p) => p.course_id === course.id);
              return (
                <TouchableOpacity
                  key={course.id}
                  style={styles.continueCard}
                  onPress={() => navigation.navigate('Courses', { screen: 'CourseDetail', params: { courseId: course.id } })}
                  activeOpacity={0.75}
                >
                  <View style={styles.continueMeta}>
                    <Text style={styles.courseTitle} numberOfLines={1}>{course.title}</Text>
                    <Text style={styles.courseLevel}>{course.level}</Text>
                  </View>
                  <View style={styles.continuePct}>
                    <Text style={styles.pctText}>{prog ? prog.percent_complete.toFixed(0) : 0}%</Text>
                  </View>
                </TouchableOpacity>
              );
            })}
          </>
        )}

        <Text style={styles.sectionTitle}>Featured Courses</Text>
        {featuredCourses.length === 0 ? (
          <View style={styles.emptyContainer}>
            <Ionicons name="book-outline" size={40} color={Colors.textMuted} />
            <Text style={styles.emptyText}>No courses available</Text>
          </View>
        ) : (
          featuredCourses.map((course) => (
            <TouchableOpacity
              key={course.id}
              style={styles.courseCard}
              onPress={() => navigation.navigate('Courses', { screen: 'CourseDetail', params: { courseId: course.id } })}
              activeOpacity={0.75}
            >
              <View style={styles.courseCardHeader}>
                <View style={styles.courseIcon}>
                  <Ionicons name="book-outline" size={20} color={Colors.blueprint} />
                </View>
                <View style={styles.courseMeta}>
                  <Text style={styles.courseTitle} numberOfLines={1}>{course.title}</Text>
                  <Text style={styles.courseSubMeta}>{course.level} {course.duration ? `· ${course.duration}` : ''}</Text>
                </View>
                <Ionicons name="chevron-forward" size={18} color={Colors.textMuted} />
              </View>
              {course.description ? (
                <Text style={styles.courseDesc} numberOfLines={2}>{course.description}</Text>
              ) : null}
            </TouchableOpacity>
          ))
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  scroll: { padding: Spacing.lg },
  header: { marginBottom: Spacing.lg },
  greeting: { ...Typography.bodySmall, color: Colors.textMuted },
  userName: { ...Typography.h2, color: Colors.textPrimary, marginTop: 2 },
  progressCard: {
    backgroundColor: Colors.surface,
    borderRadius: Radii.lg,
    padding: Spacing.lg,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.lg,
    borderWidth: 1,
    borderColor: Colors.border,
    marginBottom: Spacing.lg,
  },
  ringContainer: { alignItems: 'center', justifyContent: 'center' },
  ringOuter: {
    width: 80,
    height: 80,
    borderRadius: 40,
    borderWidth: 6,
    alignItems: 'center',
    justifyContent: 'center',
  },
  ringInner: {
    position: 'absolute',
    width: 80,
    height: 80,
    borderRadius: 40,
    borderWidth: 6,
    borderColor: 'transparent',
    borderTopColor: Colors.blueprint,
    transform: [{ rotate: '45deg' }],
  },
  ringCenter: { alignItems: 'center' },
  ringValue: { fontSize: 22, fontWeight: '800', color: Colors.textPrimary },
  ringLabel: { ...Typography.caption, color: Colors.textMuted },
  progressInfo: { flex: 1 },
  progressTitle: { ...Typography.body, color: Colors.textPrimary, fontWeight: '700', marginBottom: 4 },
  progressStat: { ...Typography.caption, color: Colors.textMuted, marginBottom: Spacing.sm },
  progressBarBg: { height: 6, backgroundColor: Colors.border, borderRadius: Radii.full, overflow: 'hidden' },
  progressBarFill: { height: '100%', backgroundColor: Colors.blueprint, borderRadius: Radii.full },
  progressPercent: { ...Typography.caption, color: Colors.blueprint, marginTop: 4, fontWeight: '600' },
  sectionTitle: { ...Typography.label, color: Colors.textMuted, marginBottom: Spacing.md, marginTop: Spacing.sm },
  continueCard: {
    backgroundColor: Colors.surface,
    borderRadius: Radii.md,
    padding: Spacing.md,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: Spacing.sm,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  continueMeta: { flex: 1, marginRight: Spacing.sm },
  continuePct: {
    backgroundColor: Colors.blueprint + '22',
    borderRadius: Radii.sm,
    paddingHorizontal: Spacing.sm,
    paddingVertical: 4,
  },
  pctText: { ...Typography.caption, color: Colors.blueprint, fontWeight: '700' },
  emptyContainer: { alignItems: 'center', paddingVertical: Spacing.xl, gap: Spacing.md },
  emptyText: { ...Typography.body, color: Colors.textMuted },
  courseCard: {
    backgroundColor: Colors.surface,
    borderRadius: Radii.md,
    padding: Spacing.md,
    marginBottom: Spacing.sm,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  courseCardHeader: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm },
  courseIcon: {
    width: 40,
    height: 40,
    borderRadius: Radii.sm,
    backgroundColor: Colors.blueprint + '22',
    alignItems: 'center',
    justifyContent: 'center',
  },
  courseMeta: { flex: 1 },
  courseTitle: { ...Typography.body, color: Colors.textPrimary, fontWeight: '600' },
  courseLevel: { ...Typography.caption, color: Colors.textMuted },
  courseSubMeta: { ...Typography.caption, color: Colors.textMuted },
  courseDesc: { ...Typography.bodySmall, color: Colors.textMuted, marginTop: Spacing.sm },
});
