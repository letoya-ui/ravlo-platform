import React, { useRef, useState } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  FlatList,
  Dimensions,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Colors, Spacing, Radii, Typography } from '../../theme';

const { width: SCREEN_WIDTH } = Dimensions.get('window');

interface SlideData {
  key: string;
  icon: keyof typeof Ionicons.glyphMap;
  title: string;
  subtitle: string;
  showButton?: boolean;
}

const SLIDES: SlideData[] = [
  {
    key: '1',
    icon: 'trending-up-outline',
    title: 'Welcome to Ravlo Investor',
    subtitle: 'Your real estate investment portfolio, at your fingertips.',
  },
  {
    key: '2',
    icon: 'cash-outline',
    title: 'Track Your Deals',
    subtitle: 'Monitor returns, deal status, and new opportunities in real time.',
  },
  {
    key: '3',
    icon: 'people-outline',
    title: 'Partner Network',
    subtitle: 'Connect with top-performing realtors and grow your referral pipeline.',
  },
  {
    key: '4',
    icon: 'rocket-outline',
    title: "Let's Get Started",
    subtitle: 'Sign in to access your portfolio.',
    showButton: true,
  },
];

interface Props {
  onDone: () => void;
}

export default function OnboardingScreen({ onDone }: Props) {
  const [activeIndex, setActiveIndex] = useState(0);
  const flatListRef = useRef<FlatList<SlideData>>(null);

  const handleSkip = async () => {
    try {
      await AsyncStorage.setItem('ravlo_onboarding_done', 'true');
    } catch {
      // ignore
    }
    onDone();
  };

  const handleGetStarted = async () => {
    try {
      await AsyncStorage.setItem('ravlo_onboarding_done', 'true');
    } catch {
      // ignore
    }
    onDone();
  };

  const onViewableItemsChanged = useRef(({ viewableItems }: any) => {
    if (viewableItems.length > 0) {
      setActiveIndex(viewableItems[0].index ?? 0);
    }
  }).current;

  const renderSlide = ({ item }: { item: SlideData }) => (
    <View style={styles.slide}>
      <View style={styles.iconCircle}>
        <Ionicons name={item.icon} size={40} color={Colors.blueprint} />
      </View>
      <Text style={styles.slideTitle}>{item.title}</Text>
      <Text style={styles.slideSubtitle}>{item.subtitle}</Text>
      {item.showButton && (
        <TouchableOpacity
          style={styles.getStartedBtn}
          onPress={handleGetStarted}
          activeOpacity={0.85}
        >
          <Text style={styles.getStartedText}>Get Started</Text>
        </TouchableOpacity>
      )}
    </View>
  );

  return (
    <SafeAreaView style={styles.container}>
      <TouchableOpacity style={styles.skipBtn} onPress={handleSkip}>
        <Text style={styles.skipText}>Skip</Text>
      </TouchableOpacity>

      <FlatList
        ref={flatListRef}
        data={SLIDES}
        renderItem={renderSlide}
        keyExtractor={(item) => item.key}
        horizontal
        pagingEnabled
        showsHorizontalScrollIndicator={false}
        onViewableItemsChanged={onViewableItemsChanged}
        viewabilityConfig={{ itemVisiblePercentThreshold: 50 }}
      />

      <View style={styles.dotsContainer}>
        {SLIDES.map((_, index) => (
          <View
            key={index}
            style={[
              styles.dot,
              index === activeIndex ? styles.dotActive : styles.dotInactive,
            ]}
          />
        ))}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  skipBtn: {
    position: 'absolute',
    top: Spacing.xl,
    right: Spacing.lg,
    zIndex: 10,
    paddingVertical: Spacing.xs,
    paddingHorizontal: Spacing.sm,
  },
  skipText: { ...Typography.body, color: Colors.textMuted },
  slide: {
    width: SCREEN_WIDTH,
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: Spacing.xl,
  },
  iconCircle: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: Colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  slideTitle: {
    ...Typography.h1,
    color: Colors.textPrimary,
    textAlign: 'center',
    marginTop: 32,
  },
  slideSubtitle: {
    ...Typography.body,
    color: Colors.textSecondary,
    textAlign: 'center',
    marginTop: 16,
    marginHorizontal: 32,
  },
  getStartedBtn: {
    backgroundColor: Colors.blueprint,
    width: '100%',
    height: 56,
    borderRadius: Radii.md,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: Spacing.xl,
  },
  getStartedText: { ...Typography.label, color: Colors.white, fontSize: 18 },
  dotsContainer: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    paddingBottom: Spacing.xl,
    gap: Spacing.sm,
  },
  dot: { borderRadius: Radii.full },
  dotActive: { width: 8, height: 8, backgroundColor: Colors.blueprint },
  dotInactive: { width: 6, height: 6, backgroundColor: Colors.border },
});
