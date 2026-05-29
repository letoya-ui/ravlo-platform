import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radii, Typography } from '../../theme';
import { api } from '../../services/api';

interface ActivityData {
  recent_users: Array<{
    id: number; name: string; email: string; role: string; subscription: string; created_at: string;
  }>;
  recent_requests: Array<{
    id: number; name: string; email: string; company: string; status: string; created_at: string;
  }>;
  recent_leads: Array<{
    id: number; name: string; email: string; status: string; created_at: string;
  }>;
}

const STATUS_COLORS: Record<string, string> = {
  pending: Colors.warning,
  approved: Colors.success,
  denied: '#EF4444',
  converted: Colors.success,
  active: Colors.info,
};

export default function AdminActivityScreen() {
  const [data, setData] = useState<ActivityData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const res = await api.get('/mobile/admin/activity');
      setData(res.data);
    } catch (err) {
      console.error('admin activity error', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchData();
    setRefreshing(false);
  }, [fetchData]);

  const formatDate = (raw: string) => {
    if (!raw || raw === 'None') return '—';
    try {
      const d = new Date(raw);
      const now = new Date();
      const diffMs = now.getTime() - d.getTime();
      const diffH = diffMs / 3600000;
      if (diffH < 1) return `${Math.round(diffMs / 60000)}m ago`;
      if (diffH < 24) return `${Math.round(diffH)}h ago`;
      const diffD = Math.round(diffH / 24);
      if (diffD < 7) return `${diffD}d ago`;
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    } catch {
      return '—';
    }
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.centered}>
          <ActivityIndicator color={Colors.blueprint} size="large" />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView
        contentContainerStyle={styles.scroll}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.blueprint} />
        }
      >
        <Text style={styles.pageTitle}>Recent Activity</Text>

        {/* Recent Signups */}
        <SectionHeader icon="person-add-outline" title="New Signups" count={data?.recent_users.length} />
        {(data?.recent_users || []).map(u => (
          <ActivityRow
            key={`user-${u.id}`}
            icon="person-circle-outline"
            iconColor={Colors.success}
            title={u.name || u.email}
            subtitle={u.email}
            meta={u.role.replace(/_/g, ' ')}
            time={formatDate(u.created_at)}
            badge={u.subscription || 'free'}
            badgeColor={Colors.info}
          />
        ))}
        {(data?.recent_users || []).length === 0 && <EmptyRow text="No recent signups" />}

        {/* Access Requests */}
        <SectionHeader icon="key-outline" title="Access Requests" count={data?.recent_requests.length} />
        {(data?.recent_requests || []).map(r => (
          <ActivityRow
            key={`req-${r.id}`}
            icon="document-outline"
            iconColor={STATUS_COLORS[r.status] || Colors.steel}
            title={r.name || r.email}
            subtitle={r.company || r.email}
            meta={r.status}
            time={formatDate(r.created_at)}
            badge={r.status}
            badgeColor={STATUS_COLORS[r.status] || Colors.steel}
          />
        ))}
        {(data?.recent_requests || []).length === 0 && <EmptyRow text="No access requests" />}

        {/* Leads */}
        {(data?.recent_leads || []).length > 0 && (
          <>
            <SectionHeader icon="trending-up-outline" title="Recent Leads" count={data?.recent_leads.length} />
            {(data?.recent_leads || []).map(l => (
              <ActivityRow
                key={`lead-${l.id}`}
                icon="person-outline"
                iconColor={Colors.softGlow}
                title={l.name || l.email}
                subtitle={l.email}
                meta={l.status}
                time={formatDate(l.created_at)}
                badge={l.status}
                badgeColor={STATUS_COLORS[l.status] || Colors.steel}
              />
            ))}
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

function SectionHeader({ icon, title, count }: { icon: any; title: string; count?: number }) {
  return (
    <View style={styles.sectionHeader}>
      <Ionicons name={icon} size={16} color={Colors.textMuted} />
      <Text style={styles.sectionTitle}>{title}</Text>
      {count !== undefined && (
        <View style={styles.countPill}>
          <Text style={styles.countPillText}>{count}</Text>
        </View>
      )}
    </View>
  );
}

function ActivityRow({
  icon, iconColor, title, subtitle, meta, time, badge, badgeColor,
}: {
  icon: any; iconColor: string; title: string; subtitle: string;
  meta: string; time: string; badge: string; badgeColor: string;
}) {
  return (
    <View style={styles.actRow}>
      <View style={[styles.actIcon, { backgroundColor: iconColor + '22' }]}>
        <Ionicons name={icon} size={18} color={iconColor} />
      </View>
      <View style={styles.actContent}>
        <View style={styles.actTop}>
          <Text style={styles.actTitle} numberOfLines={1}>{title}</Text>
          <Text style={styles.actTime}>{time}</Text>
        </View>
        <Text style={styles.actSubtitle} numberOfLines={1}>{subtitle}</Text>
        <View style={styles.actBadgeRow}>
          <View style={[styles.actBadge, { backgroundColor: badgeColor + '22', borderColor: badgeColor }]}>
            <Text style={[styles.actBadgeText, { color: badgeColor }]}>{badge.replace(/_/g, ' ')}</Text>
          </View>
        </View>
      </View>
    </View>
  );
}

function EmptyRow({ text }: { text: string }) {
  return (
    <View style={styles.emptyRow}>
      <Text style={styles.emptyText}>{text}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  scroll: { padding: Spacing.lg, paddingBottom: Spacing.xl * 2 },
  pageTitle: { ...Typography.h2, color: Colors.textPrimary, marginBottom: Spacing.lg },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
    marginTop: Spacing.lg,
    marginBottom: Spacing.sm,
  },
  sectionTitle: { ...Typography.label, color: Colors.textMuted, flex: 1 },
  countPill: {
    backgroundColor: Colors.border,
    borderRadius: Radii.full,
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  countPillText: { ...Typography.caption, color: Colors.textMuted, fontWeight: '600' },
  actRow: {
    flexDirection: 'row',
    gap: Spacing.md,
    backgroundColor: Colors.surface,
    borderRadius: Radii.md,
    borderWidth: 1,
    borderColor: Colors.border,
    padding: Spacing.md,
    marginBottom: Spacing.sm,
    alignItems: 'flex-start',
  },
  actIcon: {
    width: 38,
    height: 38,
    borderRadius: Radii.sm,
    alignItems: 'center',
    justifyContent: 'center',
  },
  actContent: { flex: 1, gap: 3 },
  actTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  actTitle: { ...Typography.body, color: Colors.textPrimary, fontWeight: '600', flex: 1 },
  actTime: { ...Typography.caption, color: Colors.textMuted, marginLeft: Spacing.sm },
  actSubtitle: { ...Typography.caption, color: Colors.textMuted },
  actBadgeRow: { flexDirection: 'row', marginTop: 2 },
  actBadge: {
    borderRadius: Radii.full,
    borderWidth: 1,
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  actBadgeText: { fontSize: 10, fontWeight: '600', textTransform: 'capitalize' },
  emptyRow: {
    paddingVertical: Spacing.md,
    alignItems: 'center',
    backgroundColor: Colors.surface,
    borderRadius: Radii.md,
    borderWidth: 1,
    borderColor: Colors.border,
    marginBottom: Spacing.sm,
  },
  emptyText: { ...Typography.caption, color: Colors.textMuted },
});
