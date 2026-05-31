import React, { useEffect, useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, FlatList, TouchableOpacity,
  RefreshControl, ActivityIndicator, Modal, TextInput,
  KeyboardAvoidingView, Platform, Alert, ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radii, Typography } from '../theme';
import { api } from '../services/api';

interface FundingRequest {
  id: number;
  deal_id: number;
  deal_title: string;
  requested_amount: number;
  status: string;
  notes: string;
  created_at: string;
  updated_at: string;
}

interface Deal {
  id: number;
  title: string;
  address: string;
  purchase_price: number;
  arv: number;
}

const STATUS_COLORS: Record<string, string> = {
  submitted: Colors.info,
  reviewing: Colors.warning,
  approved: Colors.success,
  declined: Colors.danger,
};

const STATUS_ICONS: Record<string, any> = {
  submitted: 'paper-plane-outline',
  reviewing: 'eye-outline',
  approved: 'checkmark-circle-outline',
  declined: 'close-circle-outline',
};

export default function FundingScreen() {
  const [requests, setRequests] = useState<FundingRequest[]>([]);
  const [deals, setDeals] = useState<Deal[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [selectedDeal, setSelectedDeal] = useState<Deal | null>(null);
  const [requestedAmount, setRequestedAmount] = useState('');
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [reqRes, dealRes] = await Promise.all([
        api.get('/mobile/investor/funding-requests'),
        api.get('/mobile/investor/deals', { params: { status: 'active', page: 1 } }),
      ]);
      setRequests(reqRes.data.requests || []);
      setDeals(dealRes.data.deals || []);
    } catch {
      // silent
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

  const handleSubmit = async () => {
    if (!selectedDeal) return;
    const amount = parseFloat(requestedAmount.replace(/,/g, ''));
    if (!amount || amount <= 0) {
      Alert.alert('Invalid Amount', 'Please enter a valid requested amount.');
      return;
    }
    setSubmitting(true);
    try {
      await api.post('/mobile/investor/funding-requests', {
        deal_id: selectedDeal.id,
        requested_amount: amount,
        notes,
      });
      setModalVisible(false);
      setSelectedDeal(null);
      setRequestedAmount('');
      setNotes('');
      await fetchData();
      Alert.alert('Submitted!', 'Your funding request has been submitted for review.');
    } catch (e: any) {
      Alert.alert('Error', e.response?.data?.error || 'Could not submit request.');
    } finally {
      setSubmitting(false);
    }
  };

  const fmt = (v: number) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', notation: 'compact', maximumFractionDigits: 1 }).format(v);

  const fmtFull = (v: number) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(v);

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
        <Text style={styles.title}>Capital Requests</Text>
        {deals.length > 0 && (
          <TouchableOpacity style={styles.newBtn} onPress={() => setModalVisible(true)} activeOpacity={0.8}>
            <Ionicons name="add" size={18} color={Colors.white} />
            <Text style={styles.newBtnText}>New Request</Text>
          </TouchableOpacity>
        )}
      </View>

      <FlatList
        data={requests}
        keyExtractor={r => String(r.id)}
        contentContainerStyle={styles.list}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.blueprint} />}
        ListEmptyComponent={
          <View style={styles.empty}>
            <Ionicons name="cash-outline" size={48} color={Colors.textMuted} />
            <Text style={styles.emptyText}>No funding requests yet</Text>
            <Text style={styles.emptySubText}>Submit a deal for funding review to get started</Text>
            {deals.length > 0 && (
              <TouchableOpacity style={styles.emptyBtn} onPress={() => setModalVisible(true)} activeOpacity={0.8}>
                <Text style={styles.emptyBtnText}>Submit a Deal</Text>
              </TouchableOpacity>
            )}
          </View>
        }
        renderItem={({ item }) => {
          const statusColor = STATUS_COLORS[item.status] || Colors.steel;
          const statusIcon = STATUS_ICONS[item.status] || 'ellipsis-horizontal-circle-outline';
          return (
            <View style={styles.card}>
              <View style={styles.cardTop}>
                <View style={[styles.statusIcon, { backgroundColor: statusColor + '22' }]}>
                  <Ionicons name={statusIcon} size={20} color={statusColor} />
                </View>
                <View style={styles.cardInfo}>
                  <Text style={styles.cardTitle} numberOfLines={1}>{item.deal_title}</Text>
                  <Text style={styles.cardDate}>
                    Submitted {item.created_at ? new Date(item.created_at).toLocaleDateString() : '—'}
                  </Text>
                </View>
                <View style={[styles.statusBadge, { backgroundColor: statusColor + '22', borderColor: statusColor }]}>
                  <Text style={[styles.statusText, { color: statusColor }]}>
                    {item.status.charAt(0).toUpperCase() + item.status.slice(1)}
                  </Text>
                </View>
              </View>

              <View style={styles.amountRow}>
                <View style={styles.amountBox}>
                  <Text style={styles.amountLabel}>Requested</Text>
                  <Text style={styles.amountValue}>{fmtFull(item.requested_amount)}</Text>
                </View>
              </View>

              {item.notes ? (
                <View style={styles.notesSection}>
                  <Text style={styles.notesText} numberOfLines={2}>{item.notes}</Text>
                </View>
              ) : null}

              {item.status === 'reviewing' && (
                <View style={styles.reviewingBanner}>
                  <Ionicons name="eye-outline" size={14} color={Colors.warning} />
                  <Text style={styles.reviewingText}>Under review by our lending team</Text>
                </View>
              )}
              {item.status === 'approved' && (
                <View style={styles.approvedBanner}>
                  <Ionicons name="checkmark-circle" size={14} color={Colors.success} />
                  <Text style={styles.approvedText}>Approved — contact your loan officer to proceed</Text>
                </View>
              )}
            </View>
          );
        }}
      />

      {/* Submit Modal */}
      <Modal visible={modalVisible} animationType="slide" transparent onRequestClose={() => setModalVisible(false)}>
        <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={styles.modalOverlay}>
          <View style={styles.modalSheet}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Request Funding</Text>
              <TouchableOpacity onPress={() => setModalVisible(false)}>
                <Ionicons name="close" size={22} color={Colors.textMuted} />
              </TouchableOpacity>
            </View>

            <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={styles.modalScroll}>
              <Text style={styles.modalLabel}>Select Deal</Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.dealPickerScroll} contentContainerStyle={styles.dealPickerRow}>
                {deals.map(d => (
                  <TouchableOpacity
                    key={d.id}
                    style={[styles.dealChip, selectedDeal?.id === d.id && styles.dealChipSelected]}
                    onPress={() => setSelectedDeal(d)}
                    activeOpacity={0.75}
                  >
                    <Text style={[styles.dealChipText, selectedDeal?.id === d.id && styles.dealChipTextSelected]} numberOfLines={2}>
                      {d.title || d.address || `Deal #${d.id}`}
                    </Text>
                    {d.purchase_price > 0 && (
                      <Text style={[styles.dealChipSub, selectedDeal?.id === d.id && { color: Colors.white + 'aa' }]}>
                        {fmt(d.purchase_price)}
                      </Text>
                    )}
                  </TouchableOpacity>
                ))}
              </ScrollView>

              <Text style={styles.modalLabel}>Requested Amount ($)</Text>
              <TextInput
                style={styles.modalInput}
                value={requestedAmount}
                onChangeText={setRequestedAmount}
                keyboardType="decimal-pad"
                placeholder="e.g. 250000"
                placeholderTextColor={Colors.textMuted}
              />

              <Text style={styles.modalLabel}>Notes (optional)</Text>
              <TextInput
                style={[styles.modalInput, styles.modalTextarea]}
                value={notes}
                onChangeText={setNotes}
                placeholder="Describe your funding need, timeline, or deal details..."
                placeholderTextColor={Colors.textMuted}
                multiline
                numberOfLines={4}
                textAlignVertical="top"
              />
            </ScrollView>

            <View style={styles.modalFooter}>
              <TouchableOpacity style={styles.cancelBtn} onPress={() => setModalVisible(false)}>
                <Text style={styles.cancelBtnText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.submitBtn, (!selectedDeal || !requestedAmount || submitting) && styles.submitBtnDisabled]}
                onPress={handleSubmit}
                disabled={!selectedDeal || !requestedAmount || submitting}
                activeOpacity={0.85}
              >
                {submitting ? (
                  <ActivityIndicator size="small" color={Colors.white} />
                ) : (
                  <>
                    <Ionicons name="paper-plane-outline" size={16} color={Colors.white} />
                    <Text style={styles.submitBtnText}>Submit Request</Text>
                  </>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  header: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingHorizontal: Spacing.lg, paddingTop: Spacing.md, paddingBottom: Spacing.sm,
  },
  title: { ...Typography.h2, color: Colors.textPrimary },
  newBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    backgroundColor: Colors.blueprint, borderRadius: Radii.md, paddingHorizontal: Spacing.md, paddingVertical: 8,
  },
  newBtnText: { ...Typography.caption, color: Colors.white, fontWeight: '700' },
  list: { padding: Spacing.lg, paddingBottom: Spacing.xxl },
  empty: { alignItems: 'center', paddingTop: 64, gap: Spacing.md },
  emptyText: { ...Typography.body, color: Colors.textMuted },
  emptySubText: { ...Typography.bodySmall, color: Colors.textMuted, textAlign: 'center' },
  emptyBtn: { backgroundColor: Colors.blueprint, borderRadius: Radii.md, paddingHorizontal: Spacing.lg, paddingVertical: 12, marginTop: Spacing.sm },
  emptyBtnText: { ...Typography.body, color: Colors.white, fontWeight: '700' },
  card: { backgroundColor: Colors.surface, borderRadius: Radii.md, padding: Spacing.md, marginBottom: Spacing.sm, borderWidth: 1, borderColor: Colors.border },
  cardTop: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm, marginBottom: Spacing.sm },
  statusIcon: { width: 40, height: 40, borderRadius: Radii.sm, alignItems: 'center', justifyContent: 'center' },
  cardInfo: { flex: 1, minWidth: 0 },
  cardTitle: { ...Typography.bodySmall, color: Colors.textPrimary, fontWeight: '600' },
  cardDate: { ...Typography.caption, color: Colors.textMuted, marginTop: 2 },
  statusBadge: { borderWidth: 1, borderRadius: Radii.full, paddingHorizontal: 8, paddingVertical: 3 },
  statusText: { fontSize: 10, fontWeight: '700' },
  amountRow: { flexDirection: 'row', paddingTop: Spacing.sm, borderTopWidth: 1, borderTopColor: Colors.border },
  amountBox: {},
  amountLabel: { ...Typography.caption, color: Colors.textMuted },
  amountValue: { ...Typography.h3, color: Colors.textPrimary, marginTop: 2 },
  notesSection: { marginTop: Spacing.sm, paddingTop: Spacing.sm, borderTopWidth: 1, borderTopColor: Colors.border },
  notesText: { ...Typography.bodySmall, color: Colors.textMuted },
  reviewingBanner: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: Spacing.sm, paddingTop: Spacing.sm, borderTopWidth: 1, borderTopColor: Colors.border },
  reviewingText: { ...Typography.caption, color: Colors.warning },
  approvedBanner: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: Spacing.sm, paddingTop: Spacing.sm, borderTopWidth: 1, borderTopColor: Colors.border },
  approvedText: { ...Typography.caption, color: Colors.success },
  modalOverlay: { flex: 1, justifyContent: 'flex-end', backgroundColor: 'rgba(0,0,0,0.6)' },
  modalSheet: { backgroundColor: Colors.surface, borderTopLeftRadius: Radii.xl, borderTopRightRadius: Radii.xl, maxHeight: '85%' },
  modalHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', padding: Spacing.lg, borderBottomWidth: 1, borderBottomColor: Colors.border },
  modalTitle: { ...Typography.h3, color: Colors.textPrimary },
  modalScroll: { padding: Spacing.lg },
  modalLabel: { ...Typography.label, color: Colors.textMuted, marginBottom: Spacing.sm, marginTop: Spacing.md },
  dealPickerScroll: { flexGrow: 0 },
  dealPickerRow: { gap: Spacing.sm, paddingBottom: 4 },
  dealChip: { width: 140, backgroundColor: Colors.background, borderRadius: Radii.md, padding: Spacing.sm, borderWidth: 1.5, borderColor: Colors.border },
  dealChipSelected: { backgroundColor: Colors.blueprint, borderColor: Colors.blueprint },
  dealChipText: { ...Typography.caption, color: Colors.textPrimary, fontWeight: '600' },
  dealChipTextSelected: { color: Colors.white },
  dealChipSub: { fontSize: 10, color: Colors.textMuted, marginTop: 4 },
  modalInput: {
    ...Typography.bodySmall, color: Colors.textPrimary,
    backgroundColor: Colors.background, borderRadius: Radii.md,
    borderWidth: 1, borderColor: Colors.border, padding: Spacing.md,
  },
  modalTextarea: { minHeight: 100, textAlignVertical: 'top' },
  modalFooter: { flexDirection: 'row', gap: Spacing.sm, padding: Spacing.lg, paddingTop: Spacing.sm, borderTopWidth: 1, borderTopColor: Colors.border },
  cancelBtn: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingVertical: 14, borderRadius: Radii.md, backgroundColor: Colors.background, borderWidth: 1, borderColor: Colors.border },
  cancelBtnText: { ...Typography.body, color: Colors.textPrimary, fontWeight: '600' },
  submitBtn: { flex: 2, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: Spacing.sm, paddingVertical: 14, borderRadius: Radii.md, backgroundColor: Colors.blueprint },
  submitBtnDisabled: { opacity: 0.4 },
  submitBtnText: { ...Typography.body, color: Colors.white, fontWeight: '700' },
});
