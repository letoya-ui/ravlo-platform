import React, { useState, useEffect } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, Animated,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radii, Typography } from '../theme';
import { useProgressStore } from '../store/progressStore';
import { MODULES, QuizQuestion } from '../data/modules';
import { api } from '../services/api';

type QuizState = 'idle' | 'active' | 'passed' | 'failed';

export default function LessonScreen({ route, navigation }: any) {
  const { moduleId, lessonIndex } = route.params;
  const module = MODULES.find(m => m.id === moduleId);
  const { isComplete, markComplete, markIncomplete } = useProgressStore();
  const [marking, setMarking] = useState(false);

  // Quiz state
  const [quizState, setQuizState] = useState<QuizState>('idle');
  const [currentQ, setCurrentQ] = useState(0);
  const [answers, setAnswers] = useState<number[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [showFeedback, setShowFeedback] = useState(false);

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
  const quiz = lesson.quiz || [];

  const handleToggle = async () => {
    if (complete) {
      setMarking(true);
      await markIncomplete(moduleId, lessonIndex);
      setMarking(false);
      return;
    }
    if (quiz.length > 0 && quizState !== 'passed') {
      setQuizState('active');
      setCurrentQ(0);
      setAnswers([]);
      setSelected(null);
      setShowFeedback(false);
    } else {
      await doMarkComplete();
    }
  };

  const doMarkComplete = async () => {
    setMarking(true);
    await markComplete(moduleId, lessonIndex);
    setMarking(false);
  };

  const handleSelectOption = (idx: number) => {
    if (showFeedback) return;
    setSelected(idx);
    setShowFeedback(true);
  };

  const handleNextQuestion = () => {
    if (selected === null) return;
    const newAnswers = [...answers, selected];
    setAnswers(newAnswers);
    setSelected(null);
    setShowFeedback(false);

    if (currentQ + 1 < quiz.length) {
      setCurrentQ(currentQ + 1);
    } else {
      // Score the quiz
      const correct = newAnswers.filter((a, i) => a === quiz[i].correctIndex).length;
      const score = Math.round((correct / quiz.length) * 100);
      const passed = score >= 70;

      // Report score to backend
      api.post('/mobile/academy/lesson/score', {
        module_id: moduleId,
        lesson_index: lessonIndex,
        score,
      }).catch(() => {});

      if (passed) {
        setQuizState('passed');
        doMarkComplete();
      } else {
        setQuizState('failed');
      }
    }
  };

  const handleRetryQuiz = () => {
    setQuizState('active');
    setCurrentQ(0);
    setAnswers([]);
    setSelected(null);
    setShowFeedback(false);
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

  const renderQuiz = () => {
    if (quizState === 'idle') return null;

    if (quizState === 'passed') {
      const correct = answers.filter((a, i) => a === quiz[i].correctIndex).length;
      const score = Math.round((correct / quiz.length) * 100);
      return (
        <View style={styles.quizResultCard}>
          <Ionicons name="checkmark-circle" size={40} color={Colors.success} />
          <Text style={styles.quizResultTitle}>Quiz Passed!</Text>
          <Text style={styles.quizResultScore}>{score}% — {correct}/{quiz.length} correct</Text>
          <Text style={styles.quizResultDesc}>Lesson marked complete. Keep going!</Text>
        </View>
      );
    }

    if (quizState === 'failed') {
      const correct = answers.filter((a, i) => a === quiz[i].correctIndex).length;
      const score = Math.round((correct / quiz.length) * 100);
      return (
        <View style={[styles.quizResultCard, { borderColor: Colors.danger + '44' }]}>
          <Ionicons name="close-circle" size={40} color={Colors.danger} />
          <Text style={[styles.quizResultTitle, { color: Colors.danger }]}>Not Quite</Text>
          <Text style={styles.quizResultScore}>{score}% — need 70% to pass</Text>
          <Text style={styles.quizResultDesc}>Review the lesson content and try again.</Text>
          <TouchableOpacity style={[styles.retryBtn, { borderColor: Colors.danger }]} onPress={handleRetryQuiz} activeOpacity={0.8}>
            <Ionicons name="refresh-outline" size={16} color={Colors.danger} />
            <Text style={[styles.retryBtnText, { color: Colors.danger }]}>Retry Quiz</Text>
          </TouchableOpacity>
        </View>
      );
    }

    // Active quiz
    const q: QuizQuestion = quiz[currentQ];
    const isCorrect = selected !== null && selected === q.correctIndex;

    return (
      <View style={styles.quizCard}>
        <View style={styles.quizHeader}>
          <View style={[styles.quizProgressDots]}>
            {quiz.map((_, i) => (
              <View
                key={i}
                style={[
                  styles.quizDot,
                  i === currentQ && styles.quizDotActive,
                  i < currentQ && styles.quizDotDone,
                ]}
              />
            ))}
          </View>
          <Text style={styles.quizCounter}>Q{currentQ + 1} of {quiz.length}</Text>
        </View>

        <Text style={styles.quizQuestion}>{q.question}</Text>

        <View style={styles.optionsList}>
          {q.options.map((opt, idx) => {
            let optStyle = styles.option;
            let textStyle = styles.optionText;
            if (showFeedback) {
              if (idx === q.correctIndex) {
                optStyle = { ...styles.option, ...styles.optionCorrect } as any;
                textStyle = { ...styles.optionText, color: Colors.success } as any;
              } else if (idx === selected && selected !== q.correctIndex) {
                optStyle = { ...styles.option, ...styles.optionWrong } as any;
                textStyle = { ...styles.optionText, color: Colors.danger } as any;
              }
            } else if (selected === idx) {
              optStyle = { ...styles.option, ...styles.optionSelected } as any;
            }
            return (
              <TouchableOpacity
                key={idx}
                style={optStyle}
                onPress={() => handleSelectOption(idx)}
                activeOpacity={showFeedback ? 1 : 0.75}
              >
                <View style={styles.optionLetter}>
                  <Text style={styles.optionLetterText}>{String.fromCharCode(65 + idx)}</Text>
                </View>
                <Text style={textStyle}>{opt}</Text>
              </TouchableOpacity>
            );
          })}
        </View>

        {showFeedback && (
          <View style={[styles.explanationBox, isCorrect ? styles.explanationCorrect : styles.explanationWrong]}>
            <Ionicons name={isCorrect ? 'checkmark-circle' : 'information-circle'} size={16} color={isCorrect ? Colors.success : Colors.warning} />
            <Text style={[styles.explanationText, { color: isCorrect ? Colors.success : Colors.warning }]}>
              {q.explanation}
            </Text>
          </View>
        )}

        {showFeedback && (
          <TouchableOpacity
            style={[styles.nextQBtn, { backgroundColor: module.color }]}
            onPress={handleNextQuestion}
            activeOpacity={0.85}
          >
            <Text style={styles.nextQBtnText}>
              {currentQ + 1 < quiz.length ? 'Next Question' : 'See Results'}
            </Text>
            <Ionicons name="arrow-forward" size={16} color={Colors.white} />
          </TouchableOpacity>
        )}
      </View>
    );
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
            {quiz.length > 0 && (
              <>
                <View style={styles.metaDot} />
                <Ionicons name="help-circle-outline" size={12} color={Colors.textMuted} />
                <Text style={styles.lessonDuration}>{quiz.length}-question quiz</Text>
              </>
            )}
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
        {quizState === 'idle' && (
          <>
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
          </>
        )}

        {/* Quiz Section */}
        {quizState !== 'idle' && renderQuiz()}

        {/* Mark complete / Start quiz button */}
        {(quizState === 'idle' || quizState === 'passed') && (
          <TouchableOpacity
            style={[styles.completeBtn, complete && styles.completeBtnDone]}
            onPress={handleToggle}
            disabled={marking}
            activeOpacity={0.8}
          >
            <Ionicons
              name={complete ? 'checkmark-circle' : (quiz.length > 0 && !complete ? 'help-circle-outline' : 'checkmark-circle-outline')}
              size={20}
              color={complete ? Colors.white : module.color}
            />
            <Text style={[styles.completeBtnText, complete && styles.completeBtnTextDone]}>
              {complete ? 'Marked Complete' : quiz.length > 0 ? 'Take Quiz to Complete' : 'Mark as Complete'}
            </Text>
          </TouchableOpacity>
        )}

        {/* Navigation */}
        {(quizState === 'idle' || complete) && (
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
        )}
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

  // Quiz styles
  quizCard: {
    backgroundColor: Colors.surface, borderRadius: Radii.md, padding: Spacing.lg,
    borderWidth: 1, borderColor: Colors.border, marginBottom: Spacing.lg,
  },
  quizHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: Spacing.md },
  quizProgressDots: { flexDirection: 'row', gap: 6 },
  quizDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: Colors.border },
  quizDotActive: { backgroundColor: Colors.blueprint, width: 20 },
  quizDotDone: { backgroundColor: Colors.success },
  quizCounter: { ...Typography.caption, color: Colors.textMuted, fontWeight: '600' },
  quizQuestion: { ...Typography.body, color: Colors.textPrimary, fontWeight: '700', lineHeight: 24, marginBottom: Spacing.md },
  optionsList: { gap: 8, marginBottom: Spacing.md },
  option: {
    flexDirection: 'row', alignItems: 'flex-start', gap: Spacing.sm,
    padding: Spacing.md, borderRadius: Radii.md, borderWidth: 1.5, borderColor: Colors.border,
    backgroundColor: Colors.background,
  },
  optionSelected: { borderColor: Colors.blueprint, backgroundColor: Colors.blueprint + '10' } as any,
  optionCorrect: { borderColor: Colors.success, backgroundColor: Colors.success + '10' } as any,
  optionWrong: { borderColor: Colors.danger, backgroundColor: Colors.danger + '10' } as any,
  optionLetter: {
    width: 24, height: 24, borderRadius: 12, backgroundColor: Colors.border + '80',
    alignItems: 'center', justifyContent: 'center', flexShrink: 0,
  },
  optionLetterText: { fontSize: 11, fontWeight: '800', color: Colors.textMuted },
  optionText: { ...Typography.bodySmall, color: Colors.textPrimary, flex: 1, lineHeight: 20 },
  explanationBox: {
    flexDirection: 'row', alignItems: 'flex-start', gap: Spacing.sm,
    padding: Spacing.md, borderRadius: Radii.md, borderWidth: 1, marginBottom: Spacing.md,
  },
  explanationCorrect: { backgroundColor: Colors.success + '10', borderColor: Colors.success + '33' },
  explanationWrong: { backgroundColor: Colors.warning + '10', borderColor: Colors.warning + '33' },
  explanationText: { ...Typography.caption, flex: 1, lineHeight: 18 },
  nextQBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: Spacing.sm,
    borderRadius: Radii.md, paddingVertical: 12,
  },
  nextQBtnText: { ...Typography.bodySmall, color: Colors.white, fontWeight: '700' },
  quizResultCard: {
    backgroundColor: Colors.surface, borderRadius: Radii.md, padding: Spacing.xl,
    borderWidth: 1, borderColor: Colors.success + '44', alignItems: 'center',
    marginBottom: Spacing.lg, gap: Spacing.sm,
  },
  quizResultTitle: { ...Typography.h3, color: Colors.success },
  quizResultScore: { ...Typography.body, color: Colors.textPrimary, fontWeight: '700' },
  quizResultDesc: { ...Typography.bodySmall, color: Colors.textMuted, textAlign: 'center' },
  retryBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: Spacing.sm,
    paddingHorizontal: 16, paddingVertical: 10, borderRadius: Radii.md, borderWidth: 1.5,
  },
  retryBtnText: { ...Typography.bodySmall, fontWeight: '700' },

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
