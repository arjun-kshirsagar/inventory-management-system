"use client";

import { Search } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Input } from "@/components/ui";
import { api, type Schemas } from "@/lib/api/client";
import { inr } from "@/lib/format";

type Variant = Schemas["VariantLookup"];

/** Barcode/SKU/name search that reports the chosen variant. */
export function VariantSearch({ onSelect, placeholder }: { onSelect: (v: Variant) => void; placeholder?: string }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Variant[]>([]);

  async function search(e: React.FormEvent) {
    e.preventDefault();
    if (!q.trim()) return;
    const { data } = await api.GET("/api/v1/variants/lookup", { params: { query: { q: q.trim(), limit: 30 } } });
    if (!data?.length) return toast.error(`Nothing found for “${q}”`);
    if (data.length === 1) return pick(data[0]);
    setResults(data);
  }

  function pick(v: Variant) {
    onSelect(v);
    setQ("");
    setResults([]);
  }

  return (
    <form onSubmit={search} className="relative">
      <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
      <Input
        className="pl-9"
        placeholder={placeholder ?? "Scan or search product, then Enter"}
        value={q}
        onChange={(e) => setQ(e.target.value)}
      />
      {results.length > 0 && (
        <ul className="absolute z-10 mt-1 max-h-72 w-full overflow-y-auto rounded-md border border-slate-200 bg-white shadow-lg">
          {results.map((v) => (
            <li key={v.id}>
              <button
                type="button"
                onClick={() => pick(v)}
                className="flex w-full justify-between px-3 py-2 text-left text-sm hover:bg-brand-50"
              >
                <span>
                  {v.product_name}{" "}
                  <span className="text-slate-500">
                    {v.size} · {v.color} · {v.sku}
                  </span>
                </span>
                <span className="text-slate-500">
                  {v.quantity_on_hand} in stock · {inr(v.selling_price)}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </form>
  );
}
