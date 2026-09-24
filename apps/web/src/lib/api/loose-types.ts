/**
 * `/api/ta/stats` dan seluruh `/api/recap/*` balikin `dict[str, object]`
 * di backend (lihat `routers/ta_groups.py::ta_stats` dan
 * `routers/recap.py`) -- `schema.d.ts` generate tipe generik
 * `{[key: string]: unknown}` buat response-nya, gak ada shape asli.
 * Interface di bawah nge-declare shape RIIL yang dipakai (dicek langsung
 * dari `AsyncTARepo.get_ta_stats()` dan `cti_api.services.recap._to_dict`/
 * `SYSTEM_PROMPT` schema), bukan tebakan dari nama field lama.
 */

export interface NamedCount {
  name: string;
  count: number;
}

export interface TaStats {
  total_groups: number;
  total_whitelisted: number;
  manual_count: number;
  in_news_count: number;
  by_source: NamedCount[];
  top_in_news: NamedCount[];
}

export interface RecapTopStory {
  title: string;
  why_it_matters?: string;
  source?: string;
}

export interface RecapTopTweet {
  author?: string;
  summary?: string;
  signal?: string;
}

export interface RecapActiveCampaign {
  theme?: string;
  article_count?: number;
  why_it_matters?: string;
}

export interface RecapLikelyEvent {
  event?: string;
  basis?: string;
  confidence?: string;
}

export interface RecapBody {
  summary?: string;
  top_stories?: RecapTopStory[];
  top_tweets?: RecapTopTweet[];
  active_threat_actors?: string[];
  notable_cves?: string[];
  active_campaigns?: RecapActiveCampaign[];
  apac_signals?: string[];
}

export interface RecapForecast {
  summary?: string;
  likely_events?: RecapLikelyEvent[];
  watch_items?: string[];
}

export interface RecapCounts {
  articles?: number;
  tweets?: number;
  iocs?: number;
  cves?: number;
  campaigns?: number;
  new_threat_actors?: number;
}

export interface RecapDoc {
  id: number;
  date: string;
  headline: string;
  yesterday: RecapBody;
  forecast: RecapForecast;
  counts: RecapCounts;
  generated_at: string;
  model: string;
  token_usage: { total_tokens?: number };
  raw_llm: string | null;
  cached: boolean;
}

export interface RecapListItem {
  date: string;
  headline: string;
  counts: RecapCounts;
  generated_at: string;
}
