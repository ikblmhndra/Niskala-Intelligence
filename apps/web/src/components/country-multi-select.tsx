"use client";

import { useMemo, useState } from "react";

import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { COUNTRIES } from "@/lib/countries";

interface CountryMultiSelectProps {
  value: string[];
  onChange: (next: string[]) => void;
}

/**
 * Generik (deferred sejak Grup A, dipakai pertama kali beneran di sini --
 * Client Tenant country assignment, Grup C). Port `_buildCountryPicker()`
 * lama (search input + checkbox list scrollable) -- bukan `<Command>`/
 * combobox baru, biar gak nambah dependency (`cmdk`) buat satu use-case.
 *
 * `value`/`onChange` pakai kode ISO alpha-2 (BUKAN nama penuh kayak
 * `_COUNTRIES` legacy) -- KETEMU LIVE: `client_countries.country_code`
 * di skema Postgres baru `VARCHAR(2)`, ngirim "Indonesia" mentah bikin
 * `POST /api/clients` 500 (`StringDataRightTruncationError`). Nama penuh
 * cuma buat label yang ditampilin/dicari, bukan value yang dikirim.
 */
export function CountryMultiSelect({ value, onChange }: CountryMultiSelectProps) {
  const [query, setQuery] = useState("");
  const selected = useMemo(() => new Set(value), [value]);
  const filtered = useMemo(
    () =>
      COUNTRIES.filter(
        (c) => c.name.toLowerCase().includes(query.toLowerCase()) || c.code.toLowerCase() === query.toLowerCase(),
      ),
    [query],
  );

  function toggle(code: string) {
    onChange(selected.has(code) ? value.filter((c) => c !== code) : [...value, code]);
  }

  return (
    <div className="rounded-md border border-border p-2">
      <Input
        placeholder="Search countries…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        className="mb-1.5 font-mono text-xs"
      />
      <div className="flex max-h-40 flex-col gap-0.5 overflow-y-auto">
        {filtered.map((c) => (
          <label
            key={c.code}
            className="flex cursor-pointer items-center gap-2 rounded-sm px-1 py-0.5 text-xs hover:bg-accent"
          >
            <Checkbox checked={selected.has(c.code)} onCheckedChange={() => toggle(c.code)} />
            {c.name} <span className="font-mono text-[9px] text-muted-foreground">{c.code}</span>
          </label>
        ))}
      </div>
    </div>
  );
}
