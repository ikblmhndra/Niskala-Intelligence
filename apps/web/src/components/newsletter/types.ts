import type { components } from "@/lib/api/schema";

type Article = components["schemas"]["ArticleOut"];

/** Port `SECTIONS` (`newsletter.html:436-441`). */
export type SectionKey = "highlight" | "apac" | "global_news" | "indonesia";

export const SECTION_MAX: Record<SectionKey, number> = {
  highlight: 1,
  apac: 5,
  global_news: 5,
  indonesia: 5,
};

export const SECTION_DEFS: { key: SectionKey; label: string }[] = [
  { key: "highlight", label: "Highlight" },
  { key: "apac", label: "APAC" },
  { key: "global_news", label: "Global" },
  { key: "indonesia", label: "Indonesia" },
];

export interface ComposerState {
  highlight: Article | null;
  apac: Article[];
  global_news: Article[];
  indonesia: Article[];
  notes: Record<string, string>;
}

export interface TemplateState {
  customCss: string;
  customIntro: string;
  customFooter: string;
  includeClusters: boolean;
  clusterDays: number;
}

export const EMPTY_COMPOSER_STATE: ComposerState = {
  highlight: null,
  apac: [],
  global_news: [],
  indonesia: [],
  notes: {},
};

export const DEFAULT_TEMPLATE_STATE: TemplateState = {
  customCss: "",
  customIntro: "",
  customFooter: "",
  includeClusters: false,
  clusterDays: 7,
};

export interface PreviewDialogState {
  open: boolean;
  title: string;
  html: string | null;
  mode: "compose" | "saved";
  savedId?: number;
  week?: number;
  year?: number;
}

export const PREVIEW_DIALOG_CLOSED: PreviewDialogState = {
  open: false,
  title: "",
  html: null,
  mode: "compose",
};
