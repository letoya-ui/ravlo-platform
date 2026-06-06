import React from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, Linking, Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radii, Typography } from '../theme';
import { COURSES, COURSE_PRICES, ALL_ACCESS_PRICE, canAccessCourse } from '../data/modules';
import { useAuthStore } from '../store/authStore';

export default function CourseUpgradeScreen({ navigation }: any) {
  const { user } = useAuthStore();
  const chosenCourse = user?.chosen_course || null;
  const unlockedCourses = user?.unlocked_courses || [];
  const legacyTier = user?.university_tier || null;

  const lockedCourses = COURSES.filter(
    m => !canAccessCourse(chosenCourse, unlockedCourses, m.id, legacyTier)
  );
  const unlockedCourseList = COURSES.filter(
    m => canAccessCourse(chosenCourse, unlockedCourses, m.id, legacyTier)
  );

  const handlePurchase = (courseId: string, courseTitle: string, price: number) => {
    Alert.alert(
      `Enroll in ${courseTitle}`,
      `Get full access to all lessons, quizzes, and your certificate for $${price}/month.\n\nYou'll be taken to our secure checkout.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: `Enroll for $${price}/mo`,
          onPress: () => {
            Alert.alert('Coming Soon', 'Stripe checkout integration is being set up. Contact support to enroll in this course.');
          },
        },
      ]
    );
  };

  const handleAllAccess = () => {
    Alert.alert(
      'All Access — All 8 Courses',
      `Get unlimited access to every course, lesson, and certificate for $${ALL_ACCESS_PRICE}/month. Save over 50% vs. enrolling individually.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: `Get All Access — $${ALL_ACCESS_PRICE}/mo`,
          onPress: () => {
            Alert.alert('Coming Soon', 'Stripe checkout integration is being set up. Contact support to unlock all courses.');
          },
        },
      ]
    );
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.nav}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Ionicons name="chevron-back" size={24} color={Colors.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.navTitle}>Enroll in More Courses</Text>
        <View style={{ width: 40 }} />
      </View>

      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        {/* All Access Banner */}
        <View style={styles.allAccessCard}>
          <View style={styles.allAccessLeft}>
            <View style={styles.starBadge}>
              <Ionicons name="star" size={14} color="#FFD700" />
              <Text style={styles.starText}>BEST VALUE</Text>
            </View>
            <Text style={styles.allAccessTitle}>All Access Pass</Text>
            <Text style={styles.allAccessDesc}>Every course, every lesson, every certificate. Accreditation-ready curriculum.</Text>
            <View style={styles.allAccessMeta}>
              <Ionicons name="book-outline" size={13} color={Colors.white} />
              <Text style={styles.allAccessMetaText}>8 avenues · 60+ lessons · 78 credit hours</Text>
            </View>
          </View>
          <TouchableOpacity style={styles.allAccessBtn} onPress={handleAllAccess} activeOpacity={0.85}>
            <Text style={styles.allAccessPrice}>${ALL_ACCESS_PRICE}</Text>
            <Text style={styles.allAccessPeriod}>/mo</Text>
          </TouchableOpacity>
        </View>

        {/* Current Access */}
        {unlockedCourseList.length > 0 && (
          <>
            <Text style={styles.sectionLabel}>YOUR ACCESS</Text>
            {unlockedCourseList.map(course => (
              <View key={course.id} style={styles.unlockedCard}>
                <View style={[styles.iconBox, { backgroundColor: course.color + '22' }]}>
                  <Ionicons name={course.icon as any} size={20} color={course.color} />
                </View>
                <View style={styles.cardInfo}>
                  <Text style={styles.cardTitle}>{course.title}</Text>
                  <Text style={styles.cardMeta}>{course.lessons.length} lessons · {course.creditHours} credit hrs</Text>
                </View>
                <View style={styles.accessBadge}>
                  <Ionicons name="checkmark-circle" size={16} color={Colors.success} />
                  <Text style={styles.accessBadgeText}>
                    {course.id === chosenCourse ? 'Included' : 'Enrolled'}
                  </Text>
                </View>
              </View>
            ))}
          </>
        )}

        {/* Locked Avenues */}
        {lockedCourses.length > 0 && (
          <>
            <Text style={styles.sectionLabel}>UNLOCK MORE</Text>
            {lockedCourses.map(course => (
              <View key={course.id} style={styles.lockedCard}>
                <View style={[styles.iconBox, { backgroundColor: course.color + '18' }]}>
                  <Ionicons name={course.icon as any} size={20} color={course.color} />
                </View>
                <View style={styles.cardInfo}>
                  <Text style={styles.cardTitle}>{course.title}</Text>
                  <Text style={styles.cardDesc} numberOfLines={2}>{course.description}</Text>
                  <Text style={styles.cardMeta}>{course.lessons.length} lessons · {course.creditHours} credit hrs</Text>
                </View>
                <TouchableOpacity
                  style={[styles.unlockBtn, { backgroundColor: course.color }]}
                  onPress={() => handlePurchase(course.id, course.title, COURSE_PRICES[course.id] || 49)}
                  activeOpacity={0.85}
                >
                  <Text style={styles.unlockBtnText}>${COURSE_PRICES[course.id] || 49}/mo</Text>
                </TouchableOpacity>
              </View>
            ))}
          </>
        )}

        {lockedCourses.length === 0 && (
          <View style={styles.allUnlocked}>
            <Ionicons name="trophy-outline" size={40} color={Colors.success} />
            <Text style={styles.allUnlockedTitle}>You have All Access!</Text>
            <Text style={styles.allUnlockedText}>Every course and lesson in Ravlo Academy is open to you.</Text>
          </View>
        )}

        <View style={styles.accreditationNote}>
          <Ionicons name="ribbon-outline" size={18} color={Colors.blueprint} />
          <View style={{ flex: 1 }}>
            <Text style={styles.accreditationTitle}>Accreditation Ready</Text>
            <Text style={styles.accreditationText}>
              Ravlo Academy is building toward becoming an accredited institution. All curriculum, credit hours, and certificates are structured to meet accreditation standards.
            </Text>
          </View>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  nav: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: Spacing.md, paddingVertical: Spacing.sm,
  },
  backBtn: { padding: 8, width: 40 },
  navTitle: { ...Typography.bodySmall, color: Colors.textPrimary, fontWeight: '700' },
  scroll: { padding: Spacing.lg, paddingBottom: Spacing.xxl },
  allAccessCard: {
    backgroundColor: Colors.blueprint, borderRadius: Radii.lg, padding: Spacing.lg,
    flexDirection: 'row', alignItems: 'center', marginBottom: Spacing.xl,
  },
  allAccessLeft: { flex: 1, marginRight: Spacing.md },
  starBadge: {
    flexDirection: 'row', alignItems: 'center', gap: 4, marginBottom: 8,
    backgroundColor: 'rgba(255,255,255,0.18)', alignSelf: 'flex-start',
    paddingHorizontal: 8, paddingVertical: 3, borderRadius: Radii.full,
  },
  starText: { fontSize: 10, color: '#FFD700', fontWeight: '800', letterSpacing: 0.5 },
  allAccessTitle: { ...Typography.h3, color: Colors.white, marginBottom: 4 },
  allAccessDesc: { ...Typography.caption, color: 'rgba(255,255,255,0.8)', lineHeight: 18, marginBottom: 8 },
  allAccessMeta: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  allAccessMetaText: { fontSize: 11, color: 'rgba(255,255,255,0.75)' },
  allAccessBtn: {
    backgroundColor: Colors.white, borderRadius: Radii.md, paddingHorizontal: 14, paddingVertical: 10,
    alignItems: 'center', flexShrink: 0,
  },
  allAccessPrice: { ...Typography.h3, color: Colors.blueprint },
  allAccessPeriod: { fontSize: 11, color: Colors.blueprint, fontWeight: '600', marginTop: -2 },
  sectionLabel: {
    ...Typography.caption, color: Colors.textMuted, fontWeight: '800', letterSpacing: 0.8,
    marginBottom: Spacing.sm, marginTop: 4,
  },
  unlockedCard: {
    backgroundColor: Colors.surface, borderRadius: Radii.md, padding: Spacing.md,
    flexDirection: 'row', alignItems: 'center', gap: Spacing.sm,
    marginBottom: Spacing.sm, borderWidth: 1, borderColor: Colors.border,
  },
  lockedCard: {
    backgroundColor: Colors.surface, borderRadius: Radii.md, padding: Spacing.md,
    flexDirection: 'row', alignItems: 'center', gap: Spacing.sm,
    marginBottom: Spacing.sm, borderWidth: 1, borderColor: Colors.border,
  },
  iconBox: { width: 44, height: 44, borderRadius: Radii.sm, alignItems: 'center', justifyContent: 'center', flexShrink: 0 },
  cardInfo: { flex: 1, minWidth: 0 },
  cardTitle: { ...Typography.bodySmall, color: Colors.textPrimary, fontWeight: '700' },
  cardDesc: { ...Typography.caption, color: Colors.textMuted, lineHeight: 17, marginTop: 2, marginBottom: 3 },
  cardMeta: { fontSize: 10, color: Colors.textMuted, marginTop: 2 },
  accessBadge: { flexDirection: 'row', alignItems: 'center', gap: 4, flexShrink: 0 },
  accessBadgeText: { fontSize: 11, color: Colors.success, fontWeight: '700' },
  unlockBtn: { borderRadius: Radii.sm, paddingHorizontal: 12, paddingVertical: 8, flexShrink: 0 },
  unlockBtnText: { fontSize: 12, color: Colors.white, fontWeight: '800' },
  allUnlocked: { alignItems: 'center', paddingVertical: Spacing.xl, gap: Spacing.md },
  allUnlockedTitle: { ...Typography.h3, color: Colors.success },
  allUnlockedText: { ...Typography.body, color: Colors.textMuted, textAlign: 'center' },
  accreditationNote: {
    flexDirection: 'row', alignItems: 'flex-start', gap: Spacing.md,
    backgroundColor: Colors.blueprint + '11', borderRadius: Radii.md, padding: Spacing.md,
    borderWidth: 1, borderColor: Colors.blueprint + '33', marginTop: Spacing.lg,
  },
  accreditationTitle: { ...Typography.bodySmall, color: Colors.blueprint, fontWeight: '700', marginBottom: 4 },
  accreditationText: { ...Typography.caption, color: Colors.textSecondary, lineHeight: 18 },
});
