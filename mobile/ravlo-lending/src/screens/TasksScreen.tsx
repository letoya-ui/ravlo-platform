import React, { useEffect, useState, useCallback } from 'react';
import { View, Text, StyleSheet, FlatList, TouchableOpacity, RefreshControl, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radii, Typography } from '../theme';
import { api } from '../services/api';

const PRIORITY_COLORS: Record<string, string> = { High: '#EF4444', Normal: Colors.info, Low: Colors.steel };

export default function TasksScreen() {
  const [tasks, setTasks] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/mobile/lending/tasks');
      setTasks(res.data.tasks || []);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  const onRefresh = useCallback(async () => { setRefreshing(true); await fetch(); setRefreshing(false); }, [fetch]);

  const complete = async (id: number) => {
    try {
      await api.post(`/mobile/lending/tasks/${id}/complete`);
      setTasks(prev => prev.filter(t => t.id !== id));
    } catch (e) { console.error(e); }
  };

  const fmtDate = (d: string | null) => {
    if (!d) return null;
    try {
      const date = new Date(d);
      const today = new Date(); today.setHours(0,0,0,0);
      const diff = Math.round((date.getTime() - today.getTime()) / 86400000);
      if (diff < 0) return { label: `${Math.abs(diff)}d overdue`, color: '#EF4444' };
      if (diff === 0) return { label: 'Due today', color: Colors.warning };
      if (diff === 1) return { label: 'Due tomorrow', color: Colors.softGlow };
      return { label: `Due ${date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`, color: Colors.textMuted };
    } catch { return null; }
  };

  const overdueTasks = tasks.filter(t => t.is_overdue);
  const todayTasks = tasks.filter(t => !t.is_overdue && t.due_date === new Date().toISOString().split('T')[0]);
  const otherTasks = tasks.filter(t => !t.is_overdue && t.due_date !== new Date().toISOString().split('T')[0]);

  const renderTask = ({ item }: { item: any }) => {
    const priorityColor = PRIORITY_COLORS[item.priority] || Colors.steel;
    const dateInfo = fmtDate(item.due_date);
    return (
      <View style={[styles.row, item.is_overdue && styles.rowOverdue]}>
        <TouchableOpacity style={styles.checkbox} onPress={() => complete(item.id)}>
          <Ionicons name="ellipse-outline" size={24} color={priorityColor} />
        </TouchableOpacity>
        <View style={styles.rowContent}>
          <Text style={styles.taskTitle}>{item.title}</Text>
          {item.description ? <Text style={styles.taskDesc} numberOfLines={2}>{item.description}</Text> : null}
          <View style={styles.metaRow}>
            <View style={[styles.priorityBadge, { backgroundColor: priorityColor + '22', borderColor: priorityColor }]}>
              <Text style={[styles.priorityText, { color: priorityColor }]}>{item.priority}</Text>
            </View>
            {dateInfo && <Text style={[styles.dateText, { color: dateInfo.color }]}>{dateInfo.label}</Text>}
          </View>
        </View>
        <TouchableOpacity style={styles.completeBtn} onPress={() => complete(item.id)}>
          <Ionicons name="checkmark-circle-outline" size={28} color={Colors.success} />
        </TouchableOpacity>
      </View>
    );
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Tasks</Text>
        <Text style={styles.count}>{tasks.length} pending</Text>
      </View>
      {loading && tasks.length === 0 ? (
        <View style={styles.centered}><ActivityIndicator color={Colors.blueprint} size="large" /></View>
      ) : (
        <FlatList
          data={[
            ...(overdueTasks.length > 0 ? [{ _section: 'Overdue', _id: 'overdue' }] : []),
            ...overdueTasks,
            ...(todayTasks.length > 0 ? [{ _section: 'Due Today', _id: 'today' }] : []),
            ...todayTasks,
            ...(otherTasks.length > 0 ? [{ _section: 'Upcoming', _id: 'upcoming' }] : []),
            ...otherTasks,
          ]}
          keyExtractor={(i: any) => i._id ? i._id : String(i.id)}
          contentContainerStyle={styles.list}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.blueprint} />}
          renderItem={({ item }: { item: any }) => {
            if (item._section) return <Text style={styles.sectionHeader}>{item._section}</Text>;
            return renderTask({ item });
          }}
          ListEmptyComponent={
            <View style={styles.empty}>
              <Ionicons name="checkmark-done-circle-outline" size={48} color={Colors.success} />
              <Text style={styles.emptyTitle}>All caught up!</Text>
              <Text style={styles.emptyText}>No pending tasks</Text>
            </View>
          }
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline', paddingHorizontal: Spacing.lg, paddingTop: Spacing.md, paddingBottom: Spacing.sm },
  title: { ...Typography.h2, color: Colors.textPrimary },
  count: { ...Typography.caption, color: Colors.textMuted },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  list: { paddingHorizontal: Spacing.lg, paddingBottom: 100 },
  sectionHeader: { ...Typography.label, color: Colors.textMuted, marginTop: Spacing.md, marginBottom: Spacing.sm },
  row: { flexDirection: 'row', gap: Spacing.sm, backgroundColor: Colors.surface, borderRadius: Radii.md, borderWidth: 1, borderColor: Colors.border, padding: Spacing.md, alignItems: 'flex-start', marginBottom: Spacing.sm },
  rowOverdue: { borderColor: '#EF444444', backgroundColor: '#EF444408' },
  checkbox: { paddingTop: 2 },
  rowContent: { flex: 1, gap: 3 },
  taskTitle: { ...Typography.body, color: Colors.textPrimary, fontWeight: '600' },
  taskDesc: { ...Typography.caption, color: Colors.textMuted },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm, marginTop: 4 },
  priorityBadge: { borderRadius: Radii.full, borderWidth: 1, paddingHorizontal: 6, paddingVertical: 2 },
  priorityText: { fontSize: 10, fontWeight: '700' },
  dateText: { ...Typography.caption, fontSize: 11 },
  completeBtn: { paddingTop: 2 },
  empty: { alignItems: 'center', justifyContent: 'center', paddingVertical: 80, gap: Spacing.sm },
  emptyTitle: { ...Typography.h3, color: Colors.textPrimary },
  emptyText: { ...Typography.body, color: Colors.textMuted },
});
