"use client";

import { useAuth } from "@/components/providers/auth-provider";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/** Placeholder Grup A -- isi beneran (6 chart + scraper health widget)
 * nunggu Grup B (docs/PROGRESS.md Fase 8). Halaman ini eksis buat
 * validasi pipa auth+layout+nav ada tujuan setelah login. */
export default function DashboardPage() {
  const { user } = useAuth();

  return (
    <Card className="max-w-md">
      <CardHeader>
        <CardTitle className="font-heading">Dashboard</CardTitle>
      </CardHeader>
      <CardContent className="space-y-1 text-sm text-muted-foreground">
        <p>
          Signed in as <span className="font-mono text-foreground">{user?.username}</span> (
          {user?.role})
        </p>
        <p>Grup A fondasi -- konten dashboard beneran nyusul Grup B.</p>
      </CardContent>
    </Card>
  );
}
