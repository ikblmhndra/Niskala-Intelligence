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

/**
 * Grup C (`/xintel`, `/admin/users`) -- sisa endpoint yang response-nya
 * `dict[str,object]`/`list[dict[str,object]]` polos di backend (kebanyakan
 * `routers/auth.py`/`roles.py`/`clients.py` gak declare `response_model`
 * sama sekali). Shape dicek dari `_serialize()`/return dict tiap endpoint
 * langsung.
 */

export interface AuthorCount {
  author: string;
  count: number;
}

export interface TweetStats {
  total: number;
  top_authors: AuthorCount[];
}

export interface AdminUser {
  username: string;
  role: string;
  client_ids: string[];
  force_pw_change: boolean;
  last_sign_in: string | null;
  created_at: string;
}

export interface Permission {
  key: string;
  description: string;
}

export interface Role {
  name: string;
  display_name: string;
  permissions: string[];
  is_system: boolean;
  created_by: string | null;
  created_at: string;
}

export interface Client {
  client_id: string;
  name: string;
  countries: string[];
  created_at: string;
}

export interface AuditLogEntry {
  user: string;
  action: string;
  target_id: string | null;
  detail: Record<string, unknown> | null;
  ip: string;
  timestamp: string;
}

export interface PasswordPolicy {
  min_length: number;
  require_upper: boolean;
  require_lower: boolean;
  require_number: boolean;
  require_symbol: boolean;
  hint?: string;
}

/**
 * Grup D (`/newsroom`) -- `RansomwareVictimOut` didefinisikan di
 * `schemas/ransomware.py` tapi router-nya (`GET /api/ransomware/victims`)
 * gak declare `response_model`, jadi model itu GAK NONGOL di
 * `openapi.json` sama sekali (`schema.d.ts` gak generate tipe-nya).
 * Field dicek langsung dari `_serialize()` di `routers/ransomware.py`.
 */
export interface RansomwareVictim {
  id: number;
  group_name: string;
  victim: string;
  domain: string | null;
  description: string | null;
  country_code: string | null;
  industry: string | null;
  published: string | null;
  discovered: string | null;
  post_url: string;
  ransom: string | null;
  data_size: string | null;
  screenshot: string | null;
}
