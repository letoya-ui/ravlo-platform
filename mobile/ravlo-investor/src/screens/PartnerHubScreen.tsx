import React, { useEffect, useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, FlatList, TouchableOpacity,
  RefreshControl, ActivityIndicator, Share, Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radii, Typography } from '../theme';
import { useAuthStore } from '../store/authStore';
import { api } from '../services/api';

interface Referral {
  id: number;
  name: string;
  email: string;
  status: string;
  created_at: string;
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

const PARTNER_BENEFITS = [
  { icon: 'cash-outline', title: 'Referral Commissions', desc: 'Earn when your referrals close deals or get funded', color: Colors.success },
  { icon: 'people-outline', title: 'Co-Investment Opportunities', desc: 'Access exclusive deals to invest alongside partners', color: Colors.blueprint },
  { icon: 'trending-up-outline', title: 'Deal Flow Sharing', desc: 'Share and receive off-market deal opportunities', color: Colors.warning },
  { icon: 'school-outline', title: 'Academy Access', desc: 'Priority access to Ravlo Academy training content', color: Colors.info },
];

export default function PartnerHubScreen() {
  const { user } = useAuthStore();
  const [data, setData] = useState<ReferralData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetch = useCallback(async () => {
    try {
      const res = await api.get('/mobile/partner/referrals');
      setData(res.data);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetch();
    setRefreshing(false);
  }, [fetch]);

  const referralLink = `https://ravlohq.com/join?ref=${user?.id || ''}`;

  const handleShare = async () => {
    try {
      await Share.share({
        message: `Join me on Ravlo — the all-in-one real estate investment platform. Sign up here: ${referralLink}`,
        url: referralLink,
        title: 'Join Ravlo',
      });
    } catch {
      // user dismissed
    }
  };

  const handleCopyLink = () => {
    Alert.alert('Link Copied', 'Your referral link has been copied to clipboard.');
  };

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
        <Text style={styles.title}>Partner Hub</Text>
      </View>

      <ScrollView
        contentContainerStyle={styles.scroll}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.blueprint} />}
        showsVerticalScrollIndicator={false}
      >
        {/* Referral link card */}
        <View style={styles.referralCard}>
          <View style={styles.referralTop}>
            <View style={styles.referralIcon}>
              <Ionicons name="share-social-outline" size={24} color={Colors.blueprint} />
            </View>
            <View style={styles.referralInfo}>
              <Text style={styles.referralTitle}>Your Referral Link</Text>
              <Text style={styles.referralLink} numberOfLines={1}>{referralLink}</Text>
            </View>
          </View>
          <View style={styles.referralActions}>
            <TouchableOpacity style={styles.copyBtn} onPress={handleCopyLink} activeOpacity={0.75}>
              <Ionicons name="copy-outline" size={16} color={Colors.blueprint} />
              <Text style={styles.copyBtnText}>Copy Link</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.shareBtn} onPress={handleShare} activeOpacity={0.85}>
              <Ionicons name="share-outline" size={16} color={Colors.white} />
              <Text style={styles.shareBtnText}>Share</Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Stats */}
        <View style={styles.statsRow}>
          <StatCard value={data?.total ?? 0} label="Total Referrals" color={Colors.blueprint} icon="people-outline" />
          <StatCard value={data?.pending ?? 0} label="Pending" color={Colors.warning} icon="time-outline" />
          <StatCard value={data?.converted ?? 0} label="Converted" color={Colors.success} icon="checkmark-circle-outline" />
        </View>

        {/* Conversion rate */}
        {(data?.total ?? 0) > 0 && (
          <View style={styles.conversionCard}>
            <Text style={styles.conversionLabel}>Conversion Rate</Text>
            <Text style={styles.conversionValue}>
              {data!.total > 0 ? Math.round((data!.converted / data!.total) * 100) : 0}%
            </Text>
            <View style={styles.conversionBar}>
              <View style={[
                styles.conversionFill,
                { width: `${data!.total > 0 ? Math.round((data!.converted / data!.total) * 100) : 0}%` }
              ]} />
            </View>
          </View>
        )}

        {/* Benefits */}
        <Text style={styles.sectionTitle}>Partner Benefits</Text>
        <View style={styles.benefitsGrid}>
          {PARTNER_BENEFITS.map((b, i) => (
            <View key={i} style={styles.benefitCard}>
              <View style={[styles.benefitIcon, { backgroundColor: b.color + '22' }]}>
                <Ionicons name={b.icon as any} size={20} color={b.color} />
              </View>
              <Text style={styles.benefitTitle}>{b.title}</Text>
              <Text style={styles.benefitDesc}>{b.desc}</Text>
            </View>
          ))}
        </View>

        {/* Referrals list */}
        {(data?.referrals?.length ?? 0) > 0 && (
          <>
            <Text style={styles.sectionTitle}>My Referrals</Text>
            {data!.referrals.map(r => {
              const statusColor = STATUS_COLORS[r.status] || Colors.steel;
              return (
                <View key={r.id} style={styles.refCard}>
                  <View style={styles.refAvatar}>
                    <Text style={styles.refInitials}>
                      {(r.name || 'U').charAt(0).toUpperCase()}
                    </Text>
                  </View>
                  <View style={styles.refInfo}>
                    <Text style={styles.refName}>{r.name || 'Unknown'}</Text>
                    {r.email ? <Text style={styles.refEmail}>{r.email}</Text> : null}
                    <Text style={styles.refDate}>
                      {r.created_at ? new Date(r.created_at).toLocaleDateString() : '—'}
                    </Text>
                  </View>
                  <View style={[styles.refBadge, { backgroundColor: statusColor + '22', borderColor: statusColor }]}>
                    <Text style={[styles.refBadgeText, { color: statusColor }]}>
                      {r.status.charAt(0).toUpperCase() + r.status.slice(1)}
                    </Text>
                  </View>
                </View>
              );
            })}
          </>
        )}

        {(data?.referrals?.length ?? 0) === 0 && (
          <View style={styles.emptyReferrals}>
            <Ionicons name="people-outline" size={40} color={Colors.textMuted} />
            <Text style={styles.emptyText}>No referrals yet</Text>
            <Text style={styles.emptySubText}>Share your link to start earning</Text>
            <TouchableOpacity style={styles.shareBtn2} onPress={handleShare} activeOpacity={0.85}>
              <Ionicons name="share-outline" size={16} color={Colors.white} />
              <Text style={styles.shareBtnText}>Share Your Link</Text>
            </TouchableOpacity>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

function StatCard({ value, label, color, icon }: { value: number; label: string; color: string; icon: any }) {
  return (
    <View style={[styles.statCard, { borderColor: color + '44' }]}>
      <View style={[styles.statIcon, { backgroundColor: color + '18' }]}>
        <Ionicons name={icon} size={16} color={color} />
      </View>
      <Text style={[styles.statValue, { color }]}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  header: { paddingHorizontal: Spacing.lg, paddingTop: Spacing.md, paddingBottom: Spacing.sm },
  title: { ...Typography.h2, color: Colors.textPrimary },
  scroll: { padding: Spacing.lg, paddingTop: Spacing.sm, paddingBottom: Spacing.xxl },
  referralCard: {
    backgroundColor: Colors.surface, borderRadius: Radii.lg, padding: Spacing.lg,
    borderWidth: 1, borderColor: Colors.border, marginBottom: Spacing.lg,
  },
  referralTop: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm, marginBottom: Spacing.md },
  referralIcon: { width: 48, height: 48, borderRadius: Radii.sm, backgroundColor: Colors.blueprint + '22', alignItems: 'center', justifyContent: 'center' },
  referralInfo: { flex: 1 },
  referralTitle: { ...Typography.body, color: Colors.textPrimary, fontWeight: '700' },
  referralLink: { ...Typography.caption, color: Colors.blueprint, marginTop: 3 },
  referralActions: { flexDirection: 'row', gap: Spacing.sm },
  copyBtn: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6,
    paddingVertical: 10, borderRadius: Radii.md, borderWidth: 1, borderColor: Colors.blueprint, backgroundColor: Colors.blueprint + '18',
  },
  copyBtnText: { ...Typography.bodySmall, color: Colors.blueprint, fontWeight: '600' },
  shareBtn: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6,
    paddingVertical: 10, borderRadius: Radii.md, backgroundColor: Colors.blueprint,
  },
  shareBtnText: { ...Typography.bodySmall, color: Colors.white, fontWeight: '700' },
  statsRow: { flexDirection: 'row', gap: Spacing.sm, marginBottom: Spacing.lg },
  statCard: { flex: 1, backgroundColor: Colors.surface, borderRadius: Radii.md, padding: Spacing.sm, alignItems: 'center', gap: 3, borderWidth: 1 },
  statIcon: { width: 28, height: 28, borderRadius: Radii.sm, alignItems: 'center', justifyContent: 'center' },
  statValue: { fontSize: 20, fontWeight: '800' },
  statLabel: { fontSize: 9, color: Colors.textMuted, fontWeight: '600', textAlign: 'center' },
  conversionCard: {
    backgroundColor: Colors.surface, borderRadius: Radii.md, padding: Spacing.md,
    borderWidth: 1, borderColor: Colors.border, marginBottom: Spacing.lg, flexDirection: 'row', alignItems: 'center', gap: Spacing.md,
  },
  conversionLabel: { ...Typography.bodySmall, color: Colors.textMuted },
  conversionValue: { fontSize: 22, fontWeight: '800', color: Colors.success, minWidth: 50 },
  conversionBar: { flex: 1, height: 6, backgroundColor: Colors.border, borderRadius: Radii.full, overflow: 'hidden' },
  conversionFill: { height: '100%', backgroundColor: Colors.success, borderRadius: Radii.full },
  sectionTitle: { ...Typography.label, color: Colors.textMuted, marginBottom: Spacing.md, marginTop: Spacing.xs },
  benefitsGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.sm, marginBottom: Spacing.lg },
  benefitCard: { flex: 1, minWidth: '45%', backgroundColor: Colors.surface, borderRadius: Radii.md, padding: Spacing.md, borderWidth: 1, borderColor: Colors.border },
  benefitIcon: { width: 36, height: 36, borderRadius: Radii.sm, alignItems: 'center', justifyContent: 'center', marginBottom: Spacing.sm },
  benefitTitle: { ...Typography.bodySmall, color: Colors.textPrimary, fontWeight: '700', marginBottom: 4 },
  benefitDesc: { ...Typography.caption, color: Colors.textMuted, lineHeight: 18 },
  refCard: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm, backgroundColor: Colors.surface, borderRadius: Radii.md, padding: Spacing.md, marginBottom: Spacing.sm, borderWidth: 1, borderColor: Colors.border },
  refAvatar: { width: 38, height: 38, borderRadius: 19, backgroundColor: Colors.blueprint + '22', alignItems: 'center', justifyContent: 'center' },
  refInitials: { fontSize: 16, fontWeight: '700', color: Colors.blueprint },
  refInfo: { flex: 1 },
  refName: { ...Typography.bodySmall, color: Colors.textPrimary, fontWeight: '600' },
  refEmail: { ...Typography.caption, color: Colors.textMuted, marginTop: 1 },
  refDate: { ...Typography.caption, color: Colors.textMuted, marginTop: 1 },
  refBadge: { borderWidth: 1, borderRadius: Radii.full, paddingHorizontal: 8, paddingVertical: 3 },
  refBadgeText: { fontSize: 9, fontWeight: '700', textTransform: 'uppercase' },
  emptyReferrals: { alignItems: 'center', paddingTop: Spacing.xl, gap: Spacing.sm },
  emptyText: { ...Typography.body, color: Colors.textMuted },
  emptySubText: { ...Typography.bodySmall, color: Colors.textMuted },
  shareBtn2: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: Spacing.md, paddingHorizontal: Spacing.xl, paddingVertical: 12, borderRadius: Radii.md, backgroundColor: Colors.blueprint },
});
