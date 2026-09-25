export interface IocChipStyle {
  label: string;
  bg: string;
  border: string;
  color: string;
}

/** Port `_IOC_TYPE_STYLE` (`ioc_mgmt.js:10-20`) -- 9 tipe IOC, warna
 * literal apa adanya (bukan token Tailwind diskrit) karena nuansanya
 * sengaja dibedain per tipe buat scan cepat di tabel gede, sama
 * keputusan kayak heatmap MITRE Grup G3. */
export const IOC_TYPE_STYLE: Record<string, IocChipStyle> = {
  ip: { label: "IP", bg: "rgba(218,54,51,0.12)", border: "rgba(218,54,51,0.35)", color: "#da3633" },
  domain: { label: "DOMAIN", bg: "rgba(227,179,65,0.12)", border: "rgba(227,179,65,0.35)", color: "#e3b341" },
  url: { label: "URL", bg: "rgba(47,129,247,0.12)", border: "rgba(47,129,247,0.35)", color: "#2f81f7" },
  url_with_path: { label: "URL+PATH", bg: "rgba(47,129,247,0.08)", border: "rgba(47,129,247,0.25)", color: "#2f81f7" },
  email: { label: "EMAIL", bg: "rgba(88,166,255,0.12)", border: "rgba(88,166,255,0.35)", color: "#58A6FF" },
  sha256: { label: "SHA256", bg: "rgba(83,52,131,0.2)", border: "rgba(83,52,131,0.4)", color: "#a78bdb" },
  sha1: { label: "SHA1", bg: "rgba(83,52,131,0.15)", border: "rgba(83,52,131,0.3)", color: "#a78bdb" },
  md5: { label: "MD5", bg: "rgba(83,52,131,0.15)", border: "rgba(83,52,131,0.3)", color: "#a78bdb" },
  cve: { label: "CVE", bg: "rgba(52,168,83,0.12)", border: "rgba(52,168,83,0.35)", color: "#34a853" },
};

export function iocTypeStyle(type: string): IocChipStyle {
  return IOC_TYPE_STYLE[type] ?? { label: type.toUpperCase(), bg: "rgba(255,255,255,0.05)", border: "rgba(255,255,255,0.15)", color: "var(--muted-foreground)" };
}

export const ACTIONABILITY_STYLE: Record<string, IocChipStyle> = {
  block_now: { label: "BLOCK NOW", bg: "rgba(218,54,51,0.15)", border: "rgba(218,54,51,0.45)", color: "#da3633" },
  investigate: { label: "INVESTIGATE", bg: "rgba(255,165,0,0.12)", border: "rgba(255,165,0,0.4)", color: "#ffaa00" },
  monitor: { label: "MONITOR", bg: "rgba(227,179,65,0.12)", border: "rgba(227,179,65,0.35)", color: "#e3b341" },
  archive: { label: "ARCHIVE", bg: "rgba(255,255,255,0.04)", border: "rgba(255,255,255,0.15)", color: "var(--muted-foreground)" },
};

export function actionabilityStyle(label: string): IocChipStyle {
  return ACTIONABILITY_STYLE[label] ?? ACTIONABILITY_STYLE.archive;
}

export function confidenceStyle(score: number): IocChipStyle {
  if (score >= 75) return { label: String(score), bg: "rgba(52,168,83,0.15)", border: "rgba(52,168,83,0.4)", color: "#34a853" };
  if (score >= 40) return { label: String(score), bg: "rgba(255,165,0,0.12)", border: "rgba(255,165,0,0.4)", color: "#ffaa00" };
  return { label: String(score), bg: "rgba(255,255,255,0.05)", border: "rgba(255,255,255,0.15)", color: "var(--muted-foreground)" };
}
