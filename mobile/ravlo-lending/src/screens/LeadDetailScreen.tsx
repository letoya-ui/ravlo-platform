import React, { useEffect, useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  TextInput, ActivityIndicator, Alert, Linking, Modal,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radii, Typography } from '../theme';
import { useAuthStore } from '../store/authStore';
import { api } from '../services/api';

const LEAD_STATUSES = ['New', 'Contacted', 'Active', 'Pending', 'Qualified', 'Closed', 'Unqualified'];

const STATUS_COLORS: Record<string, string> = {
  New: Colors.info,
  Contacted: Colors.softGlow,
  Active: Colors.success,
  Pending: Colors.warning,
  Qualified: Colors.blueprint,
  Closed: Colors.steel,
  Unqualified: Colors.danger,
};

interface LeadDetail {
  id: number;
  name: string;
  email: string;
  phone: string;
  message: string;
  status: string;
  created_at: string;
  notes: Array<{ id: number; content: string; created_at: string }>;
  borrowers: Array<{ id: number; full_name: string; loan_type: string; loan_amount: number; status: string }>;
}

export default function LeadDetailScreen({ route, navigation }: any) {
  const { leadId, name } = route.params;
  const { token } = useAuthStore();
  const [lead, setLead] = useState<LeadDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [noteText, setNoteText] = useState('');
  const [submittingNote, setSubmittingNote] = useState(false);
  const [statusModal, setStatusModal] = useState(false);

  const fetchLead = useCallback(async () => {
    try {
      const res = await api.get(`/mobile/lending/leads/${leadId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setLead(res.data);
    } catch {
      Alert.alert('Error', 'Could not load lead details.');
    } finally {
      setLoading(false);
    }
  }, [leadId, token]);

  useEffect(() => { fetchLead(); }, [fetchLead]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchLead();
    setRefreshing(false);
  }, [fetchLead]);

  const updateStatus = async (newStatus: string) => {
    try {
      await api.post(`/mobile/lending/leads/${leadId}/status`, { status: newStatus }, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setLead(prev => prev ? { ...prev, status: newStatus } : prev);
    } catch {
      Alert.alert('Error', 'Could not update status.');
    }
    setStatusModal(false);
  };

  const addNote = async () => {
    if (!noteText.trim()) return;
    setSubmittingNote(true);
    try {
      const res = await api.post(`/mobile/lending/leads/${leadId}/note`, { content: noteText.trim() }, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const newNote = res.data.note;
      setLead(prev => prev ? { ...prev, notes: [newNote, ...prev.notes] } : prev);
      setNoteText('');
    } catch {
      Alert.alert('Error', 'Could not add note.');
    } finally {
      setSubmittingNote(false);
    }
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <ActivityIndicator color={Colors.blueprint} style={{ flex: 1 }} />
      </SafeAreaView>
    );
  }

  if (!lead) return null;

  const statusColor = STATUS_COLORS[lead.status] || Colors.steel;

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.nav}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Ionicons name="chevron-back" size={24} color={Colors.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.navTitle} numberOfLines={1}>{lead.name}</Text>
        <View style={{ width: 40 }} />
      </View>

      <ScrollView
        contentContainerStyle={styles.scroll}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.blueprint} />}
      >
        {/* Profile header */}
        <View style={styles.profileCard}>
          <View style={styles.avatarLarge}>
            <Text style={styles.avatarText}>
              {(lead.name || '?').split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2)}
            </Text>
          </View>
          <View style={styles.profileInfo}>
            <Text style={styles.profileName}>{lead.name}</Text>
            <TouchableOpacity
              style={[styles.statusPill, { backgroundColor: statusColor + '22', borderColor: statusColor }]}
              onPress={() => setStatusModal(true)}
            >
              <Text style={[styles.statusText, { color: statusColor }]}>{lead.status}</Text>
              <Ionicons name="chevron-down" size={12} color={statusColor} />
            </TouchableOpacity>
          </View>
        </View>

        {/* Actions */}
        <View style={styles.actionsRow}>
          <ActionBtn icon="call-outline" label="Call" color={Colors.success} onPress={() => lead.phone && Linking.openURL(`tel:${lead.phone}`)} />
          <ActionBtn icon="mail-outline" label="Email" color={Colors.info} onPress={() => lead.email && Linking.openURL(`mailto:${lead.email}`)} />
          <ActionBtn icon="chatbubble-outline" label="Text" color={Colors.warning} onPress={() => lead.phone && Linking.openURL(`sms:${lead.phone}`)} />
        </View>

        {/* Info card */}
        <View style={styles.infoCard}>
          <InfoRow icon="mail-outline" label="Email" value={lead.email} />
          <InfoRow icon="call-outline" label="Phone" value={lead.phone} />
          {lead.message ? <InfoRow icon="chatbox-outline" label="Message" value={lead.message} /> : null}
          <InfoRow icon="calendar-outline" label="Added" value={new Date(lead.created_at).toLocaleDateString()} />
        </View>

        {/* Borrowers */}
        {lead.borrowers.length > 0 && (
          <>
            <Text style={styles.sectionTitle}>Borrowers</Text>
            {lead.borrowers.map(b => (
              <View key={b.id} style={styles.borrowerCard}>
                <Text style={styles.borrowerName}>{b.full_name}</Text>
                <Text style={styles.borrowerSub}>{b.loan_type} · {b.status}</Text>
                {b.loan_amount > 0 && (
                  <Text style={styles.borrowerAmount}>
                    ${b.loan_amount.toLocaleString()}
                  </Text>
                )}
              </View>
            ))}
          </>
        )}

        {/* Notes */}
        <Text style={styles.sectionTitle}>Notes</Text>
        <View style={styles.noteInputRow}>
          <TextInput
            style={styles.noteInput}
            placeholder="Add a note…"
            placeholderTextColor={Colors.textMuted}
            value={noteText}
            onChangeText={setNoteText}
            multiline
          />
          <TouchableOpacity style={styles.noteSend} onPress={addNote} disabled={submittingNote || !noteText.trim()}>
            {submittingNote
              ? <ActivityIndicator size="small" color={Colors.white} />
              : <Ionicons name="send" size={18} color={Colors.white} />}
          </TouchableOpacity>
        </View>
        {lead.notes.map(n => (
          <View key={n.id} style={styles.noteCard}>
            <Text style={styles.noteContent}>{n.content}</Text>
            <Text style={styles.noteDate}>{new Date(n.created_at).toLocaleString()}</Text>
          </View>
        ))}
      </ScrollView>

      {/* Status picker modal */}
      <Modal visible={statusModal} transparent animationType="fade" onRequestClose={() => setStatusModal(false)}>
        <TouchableOpacity style={styles.modalOverlay} activeOpacity={1} onPress={() => setStatusModal(false)}>
          <View style={styles.modalBox}>
            <Text style={styles.modalTitle}>Update Status</Text>
            {LEAD_STATUSES.map(s => {
              const c = STATUS_COLORS[s] || Colors.steel;
              return (
                <TouchableOpacity key={s} style={[styles.modalOption, lead.status === s && styles.modalOptionActive]} onPress={() => updateStatus(s)}>
                  <View style={[styles.dot, { backgroundColor: c }]} />
                  <Text style={[styles.modalOptionText, { color: lead.status === s ? Colors.textPrimary : Colors.textSecondary }]}>{s}</Text>
                  {lead.status === s && <Ionicons name="checkmark" size={16} color={Colors.blueprint} />}
                </TouchableOpacity>
              );
            })}
          </View>
        </TouchableOpacity>
      </Modal>
    </SafeAreaView>
  );
}

function ActionBtn({ icon, label, color, onPress }: any) {
  return (
    <TouchableOpacity style={[styles.actionBtn, { borderColor: color }]} onPress={onPress} activeOpacity={0.75}>
      <Ionicons name={icon} size={20} color={color} />
      <Text style={[styles.actionLabel, { color }]}>{label}</Text>
    </TouchableOpacity>
  );
}

function InfoRow({ icon, label, value }: { icon: any; label: string; value: string }) {
  if (!value) return null;
  return (
    <View style={styles.infoRow}>
      <Ionicons name={icon} size={15} color={Colors.textMuted} style={styles.infoIcon} />
      <View style={styles.infoBody}>
        <Text style={styles.infoLabel}>{label}</Text>
        <Text style={styles.infoValue}>{value}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  nav: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: Spacing.md, paddingVertical: Spacing.sm },
  backBtn: { padding: 8 },
  navTitle: { ...Typography.h3, color: Colors.textPrimary, flex: 1, textAlign: 'center' },
  scroll: { padding: Spacing.lg, paddingBottom: Spacing.xxl },
  profileCard: { flexDirection: 'row', alignItems: 'center', marginBottom: Spacing.lg },
  avatarLarge: { width: 60, height: 60, borderRadius: 30, backgroundColor: Colors.blueprint + '33', alignItems: 'center', justifyContent: 'center', marginRight: Spacing.md },
  avatarText: { ...Typography.h3, color: Colors.blueprint },
  profileInfo: { flex: 1 },
  profileName: { ...Typography.h3, color: Colors.textPrimary, marginBottom: 6 },
  statusPill: { flexDirection: 'row', alignItems: 'center', gap: 4, alignSelf: 'flex-start', borderWidth: 1, borderRadius: Radii.full, paddingHorizontal: 10, paddingVertical: 4 },
  statusText: { fontSize: 12, fontWeight: '700' },
  actionsRow: { flexDirection: 'row', gap: Spacing.sm, marginBottom: Spacing.lg },
  actionBtn: { flex: 1, flexDirection: 'column', alignItems: 'center', gap: 6, borderWidth: 1.5, borderRadius: Radii.md, paddingVertical: Spacing.sm },
  actionLabel: { fontSize: 11, fontWeight: '600' },
  infoCard: { backgroundColor: Colors.surface, borderRadius: Radii.md, borderWidth: 1, borderColor: Colors.border, marginBottom: Spacing.lg, overflow: 'hidden' },
  infoRow: { flexDirection: 'row', alignItems: 'flex-start', padding: Spacing.md, borderBottomWidth: 1, borderBottomColor: Colors.border },
  infoIcon: { marginRight: Spacing.sm, marginTop: 2 },
  infoBody: { flex: 1 },
  infoLabel: { ...Typography.caption, color: Colors.textMuted },
  infoValue: { ...Typography.bodySmall, color: Colors.textPrimary, marginTop: 2 },
  sectionTitle: { ...Typography.label, color: Colors.textMuted, marginBottom: Spacing.sm, marginTop: Spacing.sm },
  borrowerCard: { backgroundColor: Colors.surface, borderRadius: Radii.md, padding: Spacing.md, borderWidth: 1, borderColor: Colors.border, marginBottom: Spacing.sm },
  borrowerName: { ...Typography.bodySmall, color: Colors.textPrimary, fontWeight: '600' },
  borrowerSub: { ...Typography.caption, color: Colors.textMuted, marginTop: 2 },
  borrowerAmount: { ...Typography.bodySmall, color: Colors.success, marginTop: 4, fontWeight: '600' },
  noteInputRow: { flexDirection: 'row', gap: Spacing.sm, marginBottom: Spacing.sm },
  noteInput: { flex: 1, backgroundColor: Colors.surface, borderRadius: Radii.md, borderWidth: 1, borderColor: Colors.border, color: Colors.textPrimary, padding: Spacing.sm, ...Typography.bodySmall, minHeight: 44 },
  noteSend: { width: 44, height: 44, borderRadius: Radii.md, backgroundColor: Colors.blueprint, alignItems: 'center', justifyContent: 'center' },
  noteCard: { backgroundColor: Colors.surface, borderRadius: Radii.md, padding: Spacing.md, borderWidth: 1, borderColor: Colors.border, marginBottom: Spacing.sm },
  noteContent: { ...Typography.bodySmall, color: Colors.textPrimary },
  noteDate: { ...Typography.caption, color: Colors.textMuted, marginTop: 4 },
  modalOverlay: { flex: 1, backgroundColor: '#00000088', justifyContent: 'center', alignItems: 'center' },
  modalBox: { backgroundColor: Colors.surface, borderRadius: Radii.lg, padding: Spacing.lg, width: '80%', borderWidth: 1, borderColor: Colors.border },
  modalTitle: { ...Typography.h3, color: Colors.textPrimary, marginBottom: Spacing.md },
  modalOption: { flexDirection: 'row', alignItems: 'center', paddingVertical: Spacing.sm, gap: Spacing.sm },
  modalOptionActive: { opacity: 1 },
  modalOptionText: { flex: 1, ...Typography.body },
  dot: { width: 10, height: 10, borderRadius: 5 },
});
