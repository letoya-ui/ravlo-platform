import React, { useState, useRef, useCallback, useEffect } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, FlatList, StyleSheet,
  KeyboardAvoidingView, Platform, ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radii, Typography } from '../theme';
import { useAuthStore } from '../store/authStore';
import { useProgressStore } from '../store/progressStore';
import { COURSES } from '../data/modules';
import { api } from '../services/api';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
}

const STARTER_PROMPTS = [
  'Explain BRRRR strategy',
  'What is a DSCR loan?',
  'How do cap rates work?',
  'How to find off-market deals?',
  'Explain 1031 exchange',
];

export default function RavloAIScreen({ route }: any) {
  const { user } = useAuthStore();
  const { completed } = useProgressStore();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const flatListRef = useRef<FlatList>(null);

  const buildProgressPayload = useCallback(() => {
    const courseId = user?.chosen_course || 'residential';
    const course = COURSES.find(c => c.id === courseId);
    return {
      userId: user?.id || '',
      currentCourse: {
        id: courseId,
        name: course?.title || courseId,
        totalLessons: course?.lessons.length || 0,
        creditHours: course?.creditHours || 0,
      },
      completedLessonCount: completed.length,
      completedCourses: [] as string[],
      subscription: user?.university_tier || 'starter',
    };
  }, [user, completed]);

  // Auto-generate a progress check-in when the Coach tab is first opened
  useEffect(() => {
    const initial = route?.params?.initialPrompt;
    if (initial) {
      setInput(initial);
      return;
    }
    if (messages.length > 0) return;

    const generate = async () => {
      setLoading(true);
      try {
        const res = await api.post('/mobile/academy/chat', {
          messages: [{ role: 'user', content: 'Check in with me on my progress.' }],
          tier: user?.university_tier || 'starter',
          trigger: 'progress_checkin',
          progress: buildProgressPayload(),
        });
        const checkin: Message = {
          id: Date.now().toString(),
          role: 'assistant',
          content: res.data.reply || 'Hey! Ready to keep building your real estate knowledge?',
        };
        setMessages([checkin]);
      } catch {
        // Silent fail — empty state shows starter prompts
      } finally {
        setLoading(false);
      }
    };
    generate();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const send = useCallback(async (text: string) => {
    const userMsg: Message = { id: Date.now().toString(), role: 'user', content: text };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    const history = [...messages, userMsg].map(m => ({ role: m.role, content: m.content }));

    try {
      const res = await api.post('/mobile/academy/chat', {
        messages: history,
        tier: user?.university_tier || 'starter',
        trigger: 'general_chat',
        progress: buildProgressPayload(),
      });
      const aiMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: res.data.reply || res.data.message || 'No response.',
      };
      setMessages(prev => [...prev, aiMsg]);
    } catch (e: any) {
      const errMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: 'Sorry, I couldn\'t process that right now. Please try again.',
      };
      setMessages(prev => [...prev, errMsg]);
    } finally {
      setLoading(false);
    }
  }, [messages, user, buildProgressPayload]);

  const handleSend = () => {
    if (!input.trim() || loading) return;
    send(input.trim());
  };

  const handlePrompt = (p: string) => send(p);

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <View style={styles.aiIcon}>
          <Ionicons name="sparkles" size={18} color={Colors.blueprint} />
        </View>
        <View>
          <Text style={styles.title}>Ravlo AI Coach</Text>
          <Text style={styles.subtitle}>Real estate expertise, on demand</Text>
        </View>
      </View>

      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined} keyboardVerticalOffset={0}>
        {messages.length === 0 ? (
          <View style={styles.emptyState}>
            <View style={styles.emptyIcon}>
              <Ionicons name="sparkles-outline" size={36} color={Colors.blueprint} />
            </View>
            <Text style={styles.emptyTitle}>Ask me anything</Text>
            <Text style={styles.emptyDesc}>
              I'm your AI real estate coach. Ask about strategies, financing, investing, or get personalized advice.
            </Text>
            <View style={styles.starterList}>
              {STARTER_PROMPTS.map((p, i) => (
                <TouchableOpacity key={i} style={styles.starterBtn} onPress={() => handlePrompt(p)} activeOpacity={0.75}>
                  <Ionicons name="chatbubble-outline" size={13} color={Colors.blueprint} />
                  <Text style={styles.starterText}>{p}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>
        ) : (
          <FlatList
            ref={flatListRef}
            data={messages}
            keyExtractor={m => m.id}
            contentContainerStyle={styles.messageList}
            onContentSizeChange={() => flatListRef.current?.scrollToEnd({ animated: true })}
            showsVerticalScrollIndicator={false}
            renderItem={({ item }) => (
              <View style={[styles.msgRow, item.role === 'user' ? styles.msgRowUser : styles.msgRowAI]}>
                {item.role === 'assistant' && (
                  <View style={styles.aiBubbleIcon}>
                    <Ionicons name="sparkles" size={12} color={Colors.blueprint} />
                  </View>
                )}
                <View style={[styles.bubble, item.role === 'user' ? styles.bubbleUser : styles.bubbleAI]}>
                  <Text style={[styles.bubbleText, item.role === 'user' ? styles.bubbleTextUser : styles.bubbleTextAI]}>
                    {item.content}
                  </Text>
                </View>
              </View>
            )}
            ListFooterComponent={loading ? (
              <View style={[styles.msgRow, styles.msgRowAI]}>
                <View style={styles.aiBubbleIcon}>
                  <Ionicons name="sparkles" size={12} color={Colors.blueprint} />
                </View>
                <View style={[styles.bubble, styles.bubbleAI]}>
                  <ActivityIndicator size="small" color={Colors.blueprint} />
                </View>
              </View>
            ) : null}
          />
        )}

        <View style={styles.inputRow}>
          <TextInput
            style={styles.input}
            value={input}
            onChangeText={setInput}
            placeholder="Ask about real estate, investing, lending..."
            placeholderTextColor={Colors.textMuted}
            multiline
            maxLength={1000}
            onSubmitEditing={handleSend}
          />
          <TouchableOpacity
            style={[styles.sendBtn, (!input.trim() || loading) && styles.sendBtnDisabled]}
            onPress={handleSend}
            disabled={!input.trim() || loading}
            activeOpacity={0.8}
          >
            <Ionicons name="send" size={18} color={Colors.white} />
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  header: {
    flexDirection: 'row', alignItems: 'center', gap: Spacing.sm,
    paddingHorizontal: Spacing.lg, paddingTop: Spacing.md, paddingBottom: Spacing.sm,
  },
  aiIcon: {
    width: 38, height: 38, borderRadius: Radii.sm, backgroundColor: Colors.blueprint + '22',
    alignItems: 'center', justifyContent: 'center',
  },
  title: { ...Typography.body, color: Colors.textPrimary, fontWeight: '700' },
  subtitle: { ...Typography.caption, color: Colors.textMuted },
  emptyState: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: Spacing.xl },
  emptyIcon: {
    width: 72, height: 72, borderRadius: 36, backgroundColor: Colors.blueprint + '18',
    alignItems: 'center', justifyContent: 'center', marginBottom: Spacing.lg,
  },
  emptyTitle: { ...Typography.h3, color: Colors.textPrimary, marginBottom: Spacing.sm },
  emptyDesc: { ...Typography.bodySmall, color: Colors.textMuted, textAlign: 'center', marginBottom: Spacing.xl, lineHeight: 22 },
  starterList: { width: '100%', gap: Spacing.sm },
  starterBtn: {
    flexDirection: 'row', alignItems: 'center', gap: Spacing.sm,
    backgroundColor: Colors.surface, borderRadius: Radii.md, padding: Spacing.md,
    borderWidth: 1, borderColor: Colors.border,
  },
  starterText: { ...Typography.bodySmall, color: Colors.textSecondary, flex: 1 },
  messageList: { padding: Spacing.md, paddingBottom: Spacing.lg },
  msgRow: { flexDirection: 'row', marginBottom: Spacing.sm, alignItems: 'flex-end' },
  msgRowUser: { justifyContent: 'flex-end' },
  msgRowAI: { justifyContent: 'flex-start', gap: Spacing.xs },
  aiBubbleIcon: {
    width: 24, height: 24, borderRadius: 12, backgroundColor: Colors.blueprint + '22',
    alignItems: 'center', justifyContent: 'center', marginBottom: 2,
  },
  bubble: { maxWidth: '78%', borderRadius: Radii.md, padding: Spacing.md },
  bubbleUser: { backgroundColor: Colors.blueprint, borderBottomRightRadius: 4 },
  bubbleAI: { backgroundColor: Colors.surface, borderWidth: 1, borderColor: Colors.border, borderBottomLeftRadius: 4 },
  bubbleText: { ...Typography.bodySmall, lineHeight: 22 },
  bubbleTextUser: { color: Colors.white },
  bubbleTextAI: { color: Colors.textPrimary },
  inputRow: {
    flexDirection: 'row', alignItems: 'flex-end', gap: Spacing.sm,
    padding: Spacing.md, borderTopWidth: 1, borderTopColor: Colors.border,
  },
  input: {
    flex: 1, ...Typography.bodySmall, color: Colors.textPrimary,
    backgroundColor: Colors.surface, borderRadius: Radii.md,
    borderWidth: 1, borderColor: Colors.border,
    paddingHorizontal: Spacing.md, paddingVertical: 10,
    maxHeight: 120, textAlignVertical: 'top',
  },
  sendBtn: {
    width: 44, height: 44, borderRadius: 22, backgroundColor: Colors.blueprint,
    alignItems: 'center', justifyContent: 'center',
  },
  sendBtnDisabled: { opacity: 0.4 },
});
