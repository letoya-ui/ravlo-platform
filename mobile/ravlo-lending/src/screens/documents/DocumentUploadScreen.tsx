import React, { useState } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  Alert,
  FlatList,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import * as DocumentPicker from 'expo-document-picker';
import { Colors, Spacing, Radii, Typography } from '../../theme';
import { api } from '../../services/api';

const DOC_TYPES = ['Income', 'Bank Statements', 'ID', 'Purchase Agreement', 'Other'] as const;
type DocType = typeof DOC_TYPES[number];

interface PickedFile {
  name: string;
  size: number;
  uri: string;
  mimeType: string;
}

type UploadState = 'idle' | 'uploading' | 'success';

export default function DocumentUploadScreen({ route, navigation }: any) {
  const { loanId, loanNumber } = route.params;
  const [selectedDocType, setSelectedDocType] = useState<DocType>('Income');
  const [pickedFile, setPickedFile] = useState<PickedFile | null>(null);
  const [uploadState, setUploadState] = useState<UploadState>('idle');

  const handleTakePhoto = async () => {
    try {
      const { status } = await ImagePicker.requestCameraPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('Permission Required', 'Camera access is needed to photograph documents.');
        return;
      }
      const result = await ImagePicker.launchCameraAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        quality: 0.85,
        allowsEditing: false,
      });
      if (!result.canceled && result.assets.length > 0) {
        const asset = result.assets[0];
        setPickedFile({
          name: asset.fileName || `photo_${Date.now()}.jpg`,
          size: asset.fileSize || 0,
          uri: asset.uri,
          mimeType: asset.mimeType || 'image/jpeg',
        });
        setUploadState('idle');
      }
    } catch (err: any) {
      Alert.alert('Error', 'Could not open camera.');
    }
  };

  const handleChooseFile = async () => {
    try {
      const result = await DocumentPicker.getDocumentAsync({
        type: '*/*',
        copyToCacheDirectory: true,
      });
      if (!result.canceled && result.assets.length > 0) {
        const asset = result.assets[0];
        setPickedFile({
          name: asset.name,
          size: asset.size || 0,
          uri: asset.uri,
          mimeType: asset.mimeType || 'application/octet-stream',
        });
        setUploadState('idle');
      }
    } catch (err: any) {
      Alert.alert('Error', 'Could not open document picker.');
    }
  };

  const handleUpload = async () => {
    if (!pickedFile) return;
    setUploadState('uploading');
    try {
      const formData = new FormData();
      formData.append('file', {
        uri: pickedFile.uri,
        name: pickedFile.name,
        type: pickedFile.mimeType,
      } as any);
      formData.append('loan_id', String(loanId));
      formData.append('doc_type', selectedDocType.toLowerCase().replace(' ', '_'));

      await api.post('/mobile/lending/documents/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setUploadState('success');
    } catch (err: any) {
      setUploadState('idle');
      Alert.alert('Upload Failed', err.response?.data?.error || 'Could not upload document.');
    }
  };

  const handleUploadAnother = () => {
    setPickedFile(null);
    setUploadState('idle');
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return 'Unknown size';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.navBar}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Ionicons name="chevron-back" size={24} color={Colors.textPrimary} />
          <Text style={styles.backText}>Loan {loanNumber || loanId}</Text>
        </TouchableOpacity>
      </View>

      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        <Text style={styles.title}>Upload Document</Text>

        <Text style={styles.sectionLabel}>Document Type</Text>
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.chipsRow}
        >
          {DOC_TYPES.map((type) => {
            const isSelected = selectedDocType === type;
            return (
              <TouchableOpacity
                key={type}
                onPress={() => setSelectedDocType(type)}
                style={[styles.chip, isSelected && styles.chipSelected]}
                activeOpacity={0.8}
              >
                <Text style={[styles.chipText, isSelected && styles.chipTextSelected]}>
                  {type}
                </Text>
              </TouchableOpacity>
            );
          })}
        </ScrollView>

        {uploadState !== 'success' && (
          <>
            <Text style={styles.sectionLabel}>Select File</Text>
            <View style={styles.uploadButtons}>
              <TouchableOpacity
                style={styles.uploadBtn}
                onPress={handleTakePhoto}
                activeOpacity={0.8}
              >
                <Ionicons name="camera-outline" size={32} color={Colors.blueprint} />
                <Text style={styles.uploadBtnText}>Take Photo</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.uploadBtn}
                onPress={handleChooseFile}
                activeOpacity={0.8}
              >
                <Ionicons name="document-outline" size={32} color={Colors.blueprint} />
                <Text style={styles.uploadBtnText}>Choose File</Text>
              </TouchableOpacity>
            </View>
          </>
        )}

        {pickedFile && uploadState !== 'success' && (
          <View style={styles.previewCard}>
            <View style={styles.previewIconRow}>
              <Ionicons name="document-attach-outline" size={28} color={Colors.blueprint} />
              <View style={styles.previewInfo}>
                <Text style={styles.previewName} numberOfLines={2}>
                  {pickedFile.name}
                </Text>
                <Text style={styles.previewSize}>{formatFileSize(pickedFile.size)}</Text>
              </View>
            </View>

            {uploadState === 'uploading' ? (
              <View style={styles.uploadingRow}>
                <ActivityIndicator color={Colors.blueprint} />
                <Text style={styles.uploadingText}>Uploading...</Text>
              </View>
            ) : (
              <TouchableOpacity
                style={styles.submitBtn}
                onPress={handleUpload}
                activeOpacity={0.8}
              >
                <Text style={styles.submitBtnText}>Upload</Text>
              </TouchableOpacity>
            )}
          </View>
        )}

        {uploadState === 'success' && (
          <View style={styles.successCard}>
            <Ionicons name="checkmark-circle" size={56} color={Colors.success} />
            <Text style={styles.successTitle}>Upload Successful</Text>
            <Text style={styles.successSubtitle}>
              Your document has been uploaded to loan {loanNumber || loanId}.
            </Text>
            <TouchableOpacity
              style={styles.anotherBtn}
              onPress={handleUploadAnother}
              activeOpacity={0.8}
            >
              <Text style={styles.anotherBtnText}>Upload Another</Text>
            </TouchableOpacity>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  navBar: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
  },
  backBtn: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  backText: { ...Typography.body, color: Colors.textPrimary },
  scroll: { padding: Spacing.lg, paddingBottom: Spacing.xxl },
  title: { ...Typography.h2, color: Colors.textPrimary, marginBottom: Spacing.lg },
  sectionLabel: {
    ...Typography.label,
    color: Colors.textSecondary,
    marginBottom: Spacing.sm,
    marginTop: Spacing.md,
  },
  chipsRow: { flexDirection: 'row', gap: Spacing.sm, paddingVertical: Spacing.xs },
  chip: {
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: Radii.full,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  chipSelected: {
    backgroundColor: Colors.blueprint,
    borderColor: Colors.blueprint,
  },
  chipText: { ...Typography.bodySmall, color: Colors.textSecondary, fontWeight: '600' },
  chipTextSelected: { color: Colors.white },
  uploadButtons: {
    flexDirection: 'row',
    gap: Spacing.md,
    marginTop: Spacing.xs,
  },
  uploadBtn: {
    flex: 1,
    aspectRatio: 1,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: Colors.blueprint,
    borderRadius: Radii.lg,
    borderStyle: 'dashed',
    backgroundColor: Colors.surface,
    gap: Spacing.sm,
    paddingVertical: Spacing.xl,
  },
  uploadBtnText: { ...Typography.label, color: Colors.blueprint },
  previewCard: {
    backgroundColor: Colors.surface,
    borderRadius: Radii.md,
    padding: Spacing.md,
    marginTop: Spacing.lg,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  previewIconRow: { flexDirection: 'row', alignItems: 'flex-start', gap: Spacing.sm, marginBottom: Spacing.md },
  previewInfo: { flex: 1 },
  previewName: { ...Typography.body, color: Colors.textPrimary, fontWeight: '600' },
  previewSize: { ...Typography.caption, color: Colors.textMuted, marginTop: 2 },
  uploadingRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: Spacing.sm, paddingVertical: Spacing.sm },
  uploadingText: { ...Typography.body, color: Colors.textSecondary },
  submitBtn: {
    backgroundColor: Colors.blueprint,
    borderRadius: Radii.md,
    paddingVertical: Spacing.md,
    alignItems: 'center',
  },
  submitBtnText: { ...Typography.label, color: Colors.white, fontSize: 16 },
  successCard: {
    alignItems: 'center',
    backgroundColor: Colors.surface,
    borderRadius: Radii.lg,
    padding: Spacing.xl,
    marginTop: Spacing.lg,
    borderWidth: 1,
    borderColor: Colors.border,
    gap: Spacing.md,
  },
  successTitle: { ...Typography.h2, color: Colors.success },
  successSubtitle: { ...Typography.body, color: Colors.textSecondary, textAlign: 'center' },
  anotherBtn: {
    borderWidth: 1,
    borderColor: Colors.blueprint,
    borderRadius: Radii.md,
    paddingVertical: Spacing.md,
    paddingHorizontal: Spacing.xl,
    alignItems: 'center',
    marginTop: Spacing.sm,
  },
  anotherBtnText: { ...Typography.label, color: Colors.blueprint, fontSize: 16 },
});
