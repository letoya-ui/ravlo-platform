import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  FlatList,
  StyleSheet,
  RefreshControl,
  Alert,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radii, Typography } from '../theme';
import { api } from '../services/api';

interface Referral {
  id: number;
  name: string;
  email: string;
  status: string;
  created_at: string;
  converted_at: string;
}

interface ReferralData {
  referrals: Referral[];
  total: number;
  pending: number;
  converted: number;
}

const STATUS_COLORS: Record<string, string> = {
  pending: Colors.warning,
  submitted: Colors.info,
  new: Colors.info,
  converted: Colors.success,
  closed: Colors.success,
  funded: Colors.success,
};

export default function PartnerScreen() {
  const [data, setData] = useState<ReferralData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchReferrals = useCallback(async () => {
    try {
      const res = await api.get('/mobile/partner/referrals');
      setData(res.data);
    } catch (err: any) {
      Alert.alert('Error', err.response?.data?.error || 'Could not load referrals.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchReferrals(); }, [fetchReferrals]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchReferrals();
    setRefreshing(false);
  }, [fetchReferrals]);

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.centered}><ActivityIndicator size="large" color={Colors.blueprint} /></View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Partner Network</Text>
      </View>

      <View style={styles.statsRow}>
        <StatPill label="Total" value={data?.total ?? 0} color={Colors.blueprint} />
        <StatPill label="Pending" value={data?.pending ?? 0} color={Colors.warning} />
        <StatPill label="Converted" value={data?.converted ?? 0} color={Colors.success} />
      </View>

      <FlatList
        data={data?.referrals || []}
        keyExtractor={(item) => String(item.id)}
        contentContainerStyle={styles.list}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.blueprint} />}
        ListEmptyComponent={
          <View style={styles.empty}>
            <Ionicons name="people-outline" size={48} color={Colors.textMuted} />
            <Text style={styles.emptyText}>No referrals yet</Text>
          </View>
        }
        renderItem={({ item }) => {
          const statusColor = STATUS_COLORS[item.status] || Colors.steel;
          return (
            <View style={styles.card}>
              <View style={styles.cardHeader}>
                <Text style={styles.refName}>{item.name || 'Unknown'}</Text>
                <View style={[styles.badge, { backgroundColor: statusColor + '22' }]}>
                  <Text style={[styles.badgeText, { color: statusColor }]}>{item.status}</Text>
                </View>
              </View>
              {item.email ? <Text style={styles.email}>{item.email}</Text> : null}
              <Text style={styles.date}>
                Referred {item.created_at ? new Date(item.created_at).toLocaleDateString() : '—'}
              </Text>
            </View>
          );
        }}
      />
    </SafeAreaView>
  );
}

function StatPill({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <View style={[styles.statPill, { borderColor: color + '44', backgroundColor: color + '15' }]}>
      <Text style={[styles.statValue, { color }]}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  header: { paddingHorizontal: Spacing.lg, paddingTop: Spacing.md, paddingBottom: Spacing.sm },
  title: { ...Typography.h2, color: Colors.textPrimary },
  statsRow: { flexDirection: 'row', paddingHorizontal: Spacing.lg, gap: Spacing.sm, marginBottom: Spacing.md },
  statPill: {
    flex: 1,
    borderRadius: Radii.md,
    borderWidth: 1,
    padding: Spacing.sm,
    alignItems: 'center',
  },
  statValue: { fontSize: 22, fontWeight: '800' },
  statLabel: { ...Typography.caption, color: Colors.textMuted },
  list: { paddingHorizontal: Spacing.lg, paddingBottom: Spacing.xl },
  card: {
    backgroundColor: Colors.surface,
    borderRadius: Radii.md,
    padding: Spacing.md,
    marginBottom: Spacing.sm,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 },
  refName: { ...Typography.body, color: Colors.textPrimary, fontWeight: '600' },
  badge: { borderRadius: Radii.full, paddingHorizontal: Spacing.sm, paddingVertical: 2 },
  badgeText: { ...Typography.caption, fontWeight: '700', textTransform: 'uppercase' },
  email: { ...Typography.bodySmall, color: Colors.textMuted, marginBottom: 4 },
  date: { ...Typography.caption, color: Colors.textMuted },
  empty: { alignItems: 'center', paddingTop: Spacing.xxl, gap: Spacing.md },
  emptyText: { ...Typography.body, color: Colors.textMuted },
});
