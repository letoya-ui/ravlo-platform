import React, { useEffect, useState, useCallback } from 'react';
import { View, Text, StyleSheet, FlatList, TouchableOpacity, RefreshControl, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radii, Typography } from '../theme';
import { api } from '../services/api';

const ROLE_COLORS: Record<string, string> = { loan_officer: Colors.blueprint, processor: Colors.softGlow, underwriter: Colors.info, borrower: Colors.success, admin: Colors.warning };

export default function MessagesScreen({ navigation }: any) {
  const [convos, setConvos] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/mobile/lending/messages');
      setConvos(res.data.conversations || []);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, []);

  useEffect(() => { fetch(); }, [fetch]);
  const onRefresh = useCallback(async () => { setRefreshing(true); await fetch(); setRefreshing(false); }, [fetch]);

  const fmtDate = (raw: string) => {
    if (!raw || raw === 'None') return '';
    try {
      const d = new Date(raw), now = new Date();
      const diff = Math.round((now.getTime() - d.getTime()) / 86400000);
      if (diff === 0) return d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
      if (diff === 1) return 'Yesterday';
      if (diff < 7) return d.toLocaleDateString('en-US', { weekday: 'short' });
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    } catch { return ''; }
  };

  return (
    <SafeAreaView style={styles.container}>
      <Text style={styles.title}>Messages</Text>
      {loading && convos.length === 0 ? (
        <View style={styles.centered}><ActivityIndicator color={Colors.blueprint} size="large" /></View>
      ) : (
        <FlatList
          data={convos} keyExtractor={i => String(i.user_id)}
          contentContainerStyle={styles.list}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.blueprint} />}
          renderItem={({ item }) => {
            const color = ROLE_COLORS[item.role] || Colors.steel;
            const initials = (item.name || '?').split(' ').map((w: string) => w[0]).join('').toUpperCase().slice(0, 2);
            return (
              <TouchableOpacity style={styles.row}
                onPress={() => navigation.navigate('MessageThread', { userId: item.user_id, name: item.name })}
                activeOpacity={0.75}>
                <View style={[styles.avatar, { backgroundColor: color + '33' }]}>
                  <Text style={[styles.avatarText, { color }]}>{initials}</Text>
                </View>
                <View style={styles.rowContent}>
                  <View style={styles.rowTop}>
                    <Text style={[styles.name, item.unread > 0 && styles.nameBold]}>{item.name}</Text>
                    <Text style={styles.dateText}>{fmtDate(item.last_at)}</Text>
                  </View>
                  <Text style={[styles.preview, item.unread > 0 && styles.previewBold]} numberOfLines={1}>{item.last_message || '—'}</Text>
                </View>
                {item.unread > 0 && (
                  <View style={styles.unreadBadge}><Text style={styles.unreadText}>{item.unread}</Text></View>
                )}
              </TouchableOpacity>
            );
          }}
          ListEmptyComponent={
            <View style={styles.empty}>
              <Ionicons name="chatbubbles-outline" size={40} color={Colors.textMuted} />
              <Text style={styles.emptyText}>No messages yet</Text>
            </View>
          }
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  title: { ...Typography.h2, color: Colors.textPrimary, paddingHorizontal: Spacing.lg, paddingTop: Spacing.md, paddingBottom: Spacing.sm },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  list: { paddingBottom: 100 },
  row: { flexDirection: 'row', gap: Spacing.md, paddingHorizontal: Spacing.lg, paddingVertical: Spacing.md, borderBottomWidth: 1, borderBottomColor: Colors.border, alignItems: 'center' },
  avatar: { width: 48, height: 48, borderRadius: 24, alignItems: 'center', justifyContent: 'center' },
  avatarText: { fontWeight: '700', fontSize: 17 },
  rowContent: { flex: 1, gap: 3 },
  rowTop: { flexDirection: 'row', justifyContent: 'space-between' },
  name: { ...Typography.body, color: Colors.textPrimary },
  nameBold: { fontWeight: '700' },
  preview: { ...Typography.caption, color: Colors.textMuted },
  previewBold: { color: Colors.textSecondary, fontWeight: '600' },
  dateText: { ...Typography.caption, color: Colors.textMuted },
  unreadBadge: { backgroundColor: Colors.blueprint, borderRadius: 10, minWidth: 20, height: 20, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 5 },
  unreadText: { color: '#fff', fontSize: 11, fontWeight: '700' },
  empty: { alignItems: 'center', justifyContent: 'center', paddingVertical: 80, gap: Spacing.sm },
  emptyText: { ...Typography.body, color: Colors.textMuted },
});
