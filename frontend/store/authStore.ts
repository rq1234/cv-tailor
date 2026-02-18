"use client";

import { create } from "zustand";
import type { Session, User } from "@supabase/supabase-js";
import { supabase } from "@/lib/supabase";

interface AuthState {
  user: User | null;
  session: Session | null;
  loading: boolean;
  error: string | null;
  signupEmail: string | null;
  initialize: () => Promise<void>;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  clearSignupEmail: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  session: null,
  loading: true,
  error: null,
  signupEmail: null,
  initialize: async () => {
    set({ loading: true, error: null });
    const { data, error } = await supabase.auth.getSession();
    if (error) {
      set({ loading: false, error: error.message, user: null, session: null });
      return;
    }
    set({
      loading: false,
      user: data.session?.user ?? null,
      session: data.session ?? null,
      error: null,
    });

    supabase.auth.onAuthStateChange((_event, session) => {
      set({ user: session?.user ?? null, session: session ?? null });
    });
  },
  signIn: async (email: string, password: string) => {
    set({ loading: true, error: null });
    const { data, error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) {
      set({ loading: false, error: error.message });
      return;
    }
    set({ loading: false, user: data.user, session: data.session });
  },
  signUp: async (email: string, password: string) => {
    set({ loading: true, error: null });
    const { data, error } = await supabase.auth.signUp({ email, password });
    if (error) {
      set({ loading: false, error: error.message });
      return;
    }
    set({ loading: false, user: data.user ?? null, session: data.session ?? null, signupEmail: email });
  },
  signOut: async () => {
    set({ loading: true, error: null });
    const { error } = await supabase.auth.signOut();
    if (error) {
      set({ loading: false, error: error.message });
      return;
    }
    set({ loading: false, user: null, session: null });
  },
  clearSignupEmail: () => set({ signupEmail: null }),
}));
