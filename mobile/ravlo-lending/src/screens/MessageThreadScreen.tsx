import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
  View, Text, StyleSheet, FlatList, TextInput,
  TouchableOpacity, KeyboardAvoidingView, Platform,
  ActivityIndicator, RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radii, Typography } from '../theme';
import { useAuthStore } from '../store/authStore';
import { api } from '../services/api';

interface Message {
  id: number;
  sender_id: number;
  is_mine: boolean;
  content: string;
  created_at: string;
  is_read: boolean;
}

function formatTime(dateStr: string) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function formatDay(dateStr: string) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  if (d.toDateString() === today.toDateString()) return 'Today';
  if (d.toDateString() === yesterday.toDateString()) return 'Yesterday';
  return d.toLocaleDateString();
}

export default function MessageThreadScreen({ route, navigation }: any) {
  const { partnerId, partnerName } = route.params;
  const { token, user } = useAuthStore();
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const listRef = useRef<FlatList>(null);

  const fetchThread = useCallback(async () => {
    try {
      const res = await api.get(`/mobile/lending/messages/${partnerId}/thread`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setMessages(res.data.thread || []);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [partnerId, token]);

  useEffect(() => { fetchThread(); }, [fetchThread]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchThread();
    setRefreshing(false);
  }, [fetchThread]);

  const sendMessage = async () => {
    const content = input.trim();
    if (!content || sending) return;
    setSending(true);
    setInput('');
    try {
      const res = await api.post('/mobile/lending/messages/send', { receiver_id: partnerId, content }, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const newMsg: Message = {
        ...res.data.message,
        sender_id: user?.id,
        is_mine: true,
        is_read: false,
      };
      setMessages(prev => [...prev, newMsg]);
      setTimeout(() => listRef.current?.scrollToEnd({ animated: true }), 100);
    } catch {
      setInput(content);
    } finally {
      setSending(false);
    }
  };

  const grouped = messages.reduce<Array<{ day: string; msgs: Message[] }>>((acc, msg) => {
    const day = formatDay(msg.created_at);
    const last = acc[acc.length - 1];
    if (last && last.day === day) {
      last.msgs.push(msg);
    } else {
      acc.push({ day, msgs: [msg] });
    }
    return acc;
  }, []);

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.nav}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Ionicons name="chevron-back" size={24} color={Colors.textPrimary} />
        </TouchableOpacity>
        <View style={styles.navInfo}>
          <Text style={styles.navName}>{partnerName}</Text>
        </View>
        <View style={{ width: 40 }} />
      </View>

      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={0}
      >
        {loading ? (
          <ActivityIndicator color={Colors.blueprint} style={styles.flex} />
        ) : (
          <FlatList
            ref={listRef}
            data={grouped}
            keyExtractor={g => g.day}
            refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.blueprint} />}
            contentContainerStyle={styles.listContent}
            onContentSizeChange={() => listRef.current?.scrollToEnd({ animated: false })}
            ListEmptyComponent={
              <View style={styles.empty}>
                <Text style={styles.emptyText}>No messages yet. Say hi!</Text>
              </View>
            }
            renderItem={({ item: group }) => (
              <View>
                <View style={styles.dayDivider}>
                  <View style={styles.dayLine} />
                  <Text style={styles.dayLabel}>{group.day}</Text>
                  <View style={styles.dayLine} />
                </View>
                {group.msgs.map(msg => (
                  <View key={msg.id} style={[styles.bubbleRow, msg.is_mine && styles.bubbleRowMine]}>
                    <View style={[styles.bubble, msg.is_mine ? styles.bubbleMine : styles.bubbleTheirs]}>
                      <Text style={[styles.bubbleText, msg.is_mine && styles.bubbleTextMine]}>
                        {msg.content}
                      </Text>
                      <Text style={[styles.bubbleTime, msg.is_mine && styles.bubbleTimeMine]}>
                        {formatTime(msg.created_at)}
                        {msg.is_mine && (
                          <Text> {msg.is_read ? '✓✓' : '✓'}</Text>
                        )}
                      </Text>
                    </View>
                  </View>
                ))}
              </View>
            )}
          />
        )}

        <View style={styles.inputBar}>
          <TextInput
            style={styles.input}
            placeholder="Message…"
            placeholderTextColor={Colors.textMuted}
            value={input}
            onChangeText={setInput}
            multiline
            maxLength={2000}
            onSubmitEditing={sendMessage}
          />
          <TouchableOpacity
            style={[styles.sendBtn, (!input.trim() || sending) && styles.sendBtnDisabled]}
            onPress={sendMessage}
            disabled={!input.trim() || sending}
          >
            {sending
              ? <ActivityIndicator size="small" color={Colors.white} />
              : <Ionicons name="send" size={18} color={Colors.white} />}
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  flex: { flex: 1 },
  nav: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: Spacing.md, paddingVertical: Spacing.sm, borderBottomWidth: 1, borderBottomColor: Colors.border },
  backBtn: { padding: 8 },
  navInfo: { flex: 1, alignItems: 'center' },
  navName: { ...Typography.bodySmall, color: Colors.textPrimary, fontWeight: '700' },
  listContent: { paddingHorizontal: Spacing.md, paddingBottom: Spacing.md },
  dayDivider: { flexDirection: 'row', alignItems: 'center', marginVertical: Spacing.md, gap: Spacing.sm },
  dayLine: { flex: 1, height: 1, backgroundColor: Colors.border },
  dayLabel: { ...Typography.caption, color: Colors.textMuted },
  bubbleRow: { marginBottom: 4, alignItems: 'flex-start' },
  bubbleRowMine: { alignItems: 'flex-end' },
  bubble: { maxWidth: '78%', borderRadius: Radii.lg, paddingHorizontal: Spacing.md, paddingVertical: Spacing.sm, borderWidth: 1, borderColor: Colors.border, backgroundColor: Colors.surface },
  bubbleMine: { backgroundColor: Colors.blueprint, borderColor: Colors.blueprint },
  bubbleTheirs: {},
  bubbleText: { ...Typography.bodySmall, color: Colors.textPrimary },
  bubbleTextMine: { color: Colors.white },
  bubbleTime: { fontSize: 10, color: Colors.textMuted, marginTop: 4, textAlign: 'right' },
  bubbleTimeMine: { color: 'rgba(255,255,255,0.6)' },
  inputBar: { flexDirection: 'row', alignItems: 'flex-end', paddingHorizontal: Spacing.md, paddingVertical: Spacing.sm, borderTopWidth: 1, borderTopColor: Colors.border, gap: Spacing.sm, backgroundColor: Colors.surface },
  input: { flex: 1, backgroundColor: Colors.background, borderRadius: Radii.lg, borderWidth: 1, borderColor: Colors.border, color: Colors.textPrimary, paddingHorizontal: Spacing.md, paddingVertical: Spacing.sm, ...Typography.bodySmall, maxHeight: 100 },
  sendBtn: { width: 40, height: 40, borderRadius: 20, backgroundColor: Colors.blueprint, alignItems: 'center', justifyContent: 'center' },
  sendBtnDisabled: { opacity: 0.4 },
  empty: { flex: 1, alignItems: 'center', paddingTop: 60 },
  emptyText: { ...Typography.bodySmall, color: Colors.textMuted },
});
