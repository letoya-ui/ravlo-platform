import React, { useEffect, useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, FlatList, TouchableOpacity,
  RefreshControl, ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radii, Typography } from '../theme';
import { useAuthStore } from '../store/authStore';
import { api } from '../services/api';

interface Conversation {
  partner_id: number;
  partner_name: string;
  partner_role: string;
  last_message: string;
  last_message_at: string;
  unread: number;
  is_mine: boolean;
}

function relativeDate(dateStr: string) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
  return d.toLocaleDateString();
}

export default function MessagesScreen({ navigation }: any) {
  const { token } = useAuthStore();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchConversations = useCallback(async () => {
    try {
      const res = await api.get('/mobile/lending/messages', {
        headers: { Authorization: `Bearer ${token}` },
      });
      setConversations(res.data.conversations || []);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { fetchConversations(); }, [fetchConversations]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchConversations();
    setRefreshing(false);
  }, [fetchConversations]);

  const initials = (name: string) =>
    (name || '?').split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <ActivityIndicator color={Colors.blueprint} style={{ flex: 1 }} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Messages</Text>
      </View>

      <FlatList
        data={conversations}
        keyExtractor={c => String(c.partner_id)}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.blueprint} />}
        contentContainerStyle={styles.listContent}
        ListEmptyComponent={
          <View style={styles.empty}>
            <Ionicons name="chatbubbles-outline" size={48} color={Colors.textMuted} />
            <Text style={styles.emptyText}>No messages yet</Text>
          </View>
        }
        renderItem={({ item }) => (
          <TouchableOpacity
            style={[styles.card, item.unread > 0 && styles.cardUnread]}
            onPress={() => navigation.navigate('MessageThread', { partnerId: item.partner_id, partnerName: item.partner_name })}
            activeOpacity={0.75}
          >
            <View style={[styles.avatar, { backgroundColor: Colors.blueprint + '33' }]}>
              <Text style={styles.avatarText}>{initials(item.partner_name)}</Text>
            </View>
            <View style={styles.cardBody}>
              <View style={styles.topRow}>
                <Text style={[styles.partnerName, item.unread > 0 && styles.partnerNameUnread]}>
                  {item.partner_name}
                </Text>
                <Text style={styles.time}>{relativeDate(item.last_message_at)}</Text>
              </View>
              {item.partner_role ? (
                <Text style={styles.role}>{item.partner_role.replace('_', ' ')}</Text>
              ) : null}
              <Text style={styles.lastMessage} numberOfLines={1}>
                {item.is_mine ? 'You: ' : ''}{item.last_message}
              </Text>
            </View>
            {item.unread > 0 && (
              <View style={styles.badge}>
                <Text style={styles.badgeText}>{item.unread > 9 ? '9+' : item.unread}</Text>
              </View>
            )}
          </TouchableOpacity>
        )}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  header: { paddingHorizontal: Spacing.lg, paddingTop: Spacing.md, paddingBottom: Spacing.sm },
  title: { ...Typography.h2, color: Colors.textPrimary },
  listContent: { paddingHorizontal: Spacing.lg, paddingBottom: Spacing.xl },
  card: { flexDirection: 'row', alignItems: 'center', backgroundColor: Colors.surface, borderRadius: Radii.md, padding: Spacing.md, marginBottom: Spacing.sm, borderWidth: 1, borderColor: Colors.border },
  cardUnread: { borderColor: Colors.blueprint + '66' },
  avatar: { width: 46, height: 46, borderRadius: 23, alignItems: 'center', justifyContent: 'center', marginRight: Spacing.sm },
  avatarText: { ...Typography.label, color: Colors.blueprint },
  cardBody: { flex: 1, minWidth: 0 },
  topRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  partnerName: { ...Typography.bodySmall, color: Colors.textSecondary, fontWeight: '600' },
  partnerNameUnread: { color: Colors.textPrimary },
  role: { ...Typography.caption, color: Colors.textMuted, textTransform: 'capitalize', marginTop: 1 },
  lastMessage: { ...Typography.caption, color: Colors.textMuted, marginTop: 3 },
  time: { ...Typography.caption, color: Colors.textMuted },
  badge: { width: 22, height: 22, borderRadius: 11, backgroundColor: Colors.blueprint, alignItems: 'center', justifyContent: 'center', marginLeft: Spacing.sm },
  badgeText: { fontSize: 10, fontWeight: '700', color: Colors.white },
  empty: { alignItems: 'center', paddingTop: 80, gap: Spacing.md },
  emptyText: { ...Typography.body, color: Colors.textMuted },
});
