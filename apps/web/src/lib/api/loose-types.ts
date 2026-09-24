/**
 * `/api/ta/stats` dan seluruh `/api/recap/*` balikin `dict[str, object]`
 * di backend (lihat `routers/ta_groups.py::ta_stats` dan
 * `routers/recap.py`) -- `schema.d.ts` generate tipe generik
 * `{[key: string]: unknown}` buat response-nya, gak ada shape asli.
 * Interface di bawah nge-declare shape RIIL yang dipakai (dicek langsung
 * dari `AsyncTARepo.get_ta_stats()` dan `cti_api.services.recap._to_dict`/
 * `SYSTEM_PROMPT` schema), bukan tebakan dari nama field lama.
 */

import type { components } from "./schema";

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

/**
 * Grup E (`/cve` -- CVE core+ticket+lookup) -- `routers/cve.py` endpoint
 * di bawah gak declare `response_model`, shape dicek dari test snapshot
 * riil (`tests/integration/__snapshots__/test_cve_router_snapshot.ambr`)
 * BUKAN tebakan dari nama field lama -- lihat gotcha `CveTicket` vs
 * `CveTracker` keduanya punya field `active_exploitation` yang TIDAK
 * berelasi (satu bool machine-set, satu string soft-enum analyst-set).
 */
export interface CveTicket {
  ticket_id: string;
  cve_id: string;
  affected_asset: string;
  affected_version: string;
  fixed_version: string;
  asset_owner: string;
  owner_email: string;
  owner_team: string;
  active_exploitation: string;
  remediation_date_plan: string;
  remediation_status: string;
  actual_remediation_date: string;
  escalation_required: boolean;
  comments: string;
  risk_acceptance: string;
  closure_date: string;
  acknowledged_by: string;
  acknowledge_time: string;
}

/** `GET /{cve_id}/ticket` balikin `{}` kalau belum ada ticket (port
 * apa adanya legacy, bukan 404) -- bukan error state. */
export type CveTicketResponse = CveTicket | Record<string, never>;

export interface AckStatusMap {
  [cveId: string]: string;
}

export interface CisaLookupResult {
  checked: number;
  matched: number;
  catalog_size: number;
  matched_cves: string[];
}

export interface EpssLookupResult {
  checked: number;
  scored: number;
  no_data: number;
}

export interface ExploitLookupBulkResult {
  checked: number;
  with_exploits: number;
  total_found: number;
  errors: number;
  details: { cve_id: string; found: number; error?: string }[];
}

export interface ExploitLookupSingleResult {
  cve_id: string;
  found: number;
  error?: string;
}

export interface DraftEmailResult {
  email_id: string;
  method: string;
  subject: string;
  cve_count: number;
}

export interface BulkAcknowledgeResult {
  ok: boolean;
  acknowledged: number;
}

/** `bulk-false-positive` balikin HTTP 200 dengan `ok:false` buat
 * validasi gagal (bukan HTTPException) -- cek `.ok`, bukan status. */
export interface BulkFalsePositiveResult {
  ok: boolean;
  marked?: number;
  detail?: string;
}

/**
 * Grup E (`/cve` -- Tech Stack subview) -- `routers/techstack.py`
 * endpoint mutasi gak declare `response_model`.
 */
export interface TechStackActionResult {
  success: boolean;
  reason?: string;
  item?: components["schemas"]["TechStackOut"];
}

export interface TechStackSuccessFlag {
  success: boolean;
}

/**
 * Grup E (`/cve` -- Package Vulnerability subview) --
 * `routers/pkg_vuln.py` endpoint mutasi/aksi gak declare `response_model`.
 */
export interface PkgAddResult {
  success: boolean;
  id?: number;
  name?: string;
  ecosystem?: string;
  version?: string | null;
}

export interface PkgPatchResult {
  success: boolean;
  changed: boolean;
  rescan?: boolean;
  id?: number;
  name?: string;
  ecosystem?: string;
  version?: string | null;
}

export interface PkgDeleteResult {
  success: boolean;
  deleted?: string;
}

export interface PkgTaskStartedResult {
  started: boolean;
  package?: string;
  ecosystem?: string;
  version?: string | null;
}

export interface PkgVulnStats {
  packages: number;
  total_vulns: number;
  critical: number;
  high: number;
  medium: number;
  low: number;
  unacknowledged: number;
  kev_count: number;
}

export interface PkgVulnAckResult {
  success: boolean;
  acknowledged: boolean;
}
