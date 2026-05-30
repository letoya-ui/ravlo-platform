import { create } from 'zustand';
import { api } from '../services/api';

interface CompletedLesson {
  module_id: string;
  lesson_index: number;
}

interface ProgressState {
  completed: CompletedLesson[];
  loaded: boolean;
  load: () => Promise<void>;
  markComplete: (moduleId: string, lessonIndex: number) => Promise<void>;
  markIncomplete: (moduleId: string, lessonIndex: number) => Promise<void>;
  isComplete: (moduleId: string, lessonIndex: number) => boolean;
  moduleProgress: (moduleId: string, totalLessons: number) => number;
}

export const useProgressStore = create<ProgressState>((set, get) => ({
  completed: [],
  loaded: false,

  load: async () => {
    try {
      const res = await api.get('/mobile/academy/lesson-progress');
      set({ completed: res.data.completed || [], loaded: true });
    } catch {
      set({ loaded: true });
    }
  },

  markComplete: async (moduleId: string, lessonIndex: number) => {
    set(state => ({
      completed: state.completed.some(c => c.module_id === moduleId && c.lesson_index === lessonIndex)
        ? state.completed
        : [...state.completed, { module_id: moduleId, lesson_index: lessonIndex }],
    }));
    try {
      await api.post('/mobile/academy/lesson/complete', { module_id: moduleId, lesson_index: lessonIndex });
    } catch {
      // revert on failure
      set(state => ({
        completed: state.completed.filter(c => !(c.module_id === moduleId && c.lesson_index === lessonIndex)),
      }));
    }
  },

  markIncomplete: async (moduleId: string, lessonIndex: number) => {
    const prev = get().completed;
    set(state => ({
      completed: state.completed.filter(c => !(c.module_id === moduleId && c.lesson_index === lessonIndex)),
    }));
    try {
      await api.post('/mobile/academy/lesson/complete', { module_id: moduleId, lesson_index: lessonIndex, undo: true });
    } catch {
      set({ completed: prev });
    }
  },

  isComplete: (moduleId: string, lessonIndex: number) =>
    get().completed.some(c => c.module_id === moduleId && c.lesson_index === lessonIndex),

  moduleProgress: (moduleId: string, totalLessons: number) => {
    if (totalLessons === 0) return 0;
    const done = get().completed.filter(c => c.module_id === moduleId).length;
    return Math.round((done / totalLessons) * 100);
  },
}));
