import { cssVar } from "@/lib/chart-theme";

// Fill node tetap gelap di kedua tema supaya teks putih (`DEFAULT_FG`) lulus AA.
const LEVEL_COLORS = ["#d0002f", "#b04a00", "#256a8a", "#7a3a5a", "#17703f", "#430a23"];
const DEFAULT_FG = "#ffffff";

async function getMermaid() {
  const mermaid = (await import("mermaid")).default;
  const dark = document.documentElement.classList.contains("dark");
  const v = cssVar;
  mermaid.initialize({
    startOnLoad: false,
    theme: dark ? "dark" : "default",
    themeVariables: {
      darkMode: dark,
      background: v("--background"),
      mainBkg: v("--surface"),
      nodeBorder: v("--border"),
      titleColor: v("--foreground"),
      fontFamily: "'IBM Plex Mono', monospace",
      fontSize: "12px",
    },
    mindmap: { padding: 16, useMaxWidth: true },
  });
  return mermaid;
}

let renderSeq = 0;

/** Port `_mmInjectColors()` (`mindmap.js:55-104`) -- satu warna custom
 * (`nodeBg`) kalau di-set, kalau enggak fallback ke warna per-level
 * (`_MM_LEVEL_COLORS`, node terluar merah, makin dalam makin lain). */
function injectColors(svgEl: SVGElement, nodeBg: string | null, nodeFg: string | null) {
  svgEl.querySelector("#mm-color-style")?.remove();
  const fg = nodeFg || DEFAULT_FG;
  const style = document.createElementNS("http://www.w3.org/2000/svg", "style");
  style.id = "mm-color-style";

  let css = "";
  if (nodeBg) {
    css += `
      .mindmap-node > rect, .mindmap-node > circle, .mindmap-node > polygon,
      .mindmap-node > path, .mindmap-node > ellipse {
        fill: ${nodeBg} !important;
        stroke: ${nodeBg} !important;
      }`;
  } else {
    css += `
      .mindmap-node:nth-of-type(1) > rect, .mindmap-node:nth-of-type(1) > circle,
      .mindmap-node:nth-of-type(1) > path, .mindmap-node:nth-of-type(1) > ellipse
        { fill: ${LEVEL_COLORS[0]} !important; stroke: ${LEVEL_COLORS[0]} !important; }`;
    LEVEL_COLORS.forEach((color, i) => {
      css += `
      .mindmap-node.level-${i} > rect, .mindmap-node.level-${i} > circle,
      .mindmap-node.level-${i} > path, .mindmap-node.level-${i} > ellipse,
      .mindmap-node.section-${i} > rect, .mindmap-node.section-${i} > circle,
      .mindmap-node.section-${i} > path, .mindmap-node.section-${i} > ellipse
        { fill: ${color} !important; stroke: ${color} !important; }`;
    });
  }

  css += `
    .mindmap-node text, .mindmap-node tspan,
    .mindmap-node .label, .mindmap-node foreignObject span {
      fill: ${fg} !important;
      color: ${fg} !important;
    }
    .edge, .edge path, .edge line {
      stroke: ${cssVar("--muted-foreground")} !important;
      stroke-opacity: 0.7;
      fill: none !important;
    }`;

  style.textContent = css;
  svgEl.insertBefore(style, svgEl.firstChild);
}

/** Port `_mmRender()` (`mindmap.js:110-132`). */
export async function renderMindmap(
  container: HTMLElement,
  syntax: string,
  nodeBg: string | null,
  nodeFg: string | null,
): Promise<void> {
  if (!syntax || !syntax.trim()) {
    container.innerHTML = '<span class="font-mono text-[11px] text-muted-foreground">No mind map data.</span>';
    return;
  }
  try {
    const mermaid = await getMermaid();
    const id = `mmr-${++renderSeq}`;
    const { svg } = await mermaid.render(id, syntax);
    container.innerHTML = svg;
    const svgEl = container.querySelector("svg");
    if (svgEl) {
      svgEl.style.maxWidth = "100%";
      svgEl.style.height = "auto";
      injectColors(svgEl, nodeBg, nodeFg);
    }
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    container.innerHTML = `<div class="font-mono text-[10px] whitespace-pre-wrap text-destructive">Render error:\n${msg.replace(/</g, "&lt;")}</div>`;
  }
}
