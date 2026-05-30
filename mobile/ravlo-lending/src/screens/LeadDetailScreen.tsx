import React, { useEffect, useState, useCallback } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput, Alert, Linking, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radii, Typography } from '../theme';
import { api } from '../services/api';

const LEAD_STATUSES = ['New', 'Contacted', 'Active', 'In Review', 'Pending', 'Closed', 'Lost', 'Converted'];

const STATUS_COLORS: Record<string, string> = {
  New: Colors.info, Active: Colors.success, Contacted: Colors.softGlow,
  Pending: Colors.warning, Closed: Colors.steel, Lost: '#EF4444', Converted: Colors.success,
};

export default function LeadDetailScreen({ route, navigation }: any) {
  const [lead, setLead] = useState<any>(route.params?.lead || null);
  const [detail, setDetail] = useState<any>(null);
  const [note, setNote] = useState('');
  const [saving, setSaving] = useState(false);
  const [showStatusPicker, setShowStatusPicker] = useState(false);

  const fetchDetail = useCallback(async () => {
    if (!lead?.id) return;
    try {
      const res = await api.get(`/mobile/lending/leads/${lead.id}`);
      setDetail(res.data.lead);
    } catch (e) { console.error(e); }
  }, [lead?.id]);

  useEffect(() => { fetchDetail(); }, [fetchDetail]);

  const updateStatus = async (newStatus: string) => {
    try {
      await api.post(`/mobile/lending/leads/${lead.id}/status`, { status: newStatus });
      setLead((prev: any) => ({ ...prev, status: newStatus }));
      setDetail((prev: any) => prev ? { ...prev, status: newStatus } : prev);
      setShowStatusPicker(false);
    } catch { Alert.alert('Error', 'Could not update status'); }
  };

  const addNote = async () => {
    if (!note.trim()) return;
    setSaving(true);
    try {
      const res = await api.post(`/mobile/lending/leads/${lead.id}/note`, { content: note.trim() });
      setDetail((prev: any) => prev ? { ...prev, notes: [...(prev.notes || []), res.data.note] } : prev);
      setNote('');
    } catch { Alert.alert('Error', 'Could not save note'); }
    setSaving(false);
  };

  const currentLead = detail || lead;
  const color = STATUS_COLORS[currentLead?.status] || Colors.steel;

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.nav}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Ionicons name="chevron-back" size={22} color={Colors.blueprint} />
          <Text style={styles.backText}>Leads</Text>
        </TouchableOpacity>
      </View>

      <ScrollView contentContainerStyle={styles.scroll}>
        {/* Header */}
        <View style={styles.profileCard}>
          <View style={[styles.avatar, { backgroundColor: color + '33' }]}>
            <Text style={[styles.avatarText, { color }]}>
              {(currentLead?.name || '?').split(' ').map((w: string) => w[0]).join('').toUpperCase().slice(0, 2)}
            </Text>
          </View>
          <Text style={styles.name}>{currentLead?.name || 'Unknown Lead'}</Text>
          <TouchableOpacity style={[styles.statusBadge, { backgroundColor: color + '22', borderColor: color }]} onPress={() => setShowStatusPicker(!showStatusPicker)}>
            <Text style={[styles.statusText, { color }]}>{currentLead?.status || 'New'}</Text>
            <Ionicons name="chevron-down" size={12} color={color} />
          </TouchableOpacity>
          {showStatusPicker && (
            <View style={styles.statusPicker}>
              {LEAD_STATUSES.map(s => (
                <TouchableOpacity key={s} style={styles.statusOption} onPress={() => updateStatus(s)}>
                  <View style={[styles.dot, { backgroundColor: STATUS_COLORS[s] || Colors.steel }]} />
                  <Text style={styles.statusOptionText}>{s}</Text>
                  {currentLead?.status === s && <Ionicons name="checkmark" size={14} color={Colors.blueprint} />}
                </TouchableOpacity>
              ))}
            </View>
          )}
        </View>

        {/* Contact actions */}
        <View style={styles.actionRow}>
          {currentLead?.phone && (
            <TouchableOpacity style={styles.actionBtn} onPress={() => Linking.openURL(`tel:${currentLead.phone}`)}>
              <Ionicons name="call-outline" size={20} color={Colors.blueprint} />
              <Text style={styles.actionText}>Call</Text>
            </TouchableOpacity>
          )}
          {currentLead?.email && (
            <TouchableOpacity style={styles.actionBtn} onPress={() => Linking.openURL(`mailto:${currentLead.email}`)}>
              <Ionicons name="mail-outline" size={20} color={Colors.blueprint} />
              <Text style={styles.actionText}>Email</Text>
            </TouchableOpacity>
          )}
          {currentLead?.phone && (
            <TouchableOpacity style={styles.actionBtn} onPress={() => Linking.openURL(`sms:${currentLead.phone}`)}>
              <Ionicons name="chatbubble-outline" size={20} color={Colors.blueprint} />
              <Text style={styles.actionText}>Text</Text>
            </TouchableOpacity>
          )}
        </View>

        {/* Info card */}
        <View style={styles.card}>
          {currentLead?.email && <InfoRow icon="mail-outline" label="Email" value={currentLead.email} />}
          {currentLead?.phone && <InfoRow icon="call-outline" label="Phone" value={currentLead.phone} />}
          {currentLead?.message && <InfoRow icon="chatbubble-ellipses-outline" label="Message" value={currentLead.message} />}
          <InfoRow icon="time-outline" label="Added" value={fmtDate(currentLead?.created_at)} />
        </View>

        {/* Notes */}
        <Text style={styles.sectionTitle}>Notes</Text>
        {(detail?.notes || []).map((n: any) => (
          <View key={n.id} style={styles.noteCard}>
            <Text style={styles.noteText}>{n.content}</Text>
            <Text style={styles.noteDate}>{fmtDate(n.created_at)}</Text>
          </View>
        ))}
        <View style={styles.noteInputRow}>
          <TextInput style={styles.noteInput} placeholder="Add a note…" placeholderTextColor={Colors.textMuted}
            value={note} onChangeText={setNote} multiline />
          <TouchableOpacity style={[styles.noteSubmit, !note.trim() && styles.noteSubmitDisabled]}
            onPress={addNote} disabled={!note.trim() || saving}>
            {saving ? <ActivityIndicator size="small" color="#fff" /> : <Ionicons name="send" size={16} color="#fff" />}
          </TouchableOpacity>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

function InfoRow({ icon, label, value }: { icon: any; label: string; value: string }) {
  return (
    <View style={styles.infoRow}>
      <Ionicons name={icon} size={16} color={Colors.textMuted} />
      <Text style={styles.infoLabel}>{label}</Text>
      <Text style={styles.infoValue} numberOfLines={2}>{value}</Text>
    </View>
  );
}

function fmtDate(raw: string) {
  if (!raw || raw === 'None') return '—';
  try {
    const d = new Date(raw), now = new Date();
    const diff = Math.round((now.getTime() - d.getTime()) / 86400000);
    if (diff === 0) return 'Today'; if (diff === 1) return 'Yesterday';
    if (diff < 7) return `${diff}d ago`;
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: '2-digit' });
  } catch { return '—'; }
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  nav: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: Spacing.md, paddingVertical: Spacing.sm },
  backBtn: { flexDirection: 'row', alignItems: 'center', gap: 2 },
  backText: { ...Typography.body, color: Colors.blueprint },
  scroll: { padding: Spacing.lg, paddingBottom: 80 },
  profileCard: { alignItems: 'center', marginBottom: Spacing.lg, gap: Spacing.sm },
  avatar: { width: 64, height: 64, borderRadius: 32, alignItems: 'center', justifyContent: 'center' },
  avatarText: { fontWeight: '800', fontSize: 24 },
  name: { ...Typography.h2, color: Colors.textPrimary },
  statusBadge: { flexDirection: 'row', alignItems: 'center', gap: 4, borderRadius: Radii.full, borderWidth: 1, paddingHorizontal: 10, paddingVertical: 4 },
  statusText: { fontSize: 12, fontWeight: '700' },
  statusPicker: { width: '100%', backgroundColor: Colors.surface, borderRadius: Radii.md, borderWidth: 1, borderColor: Colors.border, overflow: 'hidden' },
  statusOption: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm, padding: Spacing.md, borderBottomWidth: 1, borderBottomColor: Colors.border },
  dot: { width: 8, height: 8, borderRadius: 4 },
  statusOptionText: { ...Typography.body, color: Colors.textPrimary, flex: 1 },
  actionRow: { flexDirection: 'row', gap: Spacing.sm, marginBottom: Spacing.lg },
  actionBtn: { flex: 1, backgroundColor: Colors.surface, borderRadius: Radii.md, borderWidth: 1, borderColor: Colors.border, alignItems: 'center', padding: Spacing.md, gap: 4 },
  actionText: { ...Typography.caption, color: Colors.textSecondary },
  card: { backgroundColor: Colors.surface, borderRadius: Radii.md, borderWidth: 1, borderColor: Colors.border, padding: Spacing.md, marginBottom: Spacing.lg, gap: Spacing.sm },
  infoRow: { flexDirection: 'row', alignItems: 'flex-start', gap: Spacing.sm },
  infoLabel: { ...Typography.caption, color: Colors.textMuted, width: 56 },
  infoValue: { ...Typography.caption, color: Colors.textSecondary, flex: 1 },
  sectionTitle: { ...Typography.label, color: Colors.textMuted, marginBottom: Spacing.sm },
  noteCard: { backgroundColor: Colors.surface, borderRadius: Radii.sm, borderWidth: 1, borderColor: Colors.border, padding: Spacing.sm, marginBottom: Spacing.sm },
  noteText: { ...Typography.bodySmall, color: Colors.textSecondary },
  noteDate: { ...Typography.caption, color: Colors.textMuted, marginTop: 2, fontSize: 10 },
  noteInputRow: { flexDirection: 'row', gap: Spacing.sm, alignItems: 'flex-end', marginTop: Spacing.sm },
  noteInput: { flex: 1, backgroundColor: Colors.surface, borderRadius: Radii.md, borderWidth: 1, borderColor: Colors.border, padding: Spacing.md, ...Typography.body, color: Colors.textPrimary, maxHeight: 100 } as any,
  noteSubmit: { backgroundColor: Colors.blueprint, width: 40, height: 40, borderRadius: 20, alignItems: 'center', justifyContent: 'center' },
  noteSubmitDisabled: { opacity: 0.4 },
});
