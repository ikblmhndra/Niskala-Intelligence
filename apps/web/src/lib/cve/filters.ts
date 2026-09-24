"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";

export interface CveFilters {
  search: string;
  severity: string;
  tech: string;
  dateStart: string;
  dateEnd: string;
  includeFp: boolean;
  unackedOnly: boolean;
}

export function defaultCveFilters(): CveFilters {
  return {
    search: "",
    severity: "",
    tech: "",
    dateStart: "",
    dateEnd: "",
    includeFp: false,
    unackedOnly: false,
  };
}

export const CVE_SEVERITIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW"] as const;

/** Port `_loadCveTechOptions()` (`cve.js:412`), `GET /api/cve/tech-list`. */
export function useCveTechOptions() {
  return useQuery({
    queryKey: ["cve", "tech-list"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/cve/tech-list");
      if (error) throw error;
      return data;
    },
  });
}
