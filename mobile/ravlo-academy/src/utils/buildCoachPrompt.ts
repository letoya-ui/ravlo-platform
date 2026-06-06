export interface UserProgress {
  userId: string;
  currentCourse: {
    id: string;
    name: string;
    totalLessons: number;
    creditHours: number;
  };
  currentLesson?: {
    title: string;
    duration: string;
    completed: boolean;
  } | null;
  lastQuiz?: {
    lessonTitle: string;
    score: number;
    passed: boolean;
    missedConcepts?: string[];
  } | null;
  completedLessonCount: number;
  completedCourses: string[];
  subscription: string;
}

export type CoachTrigger =
  | 'post_lesson_pass'
  | 'post_lesson_fail'
  | 'quiz_miss_explainer'
  | 'progress_checkin'
  | 'general_chat'
  | 'business_plan';

export function getModelForTier(subscription: string): string {
  switch (subscription) {
    case 'all-access':
    case 'elite':
    case 'lending':
      return 'claude-opus-4-8';
    case 'pro':
      return 'claude-sonnet-4-6';
    case 'starter':
    default:
      return 'claude-haiku-4-5-20251001';
  }
}

export const COURSE_CONNECTIONS: Record<string, { courseId: string; reason: string }> = {
  residential: { courseId: 'realtor_growth', reason: 'Residential Mastery feeds directly into Realtor Business Growth' },
  commercial: { courseId: 'deal_structuring', reason: 'Commercial skills are essential for Advanced Deal Structuring' },
  mortgage: { courseId: 'underwriting', reason: 'Mortgage & Lending pairs with Underwriting & Processing' },
  realtor_growth: { courseId: 'residential', reason: 'Business Growth strategies amplify your Residential skills' },
  investing: { courseId: 'deal_structuring', reason: 'Investing strategies connect to Advanced Deal Structuring' },
  deal_structuring: { courseId: 'investing', reason: 'Deal Structuring unlocks more sophisticated Investing plays' },
  underwriting: { courseId: 'mortgage', reason: 'Underwriting expertise deepens your Mortgage & Lending knowledge' },
  construction: { courseId: 'investing', reason: 'Construction Management is essential for BRRRR and rehab investing' },
};

export function buildCoachSystemPrompt(
  user: UserProgress,
  triggerType: CoachTrigger,
): string {
  const base = `You are Ravlo AI Coach — an expert real estate coaching AI built into Ravlo Academy. You are encouraging, direct, and practical. You connect every concept to real-world application. You never give generic advice — everything is grounded in real estate.`;

  const studentContext = `
STUDENT CONTEXT:
- Current Course: ${user.currentCourse.name} (${user.completedLessonCount} lessons completed total)
- Current Lesson: ${user.currentLesson?.title || 'N/A'}
- Courses Completed: ${user.completedCourses.length > 0 ? user.completedCourses.join(', ') : 'None yet'}
- Subscription: ${user.subscription}`;

  const triggerContext = buildTriggerContext(user, triggerType);

  return `${base}\n${studentContext}\n${triggerContext}`;
}

function buildTriggerContext(user: UserProgress, trigger: CoachTrigger): string {
  const lessonTitle = user.lastQuiz?.lessonTitle || user.currentLesson?.title || 'the current lesson';
  const quizScore = user.lastQuiz?.score ?? 0;
  const missedConcepts = user.lastQuiz?.missedConcepts || [];

  switch (trigger) {
    case 'post_lesson_pass':
      return `
TRIGGER: Student just completed and passed "${lessonTitle}" with a score of ${quizScore}%.

Your job:
1. Briefly celebrate the win (1 sentence, genuine not cheesy)
2. Reinforce the 1-2 most important takeaways from this lesson
3. Preview what's coming next and why it matters
4. Ask one engaging question to deepen their thinking

Keep it under 150 words total.`;

    case 'post_lesson_fail':
      return `
TRIGGER: Student just failed the quiz for "${lessonTitle}" with a score of ${quizScore}%. They need to score 70% to pass.
${missedConcepts.length > 0 ? `Concepts they struggled with: ${missedConcepts.join(', ')}` : ''}

Your job:
1. Be encouraging — failing a quiz is normal, not a setback
2. Identify the core concept they likely misunderstood
3. Re-explain it in plain language with a real-world example
4. Tell them exactly what to focus on before retaking
5. Do NOT make them feel bad

Keep it supportive and under 200 words.`;

    case 'quiz_miss_explainer':
      return `
TRIGGER: Student asked for help understanding a specific question they missed on the "${lessonTitle}" quiz.

Your job:
1. Explain the correct concept clearly
2. Use a real-world example from real estate practice
3. Give them a memory anchor — a simple way to remember it
4. Confirm understanding with a follow-up question

Be a tutor, not a textbook.`;

    case 'progress_checkin':
      return `
TRIGGER: Student opened the AI Coach tab (not post-lesson).
They have completed ${user.completedLessonCount} lessons and are currently in ${user.currentCourse.name}.

Your job:
1. Acknowledge where they are in their journey
2. If they're mid-course, motivate them to finish
3. If they just started a course, tell them what to expect
4. Suggest the next best action (next lesson, revisit a concept, etc.)
5. Keep it brief — this is a check-in, not a lecture

Under 100 words. Conversational tone.`;

    case 'general_chat':
      return `
TRIGGER: Student initiated a general conversation with the AI Coach.

You have full context of their progress above. Use it naturally —
reference their current course when relevant, connect answers to
lessons they've completed, and flag lessons coming up that are
relevant to their questions.

Never answer in a vacuum. Always ground your response in their
specific stage of learning.`;

    case 'business_plan':
      return `
TRIGGER: Student is generating their 90-day business plan.

Use their completed courses and current focus to make the plan hyper-specific.
If they've completed Mortgage & Lending, their plan should reference MLO strategies.
If they're in Investing, their plan should include deal sourcing targets.

Generate a structured 90-day plan with:
- Week 1-2: Foundation actions
- Week 3-6: Build phase
- Week 7-10: Execute phase
- Week 11-13: Review and scale
Make every action specific to real estate, not generic business advice.`;

    default:
      return '';
  }
}
