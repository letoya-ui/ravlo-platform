import React, { useEffect, useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, SectionList, TouchableOpacity,
  RefreshControl, ActivityIndicator, Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radii, Typography } from '../theme';
import { useAuthStore } from '../store/authStore';
import { api } from '../services/api';

interface Task {
  id: number;
  title: string;
  description: string;
  due_date: string | null;
  priority: string;
  status: string;
}

const PRIORITY_COLORS: Record<string, string> = {
  High: Colors.danger,
  Normal: Colors.blueprint,
  Low: Colors.steel,
  Critical: Colors.danger,
};

export default function TasksScreen({ navigation }: any) {
  const { token } = useAuthStore();
  const [sections, setSections] = useState<Array<{ title: string; data: Task[] }>>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [completing, setCompleting] = useState<number | null>(null);

  const fetchTasks = useCallback(async () => {
    try {
      const res = await api.get('/mobile/lending/tasks', {
        headers: { Authorization: `Bearer ${token}` },
      });
      const { overdue = [], due_today = [], upcoming = [] } = res.data;
      const built = [];
      if (overdue.length) built.push({ title: 'Overdue', data: overdue });
      if (due_today.length) built.push({ title: 'Due Today', data: due_today });
      if (upcoming.length) built.push({ title: 'Upcoming', data: upcoming });
      setSections(built);
    } catch {
      Alert.alert('Error', 'Could not load tasks.');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { fetchTasks(); }, [fetchTasks]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchTasks();
    setRefreshing(false);
  }, [fetchTasks]);

  const completeTask = async (taskId: number) => {
    setCompleting(taskId);
    try {
      await api.post(`/mobile/lending/tasks/${taskId}/complete`, {}, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setSections(prev =>
        prev
          .map(s => ({ ...s, data: s.data.filter(t => t.id !== taskId) }))
          .filter(s => s.data.length > 0)
      );
    } catch {
      Alert.alert('Error', 'Could not complete task.');
    } finally {
      setCompleting(null);
    }
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <ActivityIndicator color={Colors.blueprint} style={{ flex: 1 }} />
      </SafeAreaView>
    );
  }

  const totalCount = sections.reduce((acc, s) => acc + s.data.length, 0);

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Tasks</Text>
        <Text style={styles.subtitle}>{totalCount} open</Text>
      </View>

      <SectionList
        sections={sections}
        keyExtractor={t => String(t.id)}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.blueprint} />}
        contentContainerStyle={styles.listContent}
        ListEmptyComponent={
          <View style={styles.empty}>
            <Ionicons name="checkmark-circle-outline" size={48} color={Colors.success} />
            <Text style={styles.emptyText}>All caught up!</Text>
          </View>
        }
        renderSectionHeader={({ section }) => (
          <View style={[styles.sectionHeader, section.title === 'Overdue' && styles.sectionHeaderDanger]}>
            <Text style={[styles.sectionTitle, section.title === 'Overdue' && styles.sectionTitleDanger]}>
              {section.title}
            </Text>
            <Text style={styles.sectionCount}>{section.data.length}</Text>
          </View>
        )}
        renderItem={({ item, section }) => {
          const priorityColor = PRIORITY_COLORS[item.priority] || Colors.steel;
          const isOverdue = section.title === 'Overdue';
          return (
            <View style={[styles.taskCard, isOverdue && styles.taskCardOverdue]}>
              <View style={[styles.priorityBar, { backgroundColor: priorityColor }]} />
              <View style={styles.taskBody}>
                <Text style={styles.taskTitle}>{item.title}</Text>
                {item.description ? (
                  <Text style={styles.taskDesc} numberOfLines={2}>{item.description}</Text>
                ) : null}
                <View style={styles.taskMeta}>
                  {item.due_date ? (
                    <View style={styles.metaChip}>
                      <Ionicons name="calendar-outline" size={11} color={isOverdue ? Colors.danger : Colors.textMuted} />
                      <Text style={[styles.metaText, isOverdue && { color: Colors.danger }]}>
                        {item.due_date}
                      </Text>
                    </View>
                  ) : null}
                  <View style={[styles.metaChip, { backgroundColor: priorityColor + '22' }]}>
                    <Text style={[styles.metaText, { color: priorityColor }]}>{item.priority}</Text>
                  </View>
                </View>
              </View>
              <TouchableOpacity
                style={styles.completeBtn}
                onPress={() => completeTask(item.id)}
                disabled={completing === item.id}
              >
                {completing === item.id
                  ? <ActivityIndicator size="small" color={Colors.success} />
                  : <Ionicons name="checkmark-circle-outline" size={26} color={Colors.success} />}
              </TouchableOpacity>
            </View>
          );
        }}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: Spacing.lg, paddingTop: Spacing.md, paddingBottom: Spacing.sm },
  title: { ...Typography.h2, color: Colors.textPrimary },
  subtitle: { ...Typography.bodySmall, color: Colors.textMuted },
  listContent: { paddingHorizontal: Spacing.lg, paddingBottom: Spacing.xl },
  sectionHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: Spacing.sm, marginTop: Spacing.sm },
  sectionHeaderDanger: {},
  sectionTitle: { ...Typography.label, color: Colors.textMuted },
  sectionTitleDanger: { color: Colors.danger },
  sectionCount: { ...Typography.caption, color: Colors.textMuted, backgroundColor: Colors.surface, borderRadius: Radii.full, paddingHorizontal: 8, paddingVertical: 2 },
  taskCard: { flexDirection: 'row', backgroundColor: Colors.surface, borderRadius: Radii.md, borderWidth: 1, borderColor: Colors.border, marginBottom: Spacing.sm, overflow: 'hidden' },
  taskCardOverdue: { borderColor: Colors.danger + '44' },
  priorityBar: { width: 4 },
  taskBody: { flex: 1, padding: Spacing.md },
  taskTitle: { ...Typography.bodySmall, color: Colors.textPrimary, fontWeight: '600' },
  taskDesc: { ...Typography.caption, color: Colors.textMuted, marginTop: 3 },
  taskMeta: { flexDirection: 'row', gap: Spacing.sm, marginTop: Spacing.sm },
  metaChip: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 6, paddingVertical: 2, borderRadius: Radii.full, backgroundColor: Colors.background },
  metaText: { fontSize: 10, color: Colors.textMuted },
  completeBtn: { padding: Spacing.md, justifyContent: 'center' },
  empty: { alignItems: 'center', paddingTop: 80, gap: Spacing.md },
  emptyText: { ...Typography.body, color: Colors.textMuted },
});
