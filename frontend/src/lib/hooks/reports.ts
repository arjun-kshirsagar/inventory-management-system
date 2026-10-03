"use client";

import { useQuery } from "@tanstack/react-query";

import { fetchFile } from "@/lib/api/client";

// Report endpoints return untyped JSON (dict) from FastAPI; these types mirror app/services/reports.py.
export type Money = string;

export type Dashboard = {
  date: string;
  sales_total: Money;
  refunds_total: Money;
  net_sales: Money;
  bills: number;
  items_sold: number;
  average_bill: Money;
  low_stock_count: number;
  trend: { date: string; bills: number; total: Money }[];
};

export type SalesReport = {
  rows: { key: string; bills: number; qty: number; taxable_value: Money; tax: Money; total: Money }[];
  payments: { method: string; count: number; amount: Money }[];
  totals: { qty: number; taxable_value: Money; tax: Money; total: Money };
};

export type VariantPerf = {
  variant_id: number;
  product_name: string;
  sku: string;
  size: string;
  color: string;
  qty_sold: number;
  revenue: Money;
  on_hand: number;
};
export type SellThrough = { key: string; qty_sold: number; on_hand: number; sell_through_pct: Money };
export type ProductReport = {
  best_sellers: VariantPerf[];
  slow_movers: VariantPerf[];
  by_size: SellThrough[];
  by_color: SellThrough[];
};

export type ValuationReport = {
  rows: { category: string; variants: number; units: number; cost_value: Money; retail_value: Money; mrp_value: Money }[];
  totals: { variants: number; units: number; cost_value: Money; retail_value: Money; mrp_value: Money };
};

export type LowStockRow = {
  variant_id: number;
  product_name: string;
  sku: string;
  size: string;
  color: string;
  on_hand: number;
  reorder_level: number;
  suggested_order_qty: number;
};

export type GstReport = {
  hsn: { hsn_code: string; gst_rate: Money; qty: number; taxable_value: Money; cgst: Money; sgst: Money; igst: Money; total: Money }[];
  credit_notes: { hsn_code: string; gst_rate: Money; qty: number; taxable_value: Money; tax: Money; total: Money }[];
  by_supply_type: { supply_type: string; invoices: number; taxable_value: Money; tax: Money }[];
};

export type ProfitReport = {
  rows: { date: string; qty: number; revenue: Money; cogs: Money; gross_profit: Money; margin_pct: Money }[];
  totals: { revenue: Money; cogs: Money; gross_profit: Money; margin_pct: Money };
};

function qs(params: Record<string, string | number | undefined>) {
  const s = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== "") s.set(k, String(v));
  return s.toString();
}

async function getJson<T>(path: string): Promise<T> {
  const blob = await fetchFile(path);
  return JSON.parse(await blob.text()) as T;
}

export function useReport<T>(name: string, params: Record<string, string | number | undefined> = {}) {
  return useQuery({
    queryKey: ["reports", name, params],
    queryFn: () => getJson<T>(`/api/v1/reports/${name}?${qs(params)}`),
  });
}

export function reportCsvUrl(name: string, params: Record<string, string | number | undefined>) {
  return `/api/v1/reports/${name}?${qs({ ...params, format: "csv" })}`;
}
