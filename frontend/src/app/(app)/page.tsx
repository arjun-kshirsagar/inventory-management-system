"use client";

import Link from "next/link";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Badge, Card, Empty, PageHeader, Spinner, Stat, Table, Td, Th } from "@/components/ui";
import { inr, num } from "@/lib/format";
import { type Dashboard, type LowStockRow, useReport } from "@/lib/hooks/reports";

export default function DashboardPage() {
  const dash = useReport<Dashboard>("dashboard");
  const low = useReport<LowStockRow[]>("low-stock");

  if (dash.isLoading || !dash.data) return <Spinner />;
  const d = dash.data;
  const trend = d.trend.map((t) => ({
    ...t,
    label: new Date(t.date).toLocaleDateString("en-IN", { day: "numeric", month: "short" }),
    total: num(t.total),
  }));

  return (
    <>
      <PageHeader title="Dashboard" description={`Today, ${new Date(d.date).toDateString()}`} />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Sales today" value={inr(d.sales_total)} hint={`Net of refunds ${inr(d.net_sales)}`} />
        <Stat label="Bills" value={String(d.bills)} hint={`${d.items_sold} items sold`} />
        <Stat label="Average bill" value={inr(d.average_bill)} />
        <Stat label="Low-stock variants" value={String(d.low_stock_count)} hint="At or below reorder level" />
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-3">
        <Card title="Sales, last 30 days" className="xl:col-span-2">
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={trend} margin={{ left: 8, right: 8 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                <XAxis dataKey="label" tick={{ fontSize: 11 }} interval={4} tickLine={false} />
                <YAxis
                  tick={{ fontSize: 11 }}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={(v: number) => `₹${v >= 1000 ? `${Math.round(v / 1000)}k` : v}`}
                />
                <Tooltip
                  formatter={(v) => [inr(Number(v)), "Sales"]}
                  labelFormatter={(l) => String(l)}
                  cursor={{ fill: "#f1f5f9" }}
                />
                <Bar dataKey="total" fill="#6d28d9" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card
          title="Reorder soon"
          actions={
            <Link href="/inventory?low=1" className="text-sm text-brand-600 hover:underline">
              View all
            </Link>
          }
        >
          {low.data && low.data.length > 0 ? (
            <Table>
              <thead>
                <tr>
                  <Th>Item</Th>
                  <Th className="text-right">On hand</Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {low.data.slice(0, 8).map((r) => (
                  <tr key={r.variant_id}>
                    <Td>
                      <div className="font-medium">{r.product_name}</div>
                      <div className="text-xs text-slate-500">
                        {r.size} · {r.color}
                      </div>
                    </Td>
                    <Td className="text-right">
                      <Badge tone={r.on_hand === 0 ? "red" : "amber"}>{r.on_hand}</Badge>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          ) : (
            <Empty>All stock above reorder levels.</Empty>
          )}
        </Card>
      </div>
    </>
  );
}
