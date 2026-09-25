const LEVEL_COLORS = ["#e94560", "#f18f01", "#2e86ab", "#533483", "#1b7f5e", "#7b2d8b"];
const DEFAULT_FG = "#ffffff";

let initialized = false;

async function getMermaid() {
  const mermaid = (await import("mermaid")).default;
  if (!initialized) {
    mermaid.initialize({
      startOnLoad: false,
      theme: "dark",
      themeVariables: {
        darkMode: true,
        background: "#0d1117",
        mainBkg: "#161b22",
        nodeBorder: "#30363d",
        titleColor: "#e6edf3",
        fontFamily: "'IBM Plex Mono', monospace",
        fontSize: "12px",
      },
      mindmap: { padding: 16, useMaxWidth: true },
    });
    initialized = true;
  }
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
      stroke: #5a6a80 !important;
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
