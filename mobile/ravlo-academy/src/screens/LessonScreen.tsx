import React, { useState, useEffect } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radii, Typography } from '../theme';
import { useProgressStore } from '../store/progressStore';
import { MODULES } from '../data/modules';

export default function LessonScreen({ route, navigation }: any) {
  const { moduleId, lessonIndex } = route.params;
  const module = MODULES.find(m => m.id === moduleId);
  const { isComplete, markComplete, markIncomplete } = useProgressStore();
  const [marking, setMarking] = useState(false);

  if (!module) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.centered}>
          <Text style={styles.errorText}>Lesson not found.</Text>
        </View>
      </SafeAreaView>
    );
  }

  const lesson = module.lessons[lessonIndex];
  const complete = isComplete(moduleId, lessonIndex);
  const hasPrev = lessonIndex > 0;
  const hasNext = lessonIndex < module.lessons.length - 1;

  const handleToggle = async () => {
    setMarking(true);
    if (complete) {
      await markIncomplete(moduleId, lessonIndex);
    } else {
      await markComplete(moduleId, lessonIndex);
    }
    setMarking(false);
  };

  const handleNext = () => {
    if (hasNext) {
      navigation.replace('Lesson', { moduleId, lessonIndex: lessonIndex + 1 });
    } else {
      navigation.goBack();
    }
  };

  const renderContent = (text: string) => {
    const lines = text.split('\n');
    return lines.map((line, i) => {
      if (line.startsWith('**') && line.endsWith('**')) {
        return (
          <Text key={i} style={styles.boldLine}>{line.replace(/\*\*/g, '')}</Text>
        );
      }
      if (line.startsWith('- ')) {
        return (
          <View key={i} style={styles.bulletRow}>
            <Text style={styles.bullet}>•</Text>
            <Text style={styles.bulletText}>{line.slice(2)}</Text>
          </View>
        );
      }
      if (line.trim() === '') return <View key={i} style={{ height: Spacing.sm }} />;
      return (
        <Text key={i} style={styles.bodyText}>{line}</Text>
      );
    });
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.nav}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Ionicons name="chevron-back" size={24} color={Colors.textPrimary} />
        </TouchableOpacity>
        <View style={styles.navCenter}>
          <Text style={styles.navModule} numberOfLines={1}>{module.title}</Text>
          <Text style={styles.navLesson}>{lessonIndex + 1} of {module.lessons.length}</Text>
        </View>
        <View style={{ width: 40 }} />
      </View>

      {/* Progress dots */}
      <View style={styles.dotsRow}>
        {module.lessons.map((_, i) => (
          <View
            key={i}
            style={[
              styles.dot,
              i === lessonIndex && styles.dotActive,
              isComplete(moduleId, i) && styles.dotDone,
            ]}
          />
        ))}
      </View>

      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        {/* Lesson header */}
        <View style={[styles.lessonHeader, { borderLeftColor: module.color }]}>
          <Text style={styles.lessonTitle}>{lesson.title}</Text>
          <View style={styles.lessonMeta}>
            <Ionicons name="time-outline" size={12} color={Colors.textMuted} />
            <Text style={styles.lessonDuration}>{lesson.duration}</Text>
            {complete && (
              <>
                <View style={styles.metaDot} />
                <Ionicons name="checkmark-circle" size={12} color={Colors.success} />
                <Text style={[styles.lessonDuration, { color: Colors.success }]}>Completed</Text>
              </>
            )}
          </View>
        </View>

        {/* Content */}
        <View style={styles.contentCard}>
          {renderContent(lesson.content)}
        </View>

        {/* Key Points */}
        <Text style={styles.sectionTitle}>Key Takeaways</Text>
        <View style={styles.keyPointsCard}>
          {lesson.keyPoints.map((point, i) => (
            <View key={i} style={[styles.keyPointRow, i < lesson.keyPoints.length - 1 && styles.keyPointBorder]}>
              <View style={[styles.keyPointDot, { backgroundColor: module.color }]} />
              <Text style={styles.keyPointText}>{point}</Text>
            </View>
          ))}
        </View>

        {/* Mark complete button */}
        <TouchableOpacity
          style={[styles.completeBtn, complete && styles.completeBtnDone]}
          onPress={handleToggle}
          disabled={marking}
          activeOpacity={0.8}
        >
          <Ionicons
            name={complete ? 'checkmark-circle' : 'checkmark-circle-outline'}
            size={20}
            color={complete ? Colors.white : module.color}
          />
          <Text style={[styles.completeBtnText, complete && styles.completeBtnTextDone]}>
            {complete ? 'Marked Complete' : 'Mark as Complete'}
          </Text>
        </TouchableOpacity>

        {/* Navigation */}
        <View style={styles.navButtons}>
          {hasPrev ? (
            <TouchableOpacity
              style={styles.navBtn}
              onPress={() => navigation.replace('Lesson', { moduleId, lessonIndex: lessonIndex - 1 })}
              activeOpacity={0.75}
            >
              <Ionicons name="chevron-back" size={18} color={Colors.textPrimary} />
              <Text style={styles.navBtnText}>Previous</Text>
            </TouchableOpacity>
          ) : <View style={{ flex: 1 }} />}

          <TouchableOpacity
            style={[styles.navBtnNext, { backgroundColor: module.color }]}
            onPress={handleNext}
            activeOpacity={0.85}
          >
            <Text style={styles.navBtnNextText}>{hasNext ? 'Next Lesson' : 'Finish Module'}</Text>
            <Ionicons name={hasNext ? 'chevron-forward' : 'checkmark'} size={18} color={Colors.white} />
          </TouchableOpacity>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
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
  navCenter: { flex: 1, alignItems: 'center' },
  navModule: { ...Typography.caption, color: Colors.textMuted },
  navLesson: { ...Typography.bodySmall, color: Colors.textPrimary, fontWeight: '700' },
  dotsRow: { flexDirection: 'row', gap: 4, paddingHorizontal: Spacing.lg, marginBottom: Spacing.sm, flexWrap: 'wrap' },
  dot: { height: 4, flex: 1, minWidth: 8, maxWidth: 24, borderRadius: 2, backgroundColor: Colors.border },
  dotActive: { backgroundColor: Colors.blueprint },
  dotDone: { backgroundColor: Colors.success },
  scroll: { padding: Spacing.lg, paddingBottom: Spacing.xxl },
  lessonHeader: { borderLeftWidth: 3, paddingLeft: Spacing.md, marginBottom: Spacing.lg },
  lessonTitle: { ...Typography.h3, color: Colors.textPrimary, marginBottom: 6 },
  lessonMeta: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  lessonDuration: { ...Typography.caption, color: Colors.textMuted },
  metaDot: { width: 3, height: 3, borderRadius: 1.5, backgroundColor: Colors.textMuted },
  contentCard: {
    backgroundColor: Colors.surface, borderRadius: Radii.md, padding: Spacing.lg,
    borderWidth: 1, borderColor: Colors.border, marginBottom: Spacing.lg,
  },
  bodyText: { ...Typography.bodySmall, color: Colors.textSecondary, lineHeight: 24 },
  boldLine: { ...Typography.bodySmall, color: Colors.textPrimary, fontWeight: '700', lineHeight: 24 },
  bulletRow: { flexDirection: 'row', gap: 8, marginVertical: 2 },
  bullet: { color: Colors.textMuted, marginTop: 2, fontSize: 14 },
  bulletText: { ...Typography.bodySmall, color: Colors.textSecondary, lineHeight: 22, flex: 1 },
  sectionTitle: { ...Typography.label, color: Colors.textMuted, marginBottom: Spacing.md },
  keyPointsCard: {
    backgroundColor: Colors.surface, borderRadius: Radii.md,
    borderWidth: 1, borderColor: Colors.border, marginBottom: Spacing.lg, overflow: 'hidden',
  },
  keyPointRow: { flexDirection: 'row', alignItems: 'flex-start', gap: Spacing.sm, padding: Spacing.md },
  keyPointBorder: { borderBottomWidth: 1, borderBottomColor: Colors.border },
  keyPointDot: { width: 7, height: 7, borderRadius: 3.5, marginTop: 6 },
  keyPointText: { ...Typography.bodySmall, color: Colors.textPrimary, flex: 1, lineHeight: 20 },
  completeBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: Spacing.sm,
    borderRadius: Radii.md, paddingVertical: 14, marginBottom: Spacing.md,
    borderWidth: 1.5, borderColor: Colors.border, backgroundColor: Colors.surface,
  },
  completeBtnDone: { backgroundColor: Colors.success, borderColor: Colors.success },
  completeBtnText: { ...Typography.body, fontWeight: '700', color: Colors.textPrimary },
  completeBtnTextDone: { color: Colors.white },
  navButtons: { flexDirection: 'row', gap: Spacing.sm, marginTop: Spacing.sm },
  navBtn: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 4, borderRadius: Radii.md, paddingVertical: 12,
    backgroundColor: Colors.surface, borderWidth: 1, borderColor: Colors.border,
  },
  navBtnText: { ...Typography.bodySmall, color: Colors.textPrimary, fontWeight: '600' },
  navBtnNext: {
    flex: 2, flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 4, borderRadius: Radii.md, paddingVertical: 12,
  },
  navBtnNextText: { ...Typography.bodySmall, color: Colors.white, fontWeight: '700' },
});
