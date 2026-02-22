"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuthStore } from "@/store/authStore";
import ChangePasswordModal from "@/components/ChangePasswordModal";
import { api } from "@/lib/api";

interface TailoringRule {
  id: string;
  rule_text: string;
  is_active: boolean;
  created_at: string;
}

export default function SettingsPage() {
  const { user, signOut } = useAuthStore();
  const [rules, setRules] = useState<TailoringRule[]>([]);
  const [newRule, setNewRule] = useState("");
  const [loading, setLoading] = useState(true);
  const [rulesError, setRulesError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState("");
  const [showPasswordModal, setShowPasswordModal] = useState(false);

  const fetchRules = useCallback(async () => {
    try {
      const data = await api.get<TailoringRule[]>("/api/rules");
      setRules(data);
    } catch {
      setRulesError("Failed to load rules.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRules();
  }, [fetchRules]);

  const addRule = async () => {
    if (!newRule.trim()) return;
    setRulesError(null);
    try {
      await api.post("/api/rules", { rule_text: newRule.trim() });
      setNewRule("");
      fetchRules();
    } catch {
      setRulesError("Failed to add rule. Please try again.");
    }
  };

  const toggleRule = async (rule: TailoringRule) => {
    setRulesError(null);
    try {
      await api.put(`/api/rules/${rule.id}`, { is_active: !rule.is_active });
      fetchRules();
    } catch {
      setRulesError("Failed to update rule. Please try again.");
    }
  };

  const deleteRule = async (id: string) => {
    setRulesError(null);
    try {
      await api.delete(`/api/rules/${id}`);
      fetchRules();
    } catch {
      setRulesError("Failed to delete rule. Please try again.");
    }
  };

  const startEdit = (rule: TailoringRule) => {
    setEditingId(rule.id);
    setEditText(rule.rule_text);
  };

  const saveEdit = async () => {
    if (!editingId || !editText.trim()) return;
    setRulesError(null);
    try {
      await api.put(`/api/rules/${editingId}`, { rule_text: editText.trim() });
      setEditingId(null);
      setEditText("");
      fetchRules();
    } catch {
      setRulesError("Failed to save rule. Please try again.");
    }
  };

  return (
    <div className="max-w-3xl space-y-8">
      <h1 className="text-2xl font-bold">Settings</h1>

      {/* Tailoring Rules */}
      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Tailoring Rules</h2>
        <p className="text-sm text-muted-foreground">
          Custom rules that the AI will follow when rewriting your CV bullets.
          Active rules are applied to every tailoring run.
        </p>

        {rulesError && (
          <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
            {rulesError}
          </div>
        )}

        {/* Add new rule */}
        <div className="flex gap-2">
          <input
            type="text"
            value={newRule}
            onChange={(e) => setNewRule(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addRule()}
            placeholder='e.g. "Always quantify impact with numbers"'
            className="flex-1 rounded-md border px-3 py-2 text-sm"
          />
          <button
            onClick={addRule}
            disabled={!newRule.trim()}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            Add Rule
          </button>
        </div>

        {/* Rules list */}
        {loading ? (
          <div className="py-8 text-center text-sm text-muted-foreground">
            Loading rules...
          </div>
        ) : rules.length === 0 ? (
          <div className="rounded-lg border border-dashed p-8 text-center">
            <p className="text-sm text-muted-foreground">
              No tailoring rules yet. Add one above to customize how the AI
              rewrites your bullets.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {rules.map((rule) => (
              <div
                key={rule.id}
                className={`flex items-start gap-3 rounded-lg border p-3 ${
                  rule.is_active ? "bg-white" : "bg-muted/50 opacity-60"
                }`}
              >
                <button
                  onClick={() => toggleRule(rule)}
                  className={`mt-0.5 h-5 w-5 flex-shrink-0 rounded border ${
                    rule.is_active
                      ? "border-primary bg-primary"
                      : "border-muted-foreground"
                  } flex items-center justify-center`}
                >
                  {rule.is_active && (
                    <svg className="h-3 w-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                </button>

                <div className="flex-1 min-w-0">
                  {editingId === rule.id ? (
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={editText}
                        onChange={(e) => setEditText(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && saveEdit()}
                        className="flex-1 rounded-md border px-2 py-1 text-sm"
                        autoFocus
                      />
                      <button
                        onClick={saveEdit}
                        className="rounded px-2 py-1 text-xs bg-primary text-primary-foreground"
                      >
                        Save
                      </button>
                      <button
                        onClick={() => setEditingId(null)}
                        className="rounded px-2 py-1 text-xs bg-muted"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <p className="text-sm">{rule.rule_text}</p>
                  )}
                </div>

                {editingId !== rule.id && (
                  <div className="flex gap-1 flex-shrink-0">
                    <button
                      onClick={() => startEdit(rule)}
                      className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                    >
                      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                      </svg>
                    </button>
                    <button
                      onClick={() => deleteRule(rule.id)}
                      className="rounded p-1 text-muted-foreground hover:bg-red-50 hover:text-red-600"
                    >
                      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Account Section */}
      <section className="max-w-2xl space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold">Account</h3>
            <p className="text-sm text-muted-foreground">Manage your account settings</p>
          </div>
        </div>

        <div className="rounded-lg border p-4 space-y-4">
          {user && (
            <div>
              <label className="text-sm font-medium">Email</label>
              <p className="text-sm text-muted-foreground">{user.email}</p>
            </div>
          )}

          <button
            onClick={() => setShowPasswordModal(true)}
            className="w-full rounded-md bg-black px-3 py-2 text-sm font-medium text-white hover:bg-black/90"
          >
            Change Password
          </button>

          <button
            onClick={signOut}
            className="w-full rounded-md border px-3 py-2 text-sm font-medium hover:bg-gray-50"
          >
            Sign Out
          </button>
        </div>
      </section>

      <ChangePasswordModal isOpen={showPasswordModal} onClose={() => setShowPasswordModal(false)} />
    </div>
  );
}
