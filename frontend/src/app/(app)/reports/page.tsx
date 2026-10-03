"use client";

import clsx from "clsx";
import { Download } from "lucide-react";
import { useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { toast } from "sonner";

import { Badge, Button, Card, Empty, Input, PageHeader, Select, Spinner, Stat, Table, Td, Th } from "@/components/ui";
import { downloadBlob, errorMessage, fetchFile } from "@/lib/api/client";
import { daysAgo, formatDate, inr, isoDate, num } from "@/lib/format";
import {
  type GstReport,
  type LowStockRow,
  type ProductReport,
  type ProfitReport,
  type SalesReport,
  type ValuationReport,
  reportCsvUrl,
  useReport,
} from "@/lib/hooks/reports";

const TABS = [
  ["sales", "Sales"],
  ["products", "Best & slow sellers"],
  ["valuation", "Stock valuation"],
  ["low", "Low stock"],
  ["gst", "GST summary"],
  ["profit", "Profit"],
] as const;
type Tab = (typeof TABS)[number][0];

type Range = { start: string; end: string };

async function downloadCsv(name: string, params: Record<string, string | number | undefined>) {
  try {
    downloadBlob(await fetchFile(reportCsvUrl(name, params)), `${name}.csv`);
  } catch (e) {
    toast.error(errorMessage(e));
  }
}

function CsvButton({ name, params }: { name: string; params: Record<string, string | number | undefined> }) {
  return (
    <Button variant="secondary" size="sm" onClick={() => downloadCsv(name, params)}>
      <Download size={14} /> CSV
    </Button>
  );
}

export default function ReportsPage() {
  const [tab, setTab] = useState<Tab>("sales");
  const [range, setRange] = useState<Range>({ start: daysAgo(29), end: isoDate(new Date()) });
  const usesRange = !["valuation", "low"].includes(tab);

  return (
    <>
      <PageHeader
        title="Reports"
        actions={
          usesRange && (
            <>
              <Input type="date" value={range.start} onChange={(e) => setRange({ ...range, start: e.target.value })} aria-label="From" />
              <span className="text-slate-400">to</span>
              <Input type="date" value={range.end} onChange={(e) => setRange({ ...range, end: e.target.value })} aria-label="To" />
              <Select
                className="w-40"
                value=""
                onChange={(e) => {
                  const days = Number(e.target.value);
                  if (days) setRange({ start: daysAgo(days - 1), end: isoDate(new Date()) });
                }}
                aria-label="Quick range"
              >
                <option value="">Quick range…</option>
                <option value="1">Today</option>
                <option value="7">Last 7 days</option>
                <option value="30">Last 30 days</option>
                <option value="90">Last 90 days</option>
              </Select>
            </>
          )
        }
      />
      <div className="mb-4 flex flex-wrap gap-1 border-b border-slate-200">
        {TABS.map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={clsx(
              "-mb-px border-b-2 px-4 py-2 text-sm font-medium",
              tab === key ? "border-brand-600 text-brand-700" : "border-transparent text-slate-500 hover:text-slate-700",
            )}
          >
            {label}
          </button>
        ))}
      </div>
      {tab === "sales" && <SalesTab range={range} />}
      {tab === "products" && <ProductsTab range={range} />}
      {tab === "valuation" && <ValuationTab />}
      {tab === "low" && <LowStockTab />}
      {tab === "gst" && <GstTab range={range} />}
      {tab === "profit" && <ProfitTab range={range} />}
    </>
  );
}

const GROUPS = [
  ["day", "Day"],
  ["category", "Category"],
  ["brand", "Brand"],
  ["cashier", "Cashier"],
  ["size", "Size"],
  ["color", "Colour"],
] as const;

function SalesTab({ range }: { range: Range }) {
  const [groupBy, setGroupBy] = useState("day");
  const params = { ...range, group_by: groupBy };
  const report = useReport<SalesReport>("sales", params);
  const d = report.data;
  return (
    <div className="space-y-6">
      {d && (
        <div className="grid gap-4 sm:grid-cols-4">
          <Stat label="Net sales" value={inr(d.totals.total)} hint="Net of returns, incl. GST" />
          <Stat label="Taxable value" value={inr(d.totals.taxable_value)} />
          <Stat label="GST" value={inr(d.totals.tax)} />
          <Stat label="Units sold" value={String(d.totals.qty)} />
        </div>
      )}
      <Card
        title={
          <span className="flex items-center gap-3">
            Sales by
            <Select className="w-36" value={groupBy} onChange={(e) => setGroupBy(e.target.value)}>
              {GROUPS.map(([k, l]) => (
                <option key={k} value={k}>
                  {l}
                </option>
              ))}
            </Select>
          </span>
        }
        actions={<CsvButton name="sales" params={params} />}
      >
        {report.isLoading ? (
          <Spinner />
        ) : !d?.rows.length ? (
          <Empty>No sales in this period.</Empty>
        ) : (
          <>
            <div className="mb-6 h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={d.rows.map((r) => ({ ...r, total: num(r.total), label: groupBy === "day" ? formatDate(r.key) : r.key }))}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                  <XAxis dataKey="label" tick={{ fontSize: 11 }} tickLine={false} />
                  <YAxis tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                  <Tooltip formatter={(v) => inr(Number(v))} cursor={{ fill: "#f1f5f9" }} />
                  <Bar dataKey="total" name="Sales" fill="#6d28d9" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <Table>
              <thead>
                <tr>
                  <Th>{GROUPS.find(([k]) => k === groupBy)?.[1]}</Th>
                  <Th className="text-right">Bills</Th>
                  <Th className="text-right">Units</Th>
                  <Th className="text-right">Taxable</Th>
                  <Th className="text-right">GST</Th>
                  <Th className="text-right">Total</Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {d.rows.map((r) => (
                  <tr key={r.key}>
                    <Td className="font-medium">{groupBy === "day" ? formatDate(r.key) : r.key}</Td>
                    <Td className="text-right tabular-nums">{r.bills}</Td>
                    <Td className="text-right tabular-nums">{r.qty}</Td>
                    <Td className="text-right tabular-nums">{inr(r.taxable_value)}</Td>
                    <Td className="text-right tabular-nums">{inr(r.tax)}</Td>
                    <Td className="text-right font-medium tabular-nums">{inr(r.total)}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </>
        )}
      </Card>
      {d && d.payments.length > 0 && (
        <Card title="Payment methods">
          <div className="grid gap-4 sm:grid-cols-3">
            {d.payments.map((p) => (
              <Stat key={p.method} label={p.method.toUpperCase()} value={inr(p.amount)} hint={`${p.count} payments`} />
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

function ProductsTab({ range }: { range: Range }) {
  const report = useReport<ProductReport>("products", { ...range, limit: 20 });
  if (report.isLoading || !report.data) return <Spinner />;
  const d = report.data;
  const variantTable = (rows: ProductReport["best_sellers"]) =>
    rows.length === 0 ? (
      <Empty>Nothing to show.</Empty>
    ) : (
      <Table>
        <thead>
          <tr>
            <Th>Item</Th>
            <Th className="text-right">Sold</Th>
            <Th className="text-right">Revenue</Th>
            <Th className="text-right">In stock</Th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((r) => (
            <tr key={r.variant_id}>
              <Td>
                <div className="font-medium">{r.product_name}</div>
                <div className="text-xs text-slate-500">
                  {r.size} · {r.color}
                </div>
              </Td>
              <Td className="text-right tabular-nums">{r.qty_sold}</Td>
              <Td className="text-right tabular-nums">{inr(r.revenue)}</Td>
              <Td className="text-right tabular-nums">{r.on_hand}</Td>
            </tr>
          ))}
        </tbody>
      </Table>
    );
  const sellThrough = (rows: ProductReport["by_size"], label: string) => (
    <Table>
      <thead>
        <tr>
          <Th>{label}</Th>
          <Th className="text-right">Sold</Th>
          <Th className="text-right">In stock</Th>
          <Th>Sell-through</Th>
        </tr>
      </thead>
      <tbody className="divide-y divide-slate-100">
        {rows.map((r) => (
          <tr key={r.key}>
            <Td className="font-medium">{r.key}</Td>
            <Td className="text-right tabular-nums">{r.qty_sold}</Td>
            <Td className="text-right tabular-nums">{r.on_hand}</Td>
            <Td>
              <div className="flex items-center gap-2">
                <div className="h-2 w-24 rounded-full bg-slate-100">
                  <div className="h-2 rounded-full bg-brand-500" style={{ width: `${num(r.sell_through_pct)}%` }} />
                </div>
                <span className="tabular-nums">{num(r.sell_through_pct).toFixed(0)}%</span>
              </div>
            </Td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
  return (
    <div className="grid gap-6 xl:grid-cols-2">
      <Card title="Best sellers" actions={<CsvButton name="products" params={{ ...range, section: "best_sellers" }} />}>
        {variantTable(d.best_sellers)}
      </Card>
      <Card title="Slow movers (in stock, sold least)" actions={<CsvButton name="products" params={{ ...range, section: "slow_movers" }} />}>
        {variantTable(d.slow_movers)}
      </Card>
      <Card title="Sell-through by size" actions={<CsvButton name="products" params={{ ...range, section: "by_size" }} />}>
        {sellThrough(d.by_size, "Size")}
      </Card>
      <Card title="Sell-through by colour" actions={<CsvButton name="products" params={{ ...range, section: "by_color" }} />}>
        {sellThrough(d.by_color, "Colour")}
      </Card>
    </div>
  );
}

function ValuationTab() {
  const report = useReport<ValuationReport>("stock-valuation");
  if (report.isLoading || !report.data) return <Spinner />;
  const d = report.data;
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-4">
        <Stat label="Units in stock" value={String(d.totals.units)} hint={`${d.totals.variants} variants`} />
        <Stat label="At cost" value={inr(d.totals.cost_value)} />
        <Stat label="At selling price" value={inr(d.totals.retail_value)} />
        <Stat label="At MRP" value={inr(d.totals.mrp_value)} />
      </div>
      <Card title="By category" actions={<CsvButton name="stock-valuation" params={{}} />}>
        <Table>
          <thead>
            <tr>
              <Th>Category</Th>
              <Th className="text-right">Variants</Th>
              <Th className="text-right">Units</Th>
              <Th className="text-right">Cost value</Th>
              <Th className="text-right">Retail value</Th>
              <Th className="text-right">MRP value</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {d.rows.map((r) => (
              <tr key={r.category}>
                <Td className="font-medium">{r.category}</Td>
                <Td className="text-right tabular-nums">{r.variants}</Td>
                <Td className="text-right tabular-nums">{r.units}</Td>
                <Td className="text-right tabular-nums">{inr(r.cost_value)}</Td>
                <Td className="text-right tabular-nums">{inr(r.retail_value)}</Td>
                <Td className="text-right tabular-nums">{inr(r.mrp_value)}</Td>
              </tr>
            ))}
          </tbody>
        </Table>
      </Card>
    </div>
  );
}

function LowStockTab() {
  const report = useReport<LowStockRow[]>("low-stock");
  if (report.isLoading || !report.data) return <Spinner />;
  return (
    <Card title={`Low stock (${report.data.length})`} actions={<CsvButton name="low-stock" params={{}} />}>
      {report.data.length === 0 ? (
        <Empty>Everything is above its reorder level.</Empty>
      ) : (
        <Table>
          <thead>
            <tr>
              <Th>Item</Th>
              <Th>SKU</Th>
              <Th className="text-right">On hand</Th>
              <Th className="text-right">Reorder at</Th>
              <Th className="text-right">Suggested order</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {report.data.map((r) => (
              <tr key={r.variant_id}>
                <Td>
                  <span className="font-medium">{r.product_name}</span>{" "}
                  <span className="text-slate-500">
                    {r.size} · {r.color}
                  </span>
                </Td>
                <Td className="font-mono text-xs">{r.sku}</Td>
                <Td className="text-right">
                  <Badge tone={r.on_hand === 0 ? "red" : "amber"}>{r.on_hand}</Badge>
                </Td>
                <Td className="text-right tabular-nums">{r.reorder_level}</Td>
                <Td className="text-right tabular-nums">{r.suggested_order_qty}</Td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </Card>
  );
}

function GstTab({ range }: { range: Range }) {
  const report = useReport<GstReport>("gst", range);
  if (report.isLoading || !report.data) return <Spinner />;
  const d = report.data;
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2">
        {d.by_supply_type.map((s) => (
          <Stat
            key={s.supply_type}
            label={`${s.supply_type} supplies`}
            value={inr(s.tax)}
            hint={`${s.invoices} invoices · taxable ${inr(s.taxable_value)}`}
          />
        ))}
      </div>
      <Card title="HSN-wise summary of outward supplies (GSTR-1 Table 12)" actions={<CsvButton name="gst" params={{ ...range, section: "hsn" }} />}>
        {d.hsn.length === 0 ? (
          <Empty>No sales in this period.</Empty>
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>HSN</Th>
                <Th className="text-right">Rate</Th>
                <Th className="text-right">Qty</Th>
                <Th className="text-right">Taxable</Th>
                <Th className="text-right">CGST</Th>
                <Th className="text-right">SGST</Th>
                <Th className="text-right">IGST</Th>
                <Th className="text-right">Total</Th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {d.hsn.map((r) => (
                <tr key={`${r.hsn_code}-${r.gst_rate}`}>
                  <Td className="font-medium">{r.hsn_code}</Td>
                  <Td className="text-right">{num(r.gst_rate)}%</Td>
                  <Td className="text-right tabular-nums">{r.qty}</Td>
                  <Td className="text-right tabular-nums">{inr(r.taxable_value)}</Td>
                  <Td className="text-right tabular-nums">{inr(r.cgst)}</Td>
                  <Td className="text-right tabular-nums">{inr(r.sgst)}</Td>
                  <Td className="text-right tabular-nums">{inr(r.igst)}</Td>
                  <Td className="text-right tabular-nums">{inr(r.total)}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
      <Card title="Credit notes issued" actions={<CsvButton name="gst" params={{ ...range, section: "credit_notes" }} />}>
        {d.credit_notes.length === 0 ? (
          <Empty>No credit notes in this period.</Empty>
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>HSN</Th>
                <Th className="text-right">Rate</Th>
                <Th className="text-right">Qty</Th>
                <Th className="text-right">Taxable</Th>
                <Th className="text-right">Tax</Th>
                <Th className="text-right">Total</Th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {d.credit_notes.map((r) => (
                <tr key={`${r.hsn_code}-${r.gst_rate}`}>
                  <Td className="font-medium">{r.hsn_code}</Td>
                  <Td className="text-right">{num(r.gst_rate)}%</Td>
                  <Td className="text-right tabular-nums">{r.qty}</Td>
                  <Td className="text-right tabular-nums">{inr(r.taxable_value)}</Td>
                  <Td className="text-right tabular-nums">{inr(r.tax)}</Td>
                  <Td className="text-right tabular-nums">{inr(r.total)}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  );
}

function ProfitTab({ range }: { range: Range }) {
  const report = useReport<ProfitReport>("profit", range);
  if (report.isLoading || !report.data) return <Spinner />;
  const d = report.data;
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-4">
        <Stat label="Revenue (excl. GST)" value={inr(d.totals.revenue)} />
        <Stat label="Cost of goods sold" value={inr(d.totals.cogs)} />
        <Stat label="Gross profit" value={inr(d.totals.gross_profit)} />
        <Stat label="Margin" value={`${num(d.totals.margin_pct).toFixed(1)}%`} />
      </div>
      <Card title="Daily profit" actions={<CsvButton name="profit" params={range} />}>
        {d.rows.length === 0 ? (
          <Empty>No sales in this period.</Empty>
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>Date</Th>
                <Th className="text-right">Units</Th>
                <Th className="text-right">Revenue</Th>
                <Th className="text-right">COGS</Th>
                <Th className="text-right">Gross profit</Th>
                <Th className="text-right">Margin</Th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {d.rows.map((r) => (
                <tr key={r.date}>
                  <Td>{formatDate(r.date)}</Td>
                  <Td className="text-right tabular-nums">{r.qty}</Td>
                  <Td className="text-right tabular-nums">{inr(r.revenue)}</Td>
                  <Td className="text-right tabular-nums">{inr(r.cogs)}</Td>
                  <Td className="text-right font-medium tabular-nums">{inr(r.gross_profit)}</Td>
                  <Td className="text-right tabular-nums">{num(r.margin_pct).toFixed(1)}%</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  );
}
