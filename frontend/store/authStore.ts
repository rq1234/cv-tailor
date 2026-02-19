"use client";

import { create } from "zustand";
import type { Session, Subscription, User } from "@supabase/supabase-js";
import { supabase } from "@/lib/supabase";

// Module-level ref so initialize() can unsubscribe the previous listener
// before registering a new one (guards against StrictMode double-invoke).
let _authSubscription: Subscription | null = null;

interface AuthState {
  user: User | null;
  session: Session | null;
  /** True only while the initial auth check is running (first app load). */
  initializing: boolean;
  /** True during any in-flight auth operation (signIn, signOut, changePassword). */
  loading: boolean;
  error: string | null;
  signupEmail: string | null;
  initialize: () => Promise<void>;
  signIn: (email: string, password: string) => Promise<boolean>;
  signUp: (email: string, password: string) => Promise<boolean>;
  signOut: () => Promise<void>;
  changePassword: (currentPassword: string, newPassword: string) => Promise<boolean>;
  clearSignupEmail: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  session: null,
  initializing: true,
  loading: false,
  error: null,
  signupEmail: null,
  initialize: async () => {
    set({ initializing: true, error: null });
    const { data, error } = await supabase.auth.getSession();
    if (error) {
      set({ initializing: false, error: error.message, user: null, session: null });
      return;
    }
    set({
      initializing: false,
      user: data.session?.user ?? null,
      session: data.session ?? null,
      error: null,
    });

    _authSubscription?.unsubscribe();
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      set({ user: session?.user ?? null, session: session ?? null });
    });
    _authSubscription = subscription;
  },
  signIn: async (email: string, password: string) => {
    set({ loading: true, error: null });
    const { data, error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) {
      set({ loading: false, error: error.message });
      return false;
    }
    set({ loading: false, user: data.user, session: data.session });
    return true;
  },
  signUp: async (email: string, password: string) => {
    set({ loading: true, error: null });
    const { data, error } = await supabase.auth.signUp({ email, password });
    if (error) {
      // Check if it's a "user already exists" error
      const errorMsg = error.message.toLowerCase();
      if (errorMsg.includes('already registered') || errorMsg.includes('user already exists')) {
        set({ loading: false, error: "Email already registered. Please sign in instead." });
      } else {
        set({ loading: false, error: error.message });
      }
      return false;
    }
    set({ loading: false, user: data.user ?? null, session: data.session ?? null, signupEmail: email });
    return true;
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
  changePassword: async (currentPassword: string, newPassword: string) => {
    set({ loading: true, error: null });
    // Re-authenticate with current password first to verify identity
    const { data: sessionData } = await supabase.auth.getSession();
    const email = sessionData.session?.user?.email;
    if (!email) {
      set({ loading: false, error: "Session expired. Please sign in again." });
      return false;
    }
    const { error: signInError } = await supabase.auth.signInWithPassword({ email, password: currentPassword });
    if (signInError) {
      set({ loading: false, error: "Current password is incorrect." });
      return false;
    }
    const { error } = await supabase.auth.updateUser({ password: newPassword });
    if (error) {
      set({ loading: false, error: error.message });
      return false;
    }
    set({ loading: false, error: null });
    return true;
  },
  clearSignupEmail: () => set({ signupEmail: null }),
}));
