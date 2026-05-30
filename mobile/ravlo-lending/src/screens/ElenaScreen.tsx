import React, { useState, useRef, useCallback } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  FlatList,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radii, Typography } from '../theme';
import { api } from '../services/api';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
}

export default function RavloAIScreen() {
  const [messages, setMessages] = useState<Message[]>([
    { id: '0', role: 'assistant', content: "Hi! I'm Ravlo AI, your intelligent lending assistant. Ask me anything about loans, underwriting, investment analysis, or mortgage products." },
  ]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const listRef = useRef<FlatList>(null);

  const sendMessage = useCallback(async () => {
    const text = input.trim();
    if (!text || sending) return;

    const userMsg: Message = { id: Date.now().toString(), role: 'user', content: text };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setSending(true);

    const history = messages.map((m) => ({ role: m.role, content: m.content }));

    try {
      const res = await api.post('/mobile/ai/chat', { message: text, history });
      const aiMsg: Message = { id: (Date.now() + 1).toString(), role: 'assistant', content: res.data.reply };
      setMessages((prev) => [...prev, aiMsg]);
    } catch (err: any) {
      Alert.alert('Ravlo AI', err.response?.data?.error || 'Could not reach Ravlo AI. Please try again.');
    } finally {
      setSending(false);
      setTimeout(() => listRef.current?.scrollToEnd({ animated: true }), 100);
    }
  }, [input, messages, sending]);

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <View style={styles.avatarContainer}>
          <View style={styles.avatar}>
            <Ionicons name="sparkles" size={20} color={Colors.white} />
          </View>
          <View>
            <Text style={styles.headerName}>Ravlo AI</Text>
            <Text style={styles.headerSub}>Intelligent Lending Assistant</Text>
          </View>
        </View>
      </View>

      <FlatList
        ref={listRef}
        data={messages}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.messageList}
        onContentSizeChange={() => listRef.current?.scrollToEnd({ animated: true })}
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Ionicons name="chatbubbles-outline" size={48} color={Colors.textMuted} />
            <Text style={styles.emptyText}>Start a conversation with Ravlo AI</Text>
          </View>
        }
        renderItem={({ item }) => (
          <View style={[styles.bubble, item.role === 'user' ? styles.userBubble : styles.aiBubble]}>
            {item.role === 'assistant' && (
              <View style={styles.aiBubbleAvatar}>
                <Ionicons name="sparkles" size={12} color={Colors.white} />
              </View>
            )}
            <View style={[styles.bubbleContent, item.role === 'user' ? styles.userBubbleContent : styles.aiBubbleContent]}>
              <Text style={[styles.bubbleText, item.role === 'user' ? styles.userBubbleText : styles.aiBubbleText]}>
                {item.content}
              </Text>
            </View>
          </View>
        )}
      />

      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
        <View style={styles.inputBar}>
          <TextInput
            style={styles.textInput}
            value={input}
            onChangeText={setInput}
            placeholder="Ask Ravlo anything…"
            placeholderTextColor={Colors.textMuted}
            multiline
            maxLength={2000}
          />
          <TouchableOpacity
            style={[styles.sendBtn, (!input.trim() || sending) && styles.sendBtnDisabled]}
            onPress={sendMessage}
            disabled={!input.trim() || sending}
            activeOpacity={0.8}
          >
            {sending ? (
              <ActivityIndicator size="small" color={Colors.white} />
            ) : (
              <Ionicons name="send" size={18} color={Colors.white} />
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
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: Colors.border,
    backgroundColor: Colors.surface,
  },
  avatarContainer: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm },
  avatar: {
    width: 40,
    height: 40,
    borderRadius: Radii.full,
    backgroundColor: Colors.blueprint,
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerName: { ...Typography.body, color: Colors.textPrimary, fontWeight: '700' },
  headerSub: { ...Typography.caption, color: Colors.textMuted },
  messageList: { padding: Spacing.md, paddingBottom: Spacing.lg },
  emptyContainer: { alignItems: 'center', paddingTop: Spacing.xxl, gap: Spacing.md },
  emptyText: { ...Typography.body, color: Colors.textMuted },
  bubble: { flexDirection: 'row', marginBottom: Spacing.sm, alignItems: 'flex-end' },
  userBubble: { justifyContent: 'flex-end' },
  aiBubble: { justifyContent: 'flex-start', gap: Spacing.xs },
  aiBubbleAvatar: {
    width: 24,
    height: 24,
    borderRadius: Radii.full,
    backgroundColor: Colors.blueprint,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 4,
  },
  bubbleContent: { maxWidth: '80%', borderRadius: Radii.lg, padding: Spacing.sm + 4 },
  userBubbleContent: { backgroundColor: Colors.blueprint },
  aiBubbleContent: { backgroundColor: Colors.surface, borderWidth: 1, borderColor: Colors.border },
  bubbleText: { fontSize: 15, lineHeight: 22 },
  userBubbleText: { color: Colors.white },
  aiBubbleText: { color: Colors.textPrimary },
  inputBar: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    padding: Spacing.md,
    gap: Spacing.sm,
    borderTopWidth: 1,
    borderTopColor: Colors.border,
    backgroundColor: Colors.surface,
  },
  textInput: {
    flex: 1,
    backgroundColor: Colors.background,
    borderRadius: Radii.md,
    borderWidth: 1,
    borderColor: Colors.border,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    color: Colors.textPrimary,
    fontSize: 15,
    maxHeight: 120,
  },
  sendBtn: {
    width: 40,
    height: 40,
    borderRadius: Radii.full,
    backgroundColor: Colors.blueprint,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sendBtnDisabled: { opacity: 0.4 },
});
