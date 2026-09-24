"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import type { AdminUser, AuditLogEntry, Client, Permission, Role } from "@/lib/api/loose-types";

/**
 * Endpoint `/api/auth/users`, `/api/roles`, `/api/roles/permissions`,
 * `/api/clients` semua balikin `list[dict[str,object]]` polos di backend
 * (gak ada `response_model`) -- `data as unknown as X[]` di sini nge-cast
 * ke shape yang dicek langsung dari `_serialize()` masing-masing router
 * (`auth.py::get_users`, `roles.py`, `clients.py`), bukan tebakan.
 */

export function useAdminUsers() {
  return useQuery({
    queryKey: ["admin", "users"],
    queryFn: async () => {
      const { data, response } = await api.GET("/api/auth/users");
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return data as unknown as AdminUser[];
    },
  });
}

export function useRoles() {
  return useQuery({
    queryKey: ["admin", "roles"],
    queryFn: async () => {
      const { data, response } = await api.GET("/api/roles");
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return data as unknown as Role[];
    },
  });
}

export function usePermissions() {
  return useQuery({
    queryKey: ["admin", "permissions"],
    queryFn: async () => {
      const { data, response } = await api.GET("/api/roles/permissions");
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return data as unknown as Permission[];
    },
  });
}

export function useClients() {
  return useQuery({
    queryKey: ["admin", "clients"],
    queryFn: async () => {
      const { data, response } = await api.GET("/api/clients");
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return data as unknown as Client[];
    },
  });
}

export function useAuditLog(params: {
  page: number;
  pageSize: number;
  user: string;
  action: string;
}) {
  return useQuery({
    queryKey: ["admin", "audit-log", params],
    queryFn: async () => {
      const { data, response } = await api.GET("/api/auth/audit-log", {
        params: {
          query: {
            page: params.page,
            page_size: params.pageSize,
            user: params.user || undefined,
            action: params.action || undefined,
          },
        },
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return data as unknown as { logs: AuditLogEntry[]; total: number };
    },
  });
}
