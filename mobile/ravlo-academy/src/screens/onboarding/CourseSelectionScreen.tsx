import React, { useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator, Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radii, Typography } from '../../theme';
import { COURSES } from '../../data/modules';
import { useAuthStore } from '../../store/authStore';
import { api } from '../../services/api';

interface Props {
  onDone: () => void;
}

export default function CourseSelectionScreen({ onDone }: Props) {
  const { setChosenCourse } = useAuthStore();
  const [selected, setSelected] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const handleConfirm = async () => {
    if (!selected) return;
    setSaving(true);
    try {
      const res = await api.post('/mobile/academy/choose-course', { course_id: selected });
      setChosenCourse(res.data.chosen_course);
      onDone();
    } catch (err: any) {
      const msg = err?.response?.data?.error || 'Could not save your selection. Please try again.';
      if (err?.response?.status === 409) {
        setChosenCourse(selected);
        onDone();
        return;
      }
      Alert.alert('Error', msg);
    } finally {
      setSaving(false);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <View style={styles.iconCircle}>
          <Ionicons name="school-outline" size={32} color={Colors.blueprint} />
        </View>
        <Text style={styles.title}>Choose Your Course</Text>
        <Text style={styles.subtitle}>
          Your subscription includes one full course. Additional courses can be unlocked anytime.
        </Text>
      </View>

      <ScrollView contentContainerStyle={styles.list} showsVerticalScrollIndicator={false}>
        {COURSES.map(course => {
          const isSelected = selected === course.id;
          return (
            <TouchableOpacity
              key={course.id}
              style={[styles.card, isSelected && { borderColor: course.color, borderWidth: 2 }]}
              onPress={() => setSelected(course.id)}
              activeOpacity={0.8}
            >
              <View style={styles.cardLeft}>
                <View style={[styles.iconBox, { backgroundColor: course.color + '22' }]}>
                  <Ionicons name={course.icon as any} size={22} color={course.color} />
                </View>
                <View style={styles.cardInfo}>
                  <Text style={styles.cardTitle}>{course.title}</Text>
                  <Text style={styles.cardDesc} numberOfLines={2}>{course.description}</Text>
                  <View style={styles.metaRow}>
                    <Ionicons name="book-outline" size={11} color={Colors.textMuted} />
                    <Text style={styles.metaText}>{course.lessons.length} lessons</Text>
                    <View style={styles.metaDot} />
                    <Ionicons name="time-outline" size={11} color={Colors.textMuted} />
                    <Text style={styles.metaText}>{course.creditHours} credit hrs</Text>
                  </View>
                </View>
              </View>
              <View style={[styles.radio, isSelected && { backgroundColor: course.color, borderColor: course.color }]}>
                {isSelected && <Ionicons name="checkmark" size={14} color={Colors.white} />}
              </View>
            </TouchableOpacity>
          );
        })}

        <View style={styles.enrollNote}>
          <Ionicons name="checkmark-circle-outline" size={16} color={Colors.success} />
          <Text style={styles.enrollNoteText}>
            Your subscription covers one full course — all lessons, quizzes, and your certificate of completion.
          </Text>
        </View>
      </ScrollView>

      <View style={styles.footer}>
        <TouchableOpacity
          style={[styles.confirmBtn, !selected && styles.confirmBtnDisabled]}
          onPress={handleConfirm}
          disabled={!selected || saving}
          activeOpacity={0.85}
        >
          {saving
            ? <ActivityIndicator color={Colors.white} size="small" />
            : (
              <>
                <Text style={styles.confirmBtnText}>Start Learning</Text>
                <Ionicons name="arrow-forward" size={18} color={Colors.white} />
              </>
            )
          }
        </TouchableOpacity>
        <Text style={styles.footerNote}>Additional courses can be unlocked anytime from the Learn screen.</Text>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  header: {
    alignItems: 'center',
    paddingHorizontal: Spacing.xl,
    paddingTop: Spacing.lg,
    paddingBottom: Spacing.md,
  },
  iconCircle: {
    width: 64, height: 64, borderRadius: 32,
    backgroundColor: Colors.surface, alignItems: 'center', justifyContent: 'center',
    marginBottom: Spacing.md,
    borderWidth: 1, borderColor: Colors.border,
  },
  title: { ...Typography.h2, color: Colors.textPrimary, textAlign: 'center', marginBottom: 8 },
  subtitle: { ...Typography.body, color: Colors.textSecondary, textAlign: 'center', lineHeight: 22 },
  list: { padding: Spacing.lg, paddingBottom: Spacing.xl },
  card: {
    backgroundColor: Colors.surface, borderRadius: Radii.md, padding: Spacing.md,
    marginBottom: Spacing.sm, borderWidth: 1, borderColor: Colors.border,
    flexDirection: 'row', alignItems: 'center',
  },
  cardLeft: { flex: 1, flexDirection: 'row', alignItems: 'flex-start', gap: Spacing.sm },
  iconBox: { width: 44, height: 44, borderRadius: Radii.sm, alignItems: 'center', justifyContent: 'center', flexShrink: 0 },
  cardInfo: { flex: 1, minWidth: 0 },
  cardTitle: { ...Typography.bodySmall, color: Colors.textPrimary, fontWeight: '700', marginBottom: 3 },
  cardDesc: { ...Typography.caption, color: Colors.textMuted, lineHeight: 17, marginBottom: 6 },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  metaText: { fontSize: 10, color: Colors.textMuted, fontWeight: '500' },
  metaDot: { width: 3, height: 3, borderRadius: 1.5, backgroundColor: Colors.textMuted },
  radio: {
    width: 24, height: 24, borderRadius: 12, borderWidth: 2, borderColor: Colors.border,
    alignItems: 'center', justifyContent: 'center', flexShrink: 0, marginLeft: Spacing.sm,
  },
  enrollNote: {
    flexDirection: 'row', alignItems: 'flex-start', gap: Spacing.sm,
    backgroundColor: Colors.success + '11', borderRadius: Radii.md, padding: Spacing.md,
    borderWidth: 1, borderColor: Colors.success + '33', marginTop: Spacing.sm,
  },
  enrollNoteText: { ...Typography.caption, color: Colors.success, flex: 1, lineHeight: 18 },
  footer: {
    padding: Spacing.lg, paddingBottom: Spacing.xl,
    borderTopWidth: 1, borderTopColor: Colors.border,
    backgroundColor: Colors.background,
  },
  confirmBtn: {
    backgroundColor: Colors.blueprint, borderRadius: Radii.md, paddingVertical: 14,
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: Spacing.sm,
  },
  confirmBtnDisabled: { opacity: 0.4 },
  confirmBtnText: { ...Typography.body, color: Colors.white, fontWeight: '700', fontSize: 16 },
  footerNote: { ...Typography.caption, color: Colors.textMuted, textAlign: 'center', marginTop: Spacing.sm },
});
