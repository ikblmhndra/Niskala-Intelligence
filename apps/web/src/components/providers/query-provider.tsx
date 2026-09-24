"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

export function QueryProvider({ children }: { children: React.ReactNode }) {
  // `useState(() => new QueryClient())` -- satu instance per mount klien,
  // bukan per render (dan bukan module-level singleton, biar gak kebawa
  // lintas request pas SSR).
  const [client] = useState(() => new QueryClient());
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
