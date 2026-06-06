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
  const chosenAvenue = user?.chosen_avenue || null;
  const unlockedAvenues = user?.unlocked_avenues || [];
  const legacyTier = user?.university_tier || null;

  useEffect(() => {
    if (!loaded) load();
  }, []);

  const accessibleModules = MODULES.filter(
    m => canAccessModule(chosenAvenue, unlockedAvenues, m.id, legacyTier)
  );
  const lockedModules = MODULES.filter(
    m => !canAccessModule(chosenAvenue, unlockedAvenues, m.id, legacyTier)
  );

  const totalLessons = accessibleModules.reduce((acc, m) => acc + m.lessons.length, 0);

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <View>
          <Text style={styles.title}>Academy</Text>
          <Text style={styles.subtitle}>{accessibleModules.length} avenues · {totalLessons} lessons</Text>
        </View>
        <TouchableOpacity
          style={styles.unlockBtn}
          onPress={() => navigation.navigate('AvenueUpgrade')}
          activeOpacity={0.8}
        >
          <Ionicons name="lock-open-outline" size={14} color={Colors.blueprint} />
          <Text style={styles.unlockBtnText}>Unlock More</Text>
        </TouchableOpacity>
      </View>

      <FlatList
        data={[...accessibleModules, ...lockedModules]}
        keyExtractor={m => m.id}
        contentContainerStyle={styles.list}
        showsVerticalScrollIndicator={false}
        ListHeaderComponent={
          accessibleModules.length === 0 ? (
            <View style={styles.chooseHint}>
              <Ionicons name="arrow-down-circle-outline" size={20} color={Colors.textMuted} />
              <Text style={styles.chooseHintText}>Choose a free avenue below to begin learning.</Text>
            </View>
          ) : null
        }
        renderItem={({ item }) => {
          const accessible = canAccessModule(chosenAvenue, unlockedAvenues, item.id, legacyTier);
          const progress = moduleProgress(item.id, item.lessons.length);
          const done = Math.round((progress / 100) * item.lessons.length);
          const isFreeAvenue = item.id === chosenAvenue;

          return (
            <TouchableOpacity
              style={[styles.card, !accessible && styles.cardLocked]}
              onPress={() => {
                if (accessible) {
                  navigation.navigate('ModuleDetail', { moduleId: item.id });
                } else {
                  navigation.navigate('AvenueUpgrade');
                }
              }}
              activeOpacity={accessible ? 0.75 : 0.9}
            >
              <View style={styles.cardTop}>
                <View style={[styles.iconBox, { backgroundColor: item.color + '22' }]}>
                  <Ionicons name={item.icon as any} size={22} color={accessible ? item.color : Colors.textMuted} />
                </View>
                <View style={styles.cardInfo}>
                  <View style={styles.titleRow}>
                    <Text style={[styles.cardTitle, !accessible && styles.lockedText]} numberOfLines={1}>
                      {item.title}
                    </Text>
                    {isFreeAvenue && (
                      <View style={styles.freeBadge}>
                        <Text style={styles.freeBadgeText}>INCLUDED</Text>
                      </View>
                    )}
                  </View>
                  <Text style={styles.cardDesc} numberOfLines={2}>{item.description}</Text>
                  <View style={styles.metaRow}>
                    <Ionicons name="book-outline" size={10} color={Colors.textMuted} />
                    <Text style={styles.lessonCount}>{item.lessons.length} lessons</Text>
                    <View style={styles.metaDot} />
                    <Ionicons name="ribbon-outline" size={10} color={Colors.textMuted} />
                    <Text style={styles.lessonCount}>{item.creditHours} credit hrs</Text>
                  </View>
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
                  <View style={styles.lockBadge}>
                    <Ionicons name="lock-closed-outline" size={14} color={Colors.textMuted} />
                  </View>
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
                <TouchableOpacity
                  style={styles.upgradeRow}
                  onPress={() => navigation.navigate('AvenueUpgrade')}
                  activeOpacity={0.7}
                >
                  <Ionicons name="flash-outline" size={12} color={Colors.blueprint} />
                  <Text style={styles.upgradeText}>Tap to unlock this avenue</Text>
                </TouchableOpacity>
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
  subtitle: { ...Typography.caption, color: Colors.textMuted, marginTop: 2 },
  unlockBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    backgroundColor: Colors.blueprint + '15', paddingHorizontal: 12, paddingVertical: 7,
    borderRadius: Radii.full, borderWidth: 1, borderColor: Colors.blueprint + '30',
  },
  unlockBtnText: { fontSize: 12, color: Colors.blueprint, fontWeight: '700' },
  list: { padding: Spacing.lg, paddingTop: Spacing.sm },
  chooseHint: {
    flexDirection: 'row', alignItems: 'center', gap: Spacing.sm,
    backgroundColor: Colors.surface, borderRadius: Radii.md, padding: Spacing.md,
    borderWidth: 1, borderColor: Colors.border, marginBottom: Spacing.md,
  },
  chooseHintText: { ...Typography.caption, color: Colors.textMuted, flex: 1 },
  card: {
    backgroundColor: Colors.surface, borderRadius: Radii.md, padding: Spacing.md,
    marginBottom: Spacing.sm, borderWidth: 1, borderColor: Colors.border,
  },
  cardLocked: { opacity: 0.7 },
  cardTop: { flexDirection: 'row', alignItems: 'flex-start', gap: Spacing.sm },
  iconBox: { width: 44, height: 44, borderRadius: Radii.sm, alignItems: 'center', justifyContent: 'center' },
  cardInfo: { flex: 1, minWidth: 0 },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 3 },
  cardTitle: { ...Typography.bodySmall, color: Colors.textPrimary, fontWeight: '700', flex: 1 },
  lockedText: { color: Colors.textMuted },
  freeBadge: {
    backgroundColor: Colors.success + '22', paddingHorizontal: 6, paddingVertical: 2,
    borderRadius: Radii.full, borderWidth: 1, borderColor: Colors.success + '44',
  },
  freeBadgeText: { fontSize: 9, color: Colors.success, fontWeight: '800', letterSpacing: 0.5 },
  cardDesc: { ...Typography.caption, color: Colors.textMuted, lineHeight: 17, marginBottom: 5 },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  lessonCount: { fontSize: 10, color: Colors.textMuted, fontWeight: '500' },
  metaDot: { width: 2.5, height: 2.5, borderRadius: 1.25, backgroundColor: Colors.textMuted },
  badge: { width: 32, height: 32, borderRadius: Radii.full, alignItems: 'center', justifyContent: 'center' },
  lockBadge: { width: 32, height: 32, alignItems: 'center', justifyContent: 'center' },
  progressSection: { marginTop: Spacing.sm, flexDirection: 'row', alignItems: 'center', gap: Spacing.sm },
  progressBar: { flex: 1, height: 4, backgroundColor: Colors.border, borderRadius: Radii.full, overflow: 'hidden' },
  progressFill: { height: '100%', borderRadius: Radii.full },
  progressText: { fontSize: 10, fontWeight: '700', minWidth: 80 },
  upgradeRow: { flexDirection: 'row', alignItems: 'center', gap: 5, marginTop: Spacing.sm },
  upgradeText: { fontSize: 11, color: Colors.blueprint, fontWeight: '600' },
});
