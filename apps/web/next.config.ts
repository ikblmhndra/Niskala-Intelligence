import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Build "standalone": `.next/standalone/server.js` + cuma node_modules yang
  // beneran dipakai (file tracing) -- image `web` (docker/web.Dockerfile)
  // jalan tanpa `pnpm install` penuh, jauh lebih kecil.
  output: "standalone",
};

export default nextConfig;
