import React, { useEffect } from 'react';
import {
  View, Text, StyleSheet, FlatList, TouchableOpacity,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radii, Typography } from '../theme';
import { useAuthStore } from '../store/authStore';
import { useProgressStore } from '../store/progressStore';
import { MODULES, canAccessModule } from '../data/modules';

export default function LearnScreen({ navigation }: any) {
  const { user } = useAuthStore();
  const { load, loaded, moduleProgress } = useProgressStore();
  const tier = user?.university_tier || null;

  useEffect(() => {
    if (!loaded) load();
  }, []);

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Academy</Text>
        <Text style={styles.subtitle}>{MODULES.length} modules</Text>
      </View>

      <FlatList
        data={MODULES}
        keyExtractor={m => m.id}
        contentContainerStyle={styles.list}
        showsVerticalScrollIndicator={false}
        renderItem={({ item }) => {
          const accessible = canAccessModule(tier, item.id);
          const progress = moduleProgress(item.id, item.lessons.length);
          const done = Math.round((progress / 100) * item.lessons.length);

          return (
            <TouchableOpacity
              style={[styles.card, !accessible && styles.cardLocked]}
              onPress={() => {
                if (accessible) navigation.navigate('ModuleDetail', { moduleId: item.id });
              }}
              activeOpacity={accessible ? 0.75 : 1}
            >
              <View style={styles.cardTop}>
                <View style={[styles.iconBox, { backgroundColor: item.color + '22' }]}>
                  <Ionicons name={item.icon as any} size={22} color={accessible ? item.color : Colors.textMuted} />
                </View>
                <View style={styles.cardInfo}>
                  <Text style={[styles.cardTitle, !accessible && styles.lockedText]}>{item.title}</Text>
                  <Text style={styles.cardDesc} numberOfLines={2}>{item.description}</Text>
                  <Text style={styles.lessonCount}>{item.lessons.length} lessons</Text>
                </View>
                {accessible ? (
                  progress === 100 ? (
                    <View style={[styles.badge, { backgroundColor: Colors.success + '22' }]}>
                      <Ionicons name="checkmark-circle" size={18} color={Colors.success} />
                    </View>
                  ) : (
                    <Ionicons name="chevron-forward" size={18} color={Colors.textMuted} />
                  )
                ) : (
                  <Ionicons name="lock-closed-outline" size={18} color={Colors.textMuted} />
                )}
              </View>

              {accessible && (
                <View style={styles.progressSection}>
                  <View style={styles.progressBar}>
                    <View style={[styles.progressFill, { width: `${progress}%`, backgroundColor: item.color }]} />
                  </View>
                  <Text style={[styles.progressText, { color: item.color }]}>
                    {done}/{item.lessons.length} complete
                  </Text>
                </View>
              )}

              {!accessible && (
                <View style={styles.upgradeRow}>
                  <Ionicons name="star-outline" size={12} color={Colors.warning} />
                  <Text style={styles.upgradeText}>
                    {item.tiers.includes('pro') ? 'Pro' : 'Elite'} plan required
                  </Text>
                </View>
              )}
            </TouchableOpacity>
          );
        }}
      />
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
  subtitle: { ...Typography.bodySmall, color: Colors.textMuted },
  list: { padding: Spacing.lg, paddingTop: Spacing.sm },
  card: {
    backgroundColor: Colors.surface, borderRadius: Radii.md, padding: Spacing.md,
    marginBottom: Spacing.sm, borderWidth: 1, borderColor: Colors.border,
  },
  cardLocked: { opacity: 0.65 },
  cardTop: { flexDirection: 'row', alignItems: 'flex-start', gap: Spacing.sm },
  iconBox: { width: 44, height: 44, borderRadius: Radii.sm, alignItems: 'center', justifyContent: 'center' },
  cardInfo: { flex: 1, minWidth: 0 },
  cardTitle: { ...Typography.bodySmall, color: Colors.textPrimary, fontWeight: '700' },
  lockedText: { color: Colors.textMuted },
  cardDesc: { ...Typography.caption, color: Colors.textMuted, marginTop: 3, lineHeight: 18 },
  lessonCount: { ...Typography.caption, color: Colors.textMuted, marginTop: 4 },
  badge: { width: 32, height: 32, borderRadius: Radii.full, alignItems: 'center', justifyContent: 'center' },
  progressSection: { marginTop: Spacing.sm, flexDirection: 'row', alignItems: 'center', gap: Spacing.sm },
  progressBar: { flex: 1, height: 4, backgroundColor: Colors.border, borderRadius: Radii.full, overflow: 'hidden' },
  progressFill: { height: '100%', borderRadius: Radii.full },
  progressText: { fontSize: 10, fontWeight: '700', minWidth: 80 },
  upgradeRow: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: Spacing.sm },
  upgradeText: { fontSize: 10, color: Colors.warning, fontWeight: '600' },
});
