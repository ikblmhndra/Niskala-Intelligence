/** Warna token + alpha tanpa hex-suffix (`${color}18`) -- works untuk `var(--x)`. */
export const tint = (color: string, pct: number) => `color-mix(in srgb, ${color} ${pct}%, transparent)`;
