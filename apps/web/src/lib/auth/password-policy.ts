"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import type { PasswordPolicy } from "@/lib/api/loose-types";

const DEFAULT_POLICY: PasswordPolicy = {
  min_length: 8,
  require_upper: true,
  require_lower: true,
  require_number: true,
  require_symbol: true,
};

/** Port `loadPolicy()`/`_pwPolicy` lama -- `/api/auth/policy` publik (gak
 * butuh auth), dipakai buat live-validate password di client SEBELUM
 * submit (server tetap validasi ulang, ini cuma UX). Dipakai bareng di
 * Add User, Reset Password (admin), dan Change Password (diri sendiri). */
export function usePasswordPolicy() {
  const query = useQuery({
    queryKey: ["auth", "policy"],
    queryFn: async () => {
      const { data, response } = await api.GET("/api/auth/policy");
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return data as unknown as PasswordPolicy;
    },
    staleTime: 60_000,
  });
  return query.data ?? DEFAULT_POLICY;
}

export function policyHint(p: PasswordPolicy): string {
  if (p.hint) return p.hint;
  const parts = [`Min ${p.min_length || 8} chars`];
  if (p.require_upper) parts.push("uppercase");
  if (p.require_lower) parts.push("lowercase");
  if (p.require_number) parts.push("number");
  if (p.require_symbol) parts.push("symbol");
  return parts.join(" · ");
}

export function validatePasswordClient(pw: string, p: PasswordPolicy): string | null {
  if (pw.length < (p.min_length || 8)) return `Min ${p.min_length || 8} characters`;
  if (p.require_upper && !/[A-Z]/.test(pw)) return "Need uppercase letter";
  if (p.require_lower && !/[a-z]/.test(pw)) return "Need lowercase letter";
  if (p.require_number && !/[0-9]/.test(pw)) return "Need number";
  if (p.require_symbol && !/[^A-Za-z0-9]/.test(pw)) return "Need symbol (e.g. !@#$)";
  return null;
}
