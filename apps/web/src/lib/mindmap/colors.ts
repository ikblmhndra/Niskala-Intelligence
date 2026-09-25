const DEFAULT_FG = "#ffffff";

export interface MindmapColorPrefs {
  nodeBg: string | null;
  nodeFg: string | null;
}

function key(featureType: string, docId: string) {
  return `mm-colors::${featureType}::${docId}`;
}

/** Port `_mmLoadColors()`/`_mmSaveColors()` (`mindmap.js:41-53`) --
 * preferensi warna per-diagram, per-viewer, gak perlu server round-trip. */
export function loadMindmapColors(featureType: string, docId: string): MindmapColorPrefs {
  try {
    const raw = localStorage.getItem(key(featureType, docId));
    if (!raw) return { nodeBg: null, nodeFg: null };
    const parsed = JSON.parse(raw) as Partial<MindmapColorPrefs>;
    return { nodeBg: parsed.nodeBg ?? null, nodeFg: parsed.nodeFg ?? null };
  } catch {
    return { nodeBg: null, nodeFg: null };
  }
}

export function saveMindmapColors(featureType: string, docId: string, nodeBg: string | null, nodeFg: string | null): void {
  try {
    localStorage.setItem(key(featureType, docId), JSON.stringify({ nodeBg, nodeFg }));
  } catch {
    // best-effort, sama kayak legacy (private window/blocked storage)
  }
}

export { DEFAULT_FG };
