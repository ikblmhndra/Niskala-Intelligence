"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api/client";

export interface NewsroomFilters {
  search: string;
  dateStart: string;
  dateEnd: string;
  country: string;
  industry: string;
  actor: string;
}

function isoDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

/** Default range "7 hari terakhir" -- port default `autorefresh.js` init
 * (`_d7`/`_todayD`), BUKAN unfiltered/all-time. Newsroom lama emang selalu
 * mulai ke-scope 7 hari, bukan preferensi UI baru. */
export function defaultNewsroomFilters(): NewsroomFilters {
  const today = new Date();
  const weekAgo = new Date(today);
  weekAgo.setDate(today.getDate() - 7);
  return {
    search: "",
    dateStart: isoDate(weekAgo),
    dateEnd: isoDate(today),
    country: "",
    industry: "",
    actor: "",
  };
}

/**
 * Port `/api/filters` (isi dropdown country/industry/actor). Country di
 * sini kode ISO alpha-2 langsung dari `FilterOptions.countries` --
 * `variantToCanonical`/`expandCountry`/`/api/country-groups` legacy
 * SENGAJA gak diport, `routers/articles.py` sendiri bilang itu peta
 * nama-negara-bebas-teks yang udah obsolete (skema baru `ArticleCountry.
 * country_code` udah ISO alpha-2 dari enrichment, gak ada lagi varian
 * nama yang perlu di-grup di layer API).
 */
export function useFilterOptions() {
  return useQuery({
    queryKey: ["newsroom", "filter-options"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/filters");
      if (error) throw error;
      return data;
    },
    staleTime: 5 * 60_000,
  });
}
