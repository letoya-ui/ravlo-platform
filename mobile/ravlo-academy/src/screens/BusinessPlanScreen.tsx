import React, { useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  TextInput, ActivityIndicator, KeyboardAvoidingView, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radii, Typography } from '../theme';
import { api } from '../services/api';

interface Answers {
  role: string;
  goal: string;
  challenge: string;
  market: string;
  experience: string;
}

const QUESTIONS = [
  {
    key: 'role' as keyof Answers,
    question: 'What is your role in real estate?',
    placeholder: 'e.g., Agent, Investor, Lender, Wholesaler...',
    icon: 'person-outline',
  },
  {
    key: 'goal' as keyof Answers,
    question: 'What is your #1 business goal for the next 12 months?',
    placeholder: 'e.g., Close 24 deals, build a 10-unit portfolio, originate $10M...',
    icon: 'flag-outline',
  },
  {
    key: 'challenge' as keyof Answers,
    question: 'What is your biggest challenge right now?',
    placeholder: 'e.g., Lead generation, capital access, time management...',
    icon: 'warning-outline',
  },
  {
    key: 'market' as keyof Answers,
    question: 'What market or niche do you focus on?',
    placeholder: 'e.g., Dallas TX single-family, NYC commercial, nationwide DSCR loans...',
    icon: 'location-outline',
  },
  {
    key: 'experience' as keyof Answers,
    question: 'How many years of experience do you have?',
    placeholder: 'e.g., 0-1 years just starting, 5 years, 15+ years veteran...',
    icon: 'school-outline',
  },
];

export default function BusinessPlanScreen() {
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState<Answers>({ role: '', goal: '', challenge: '', market: '', experience: '' });
  const [plan, setPlan] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const currentQ = QUESTIONS[step];
  const isLastStep = step === QUESTIONS.length - 1;
  const allDone = plan !== null;

  const handleNext = async () => {
    if (!answers[currentQ.key].trim()) return;
    if (isLastStep) {
      setLoading(true);
      setError(null);
      try {
        const res = await api.post('/mobile/academy/business-plan', { answers });
        setPlan(res.data.plan);
      } catch (e: any) {
        setError(e.response?.data?.error || 'Failed to generate plan. Please try again.');
      } finally {
        setLoading(false);
      }
    } else {
      setStep(s => s + 1);
    }
  };

  const handleReset = () => {
    setStep(0);
    setAnswers({ role: '', goal: '', challenge: '', market: '', experience: '' });
    setPlan(null);
    setError(null);
  };

  const renderPlan = (text: string) => {
    const lines = text.split('\n');
    return lines.map((line, i) => {
      if (line.startsWith('## ') || line.startsWith('# ')) {
        return <Text key={i} style={styles.planHeading}>{line.replace(/^#+\s/, '')}</Text>;
      }
      if (line.startsWith('**') && line.endsWith('**')) {
        return <Text key={i} style={styles.planBold}>{line.replace(/\*\*/g, '')}</Text>;
      }
      if (line.startsWith('- ') || line.startsWith('• ')) {
        return (
          <View key={i} style={styles.planBulletRow}>
            <Text style={styles.planBullet}>•</Text>
            <Text style={styles.planBulletText}>{line.slice(2)}</Text>
          </View>
        );
      }
      if (line.match(/^\d+\./)) {
        return (
          <View key={i} style={styles.planBulletRow}>
            <Text style={styles.planBullet}>{line.match(/^\d+/)?.[0]}.</Text>
            <Text style={styles.planBulletText}>{line.replace(/^\d+\.\s*/, '')}</Text>
          </View>
        );
      }
      if (line.trim() === '') return <View key={i} style={{ height: Spacing.sm }} />;
      return <Text key={i} style={styles.planBody}>{line}</Text>;
    });
  };

  if (allDone) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.header}>
          <Text style={styles.headerTitle}>Your Business Plan</Text>
          <TouchableOpacity onPress={handleReset} style={styles.resetBtn}>
            <Ionicons name="refresh-outline" size={18} color={Colors.blueprint} />
            <Text style={styles.resetText}>Regenerate</Text>
          </TouchableOpacity>
        </View>
        <ScrollView contentContainerStyle={styles.planScroll} showsVerticalScrollIndicator={false}>
          <View style={styles.planCard}>
            {renderPlan(plan!)}
          </View>
        </ScrollView>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
        <View style={styles.header}>
          <Text style={styles.headerTitle}>Business Plan</Text>
          <Text style={styles.headerSub}>AI-powered in 5 questions</Text>
        </View>

        {/* Progress */}
        <View style={styles.progressRow}>
          {QUESTIONS.map((_, i) => (
            <View
              key={i}
              style={[styles.stepDot, i <= step && styles.stepDotActive, i < step && styles.stepDotDone]}
            />
          ))}
        </View>
        <Text style={styles.stepLabel}>Question {step + 1} of {QUESTIONS.length}</Text>

        <ScrollView contentContainerStyle={styles.formScroll} showsVerticalScrollIndicator={false} keyboardShouldPersistTaps="handled">
          <View style={styles.questionCard}>
            <View style={styles.questionIcon}>
              <Ionicons name={currentQ.icon as any} size={24} color={Colors.blueprint} />
            </View>
            <Text style={styles.questionText}>{currentQ.question}</Text>
            <TextInput
              style={styles.input}
              value={answers[currentQ.key]}
              onChangeText={val => setAnswers(prev => ({ ...prev, [currentQ.key]: val }))}
              placeholder={currentQ.placeholder}
              placeholderTextColor={Colors.textMuted}
              multiline
              numberOfLines={3}
              autoFocus
            />
          </View>

          {error && (
            <View style={styles.errorBox}>
              <Ionicons name="alert-circle-outline" size={16} color={Colors.danger} />
              <Text style={styles.errorText}>{error}</Text>
            </View>
          )}

          {/* Previous answers summary */}
          {step > 0 && (
            <View style={styles.summaryCard}>
              <Text style={styles.summaryTitle}>Your Answers So Far</Text>
              {QUESTIONS.slice(0, step).map((q, i) => (
                <View key={i} style={styles.summaryRow}>
                  <Text style={styles.summaryQ}>{q.question}</Text>
                  <Text style={styles.summaryA}>{answers[q.key]}</Text>
                </View>
              ))}
            </View>
          )}
        </ScrollView>

        <View style={styles.footer}>
          {step > 0 && (
            <TouchableOpacity style={styles.backBtn} onPress={() => setStep(s => s - 1)} activeOpacity={0.75}>
              <Ionicons name="chevron-back" size={18} color={Colors.textPrimary} />
              <Text style={styles.backBtnText}>Back</Text>
            </TouchableOpacity>
          )}
          <TouchableOpacity
            style={[
              styles.nextBtn,
              !answers[currentQ.key].trim() && styles.nextBtnDisabled,
            ]}
            onPress={handleNext}
            disabled={!answers[currentQ.key].trim() || loading}
            activeOpacity={0.85}
          >
            {loading ? (
              <ActivityIndicator color={Colors.white} size="small" />
            ) : (
              <>
                <Text style={styles.nextBtnText}>{isLastStep ? 'Generate Plan' : 'Next'}</Text>
                <Ionicons name={isLastStep ? 'sparkles-outline' : 'chevron-forward'} size={18} color={Colors.white} />
              </>
            )}
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  header: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingHorizontal: Spacing.lg, paddingTop: Spacing.md, paddingBottom: Spacing.sm,
  },
  headerTitle: { ...Typography.h2, color: Colors.textPrimary },
  headerSub: { ...Typography.caption, color: Colors.textMuted },
  resetBtn: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  resetText: { ...Typography.bodySmall, color: Colors.blueprint, fontWeight: '600' },
  progressRow: { flexDirection: 'row', gap: 6, paddingHorizontal: Spacing.lg, marginBottom: Spacing.xs },
  stepDot: {
    flex: 1, height: 4, borderRadius: 2, backgroundColor: Colors.border,
  },
  stepDotActive: { backgroundColor: Colors.blueprint },
  stepDotDone: { backgroundColor: Colors.success },
  stepLabel: { ...Typography.caption, color: Colors.textMuted, paddingHorizontal: Spacing.lg, marginBottom: Spacing.md },
  formScroll: { paddingHorizontal: Spacing.lg, paddingBottom: Spacing.xxl },
  questionCard: {
    backgroundColor: Colors.surface, borderRadius: Radii.lg, padding: Spacing.lg,
    borderWidth: 1, borderColor: Colors.border, marginBottom: Spacing.md,
  },
  questionIcon: {
    width: 48, height: 48, borderRadius: Radii.sm, backgroundColor: Colors.blueprint + '22',
    alignItems: 'center', justifyContent: 'center', marginBottom: Spacing.md,
  },
  questionText: { ...Typography.body, color: Colors.textPrimary, fontWeight: '700', marginBottom: Spacing.md, lineHeight: 26 },
  input: {
    ...Typography.bodySmall,
    color: Colors.textPrimary,
    backgroundColor: Colors.background,
    borderRadius: Radii.md,
    borderWidth: 1,
    borderColor: Colors.border,
    padding: Spacing.md,
    minHeight: 80,
    textAlignVertical: 'top',
  },
  errorBox: {
    flexDirection: 'row', alignItems: 'center', gap: Spacing.sm,
    backgroundColor: Colors.danger + '18', borderRadius: Radii.md,
    padding: Spacing.md, marginBottom: Spacing.md,
  },
  errorText: { ...Typography.bodySmall, color: Colors.danger, flex: 1 },
  summaryCard: {
    backgroundColor: Colors.surface, borderRadius: Radii.md, padding: Spacing.md,
    borderWidth: 1, borderColor: Colors.border,
  },
  summaryTitle: { ...Typography.caption, color: Colors.textMuted, fontWeight: '700', marginBottom: Spacing.sm },
  summaryRow: { marginBottom: Spacing.sm },
  summaryQ: { ...Typography.caption, color: Colors.textMuted },
  summaryA: { ...Typography.bodySmall, color: Colors.textSecondary, marginTop: 2 },
  footer: { flexDirection: 'row', gap: Spacing.sm, padding: Spacing.lg, paddingTop: Spacing.sm },
  backBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: Spacing.md, paddingVertical: 14,
    backgroundColor: Colors.surface, borderRadius: Radii.md, borderWidth: 1, borderColor: Colors.border,
  },
  backBtnText: { ...Typography.bodySmall, color: Colors.textPrimary, fontWeight: '600' },
  nextBtn: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: Spacing.sm,
    paddingVertical: 14, backgroundColor: Colors.blueprint, borderRadius: Radii.md,
  },
  nextBtnDisabled: { opacity: 0.4 },
  nextBtnText: { ...Typography.body, color: Colors.white, fontWeight: '700' },
  planScroll: { padding: Spacing.lg, paddingBottom: Spacing.xxl },
  planCard: {
    backgroundColor: Colors.surface, borderRadius: Radii.lg, padding: Spacing.lg,
    borderWidth: 1, borderColor: Colors.border,
  },
  planHeading: { ...Typography.h3, color: Colors.textPrimary, marginTop: Spacing.md, marginBottom: Spacing.sm },
  planBold: { ...Typography.bodySmall, color: Colors.textPrimary, fontWeight: '700', marginTop: Spacing.sm },
  planBody: { ...Typography.bodySmall, color: Colors.textSecondary, lineHeight: 24 },
  planBulletRow: { flexDirection: 'row', gap: 8, marginVertical: 3 },
  planBullet: { color: Colors.blueprint, fontSize: 14, marginTop: 2, minWidth: 16 },
  planBulletText: { ...Typography.bodySmall, color: Colors.textSecondary, lineHeight: 22, flex: 1 },
});
