import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  FlatList,
  StyleSheet,
  RefreshControl,
  Alert,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radii, Typography } from '../theme';
import { api } from '../services/api';

interface CourseProgress {
  id: number;
  course_id: number;
  completed: boolean;
  percent_complete: number;
  last_accessed: string;
}

interface ProgressData {
  progress: CourseProgress[];
  courses_completed: number;
  completion_rate: number;
}

export default function ProgressScreen() {
  const [data, setData] = useState<ProgressData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchProgress = useCallback(async () => {
    try {
      const res = await api.get('/mobile/academy/progress');
      setData(res.data);
    } catch (err: any) {
      Alert.alert('Error', err.response?.data?.error || 'Could not load progress.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchProgress(); }, [fetchProgress]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchProgress();
    setRefreshing(false);
  }, [fetchProgress]);

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.centered}><ActivityIndicator size="large" color={Colors.blueprint} /></View>
      </SafeAreaView>
    );
  }

  const total = data?.progress.length ?? 0;
  const completed = data?.courses_completed ?? 0;
  const rate = data?.completion_rate ?? 0;

  return (
    <SafeAreaView style={styles.container}>
      <FlatList
        data={data?.progress || []}
        keyExtractor={(item) => String(item.id ?? item.course_id)}
        contentContainerStyle={styles.list}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.blueprint} />}
        ListHeaderComponent=(
          <View>
            <Text style={styles.title}>My Progress</Text>
            <View style={styles.statsRow}>
              <StatCard
                label="Completed"
                value={String(completed)}
                icon="checkmark-circle-outline"
                color={Colors.success}
              />
              <StatCard
                label="Total Started"
                value={String(total)}
                icon="book-outline"
                color={Colors.blueprint}
              />
              <StatCard
                label="Rate"
                value={`${rate.toFixed(0)}%`}
                icon="bar-chart-outline"
                color={Colors.info}
              />
            </View>
            <Text style={styles.sectionTitle}>Course Progress</Text>
          </View>
        )
        ListEmptyComponent={
          <View style={styles.empty}>
            <Ionicons name="bar-chart-outline" size={48} color={Colors.textMuted} />
            <Text style={styles.emptyText}>No progress recorded yet</Text>
            <Text style={styles.emptySubText}>Start a course to track your progress</Text>
          </View>
        }
        renderItem={({ item }) => {
          const pct = Math.min(item.percent_complete, 100);
          const barColor = item.completed ? Colors.success : Colors.blueprint;
          return (
            <View style={styles.progressCard}>
              <View style={styles.progressHeader}>
                <View style={styles.courseInfo}>
                  <Text style={styles.courseId}>Course #{item.course_id}</Text>
                  {item.last_accessed ? (
                    <Text style={styles.lastAccessed}>
                      Last: {new Date(item.last_accessed).toLocaleDateString()}
                    </Text>
                  ) : null}
                </View>
                <View style={[styles.completionBadge, { backgroundColor: item.completed ? Colors.success + '22' : Colors.border }]}>
                  {item.completed ? (
                    <Ionicons name="checkmark-circle" size={16} color={Colors.success} />
                  ) : (
                    <Text style={styles.pctLabel}>{pct.toFixed(0)}%</Text>
                  )}
                </View>
              </View>
              <View style={styles.barBg}>
                <View style={[styles.barFill, { width: `${pct}%`, backgroundColor: barColor }]} />
              </View>
            </View>
          );
        }}
      />
    </SafeAreaView>
  );
}

function StatCard({ label, value, icon, color }: { label: string; value: string; icon: any; color: string }) {
  return (
    <View style={[styles.statCard, { borderColor: color + '44' }]}>
      <Ionicons name={icon} size={20} color={color} />
      <Text style={[styles.statValue, { color }]}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  list: { padding: Spacing.lg, paddingBottom: Spacing.xl },
  title: { ...Typography.h2, color: Colors.textPrimary, marginBottom: Spacing.lg },
  statsRow: { flexDirection: 'row', gap: Spacing.sm, marginBottom: Spacing.lg },
  statCard: {
    flex: 1,
    backgroundColor: Colors.surface,
    borderRadius: Radii.md,
    padding: Spacing.sm,
    alignItems: 'center',
    borderWidth: 1,
    gap: 4,
  },
  statValue: { fontSize: 20, fontWeight: '800' },
  statLabel: { ...Typography.caption, color: Colors.textMuted, textAlign: 'center' },
  sectionTitle: { ...Typography.label, color: Colors.textMuted, marginBottom: Spacing.md },
  progressCard: {
    backgroundColor: Colors.surface,
    borderRadius: Radii.md,
    padding: Spacing.md,
    marginBottom: Spacing.sm,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  progressHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: Spacing.sm },
  courseInfo: { flex: 1 },
  courseId: { ...Typography.body, color: Colors.textPrimary, fontWeight: '600' },
  lastAccessed: { ...Typography.caption, color: Colors.textMuted },
  completionBadge: { width: 32, height: 32, borderRadius: Radii.full, alignItems: 'center', justifyContent: 'center' },
  pctLabel: { ...Typography.caption, color: Colors.textMuted, fontWeight: '700' },
  barBg: { height: 6, backgroundColor: Colors.border, borderRadius: Radii.full, overflow: 'hidden' },
  barFill: { height: '100%', borderRadius: Radii.full },
  empty: { alignItems: 'center', paddingTop: Spacing.xl, gap: Spacing.sm },
  emptyText: { ...Typography.body, color: Colors.textMuted },
  emptySubText: { ...Typography.bodySmall, color: Colors.textMuted, textAlign: 'center' },
});
