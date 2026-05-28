import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  FlatList,
  StyleSheet,
  TouchableOpacity,
  RefreshControl,
  Alert,
  ActivityIndicator,
  ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radii, Typography } from '../theme';
import { api } from '../services/api';

interface Course {
  id: number;
  title: string;
  description: string;
  level: string;
  category: string;
  duration: string;
}

const FILTERS = ['All', 'Beginner', 'Advanced'];

const LEVEL_COLORS: Record<string, string> = {
  Beginner: Colors.success,
  Intermediate: Colors.warning,
  Advanced: Colors.danger,
};

export default function CourseListScreen({ navigation }: any) {
  const [courses, setCourses] = useState<Course[]>([]);
  const [filtered, setFiltered] = useState<Course[]>([]);
  const [activeFilter, setActiveFilter] = useState('All');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchCourses = useCallback(async () => {
    try {
      const res = await api.get('/mobile/academy/courses');
      const data: Course[] = res.data.courses || [];
      setCourses(data);
      setFiltered(activeFilter === 'All' ? data : data.filter((c) => c.level === activeFilter));
    } catch (err: any) {
      Alert.alert('Error', err.response?.data?.error || 'Could not load courses.');
    } finally {
      setLoading(false);
    }
  }, [activeFilter]);

  useEffect(() => { fetchCourses(); }, [fetchCourses]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchCourses();
    setRefreshing(false);
  }, [fetchCourses]);

  const applyFilter = (f: string) => {
    setActiveFilter(f);
    setFiltered(f === 'All' ? courses : courses.filter((c) => c.level === f));
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.centered}><ActivityIndicator size="large" color={Colors.blueprint} /></View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Courses</Text>
      </View>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.filterScroll} contentContainerStyle={styles.filterRow}>
        {FILTERS.map((f) => (
          <TouchableOpacity
            key={f}
            style={[styles.filterChip, activeFilter === f && styles.filterChipActive]}
            onPress={() => applyFilter(f)}
          >
            <Text style={[styles.filterText, activeFilter === f && styles.filterTextActive]}>{f}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>
      <FlatList
        data={filtered}
        keyExtractor={(item) => String(item.id)}
        contentContainerStyle={styles.grid}
        numColumns={2}
        columnWrapperStyle={styles.row}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.blueprint} />}
        ListEmptyComponent={
          <View style={styles.empty}>
            <Ionicons name="book-outline" size={48} color={Colors.textMuted} />
            <Text style={styles.emptyText}>No courses found</Text>
          </View>
        }
        renderItem={({ item }) => {
          const levelColor = LEVEL_COLORS[item.level] || Colors.blueprint;
          return (
            <TouchableOpacity
              style={styles.card}
              onPress={() => navigation.navigate('CourseDetail', { courseId: item.id })}
              activeOpacity={0.75}
            >
              <View style={[styles.cardIcon, { backgroundColor: levelColor + '22' }]}>
                <Ionicons name="book-outline" size={24} color={levelColor} />
              </View>
              <Text style={styles.cardTitle} numberOfLines={2}>{item.title}</Text>
              <View style={styles.cardMeta}>
                <View style={[styles.levelBadge, { backgroundColor: levelColor + '22' }]}>
                  <Text style={[styles.levelText, { color: levelColor }]}>{item.level}</Text>
                </View>
                {item.duration ? <Text style={styles.duration}>{item.duration}</Text> : null}
              </View>
            </TouchableOpacity>
          );
        }}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  header: { paddingHorizontal: Spacing.lg, paddingTop: Spacing.md, paddingBottom: Spacing.sm },
  title: { ...Typography.h2, color: Colors.textPrimary },
  filterScroll: { flexGrow: 0 },
  filterRow: { paddingHorizontal: Spacing.lg, paddingBottom: Spacing.md, gap: Spacing.sm },
  filterChip: {
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.xs + 2,
    borderRadius: Radii.full,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.surface,
  },
  filterChipActive: { borderColor: Colors.blueprint, backgroundColor: Colors.blueprint + '22' },
  filterText: { ...Typography.caption, color: Colors.textMuted, fontWeight: '600' },
  filterTextActive: { color: Colors.blueprint },
  grid: { paddingHorizontal: Spacing.lg, paddingBottom: Spacing.xl },
  row: { gap: Spacing.sm, marginBottom: Spacing.sm },
  card: {
    flex: 1,
    backgroundColor: Colors.surface,
    borderRadius: Radii.md,
    padding: Spacing.md,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  cardIcon: {
    width: 48,
    height: 48,
    borderRadius: Radii.sm,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: Spacing.sm,
  },
  cardTitle: { ...Typography.bodySmall, color: Colors.textPrimary, fontWeight: '600', marginBottom: Spacing.sm },
  cardMeta: { gap: 4 },
  levelBadge: { borderRadius: Radii.full, paddingHorizontal: 8, paddingVertical: 2, alignSelf: 'flex-start' },
  levelText: { ...Typography.caption, fontWeight: '700' },
  duration: { ...Typography.caption, color: Colors.textMuted },
  empty: { alignItems: 'center', paddingTop: Spacing.xxl, gap: Spacing.md },
  emptyText: { ...Typography.body, color: Colors.textMuted },
});
