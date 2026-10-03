"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { SaleStatusBadge } from "@/components/SaleStatusBadge";
import { Card, Empty, Input, PageHeader, Pagination, Select, Spinner, Table, Td, Th } from "@/components/ui";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { formatDateTime, inr } from "@/lib/format";

const LIMIT = 25;
type Status = Schemas["SaleStatus"];

export default function SalesPage() {
  const [q, setQ] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [status, setStatus] = useState<Status | "">("");
  const [offset, setOffset] = useState(0);

  const sales = useQuery({
    queryKey: ["sales", q, start, end, status, offset],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/sales", {
          params: {
            query: {
              q: q || undefined,
              start: start || undefined,
              end: end || undefined,
              status: status || undefined,
              offset,
              limit: LIMIT,
            },
          },
        }),
      ),
    placeholderData: keepPreviousData,
  });

  return (
    <>
      <PageHeader title="Sales & Invoices" description="Search past bills, reprint invoices and process returns." />
      <Card>
        <div className="mb-4 grid gap-3 sm:grid-cols-4">
          <Input
            placeholder="Invoice no, customer name or phone"
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setOffset(0);
            }}
          />
          <Input type="date" value={start} onChange={(e) => setStart(e.target.value)} aria-label="From" />
          <Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} aria-label="To" />
          <Select value={status} onChange={(e) => setStatus(e.target.value as Status | "")}>
            <option value="">All statuses</option>
            <option value="completed">Completed</option>
            <option value="partially_returned">Partially returned</option>
            <option value="returned">Returned</option>
          </Select>
        </div>
        {sales.isLoading ? (
          <Spinner />
        ) : !sales.data?.items.length ? (
          <Empty>No sales found.</Empty>
        ) : (
          <>
            <Table>
              <thead>
                <tr>
                  <Th>Invoice</Th>
                  <Th>Date</Th>
                  <Th>Customer</Th>
                  <Th>Cashier</Th>
                  <Th className="text-right">Items</Th>
                  <Th className="text-right">Total</Th>
                  <Th>Status</Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {sales.data.items.map((s) => (
                  <tr key={s.id} className="hover:bg-slate-50">
                    <Td>
                      <Link href={`/sales/${s.id}`} className="font-medium text-brand-600 hover:underline">
                        {s.invoice_no}
                      </Link>
                    </Td>
                    <Td>{formatDateTime(s.created_at)}</Td>
                    <Td>{s.customer_name ?? <span className="text-slate-400">Walk-in</span>}</Td>
                    <Td>{s.cashier_name}</Td>
                    <Td className="text-right tabular-nums">{s.item_count}</Td>
                    <Td className="text-right font-medium tabular-nums">{inr(s.grand_total)}</Td>
                    <Td><SaleStatusBadge status={s.status} /></Td>
                  </tr>
                ))}
              </tbody>
            </Table>
            <Pagination offset={offset} limit={LIMIT} total={sales.data.total} onChange={setOffset} />
          </>
        )}
      </Card>
    </>
  );
}
