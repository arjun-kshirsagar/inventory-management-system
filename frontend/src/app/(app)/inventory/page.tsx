"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { PackagePlus, SlidersHorizontal } from "lucide-react";
import Link from "next/link";
import { Fragment, Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { toast } from "sonner";

import {
  Badge,
  Button,
  Card,
  Empty,
  Field,
  Input,
  Modal,
  PageHeader,
  Pagination,
  Select,
  Spinner,
  Table,
  Td,
  Th,
} from "@/components/ui";
import { api, errorMessage, unwrap, type Schemas } from "@/lib/api/client";
import { useAuth } from "@/lib/auth";
import { formatDateTime, inr } from "@/lib/format";
import { useCategories } from "@/lib/hooks/catalog";

type Tab = "stock" | "receipts" | "movements";
type StockLevel = Schemas["StockLevel"];

export default function InventoryPage() {
  return (
    <Suspense fallback={<Spinner />}>
      <Inventory />
    </Suspense>
  );
}

function Inventory() {
  const params = useSearchParams();
  const [tab, setTab] = useState<Tab>("stock");
  return (
    <>
      <PageHeader
        title="Inventory"
        description="Stock on hand per size and colour, goods received and every stock movement."
        actions={
          <Link href="/inventory/receive">
            <Button>
              <PackagePlus size={16} /> Receive stock
            </Button>
          </Link>
        }
      />
      <div className="mb-4 flex gap-1 border-b border-slate-200">
        {(["stock", "receipts", "movements"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={clsx(
              "-mb-px border-b-2 px-4 py-2 text-sm font-medium capitalize",
              tab === t ? "border-brand-600 text-brand-700" : "border-transparent text-slate-500 hover:text-slate-700",
            )}
          >
            {t === "receipts" ? "Goods received" : t}
          </button>
        ))}
      </div>
      {tab === "stock" && <StockTab lowOnly={params.get("low") === "1"} />}
      {tab === "receipts" && <ReceiptsTab />}
      {tab === "movements" && <MovementsTab />}
    </>
  );
}

const LIMIT = 50;

function StockTab({ lowOnly: initialLow }: { lowOnly: boolean }) {
  const { user } = useAuth();
  const [q, setQ] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [size, setSize] = useState("");
  const [lowOnly, setLowOnly] = useState(initialLow);
  const [offset, setOffset] = useState(0);
  const [adjusting, setAdjusting] = useState<StockLevel | null>(null);
  const categories = useCategories();

  const stock = useQuery({
    queryKey: ["stock", q, categoryId, size, lowOnly, offset],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/inventory/stock", {
          params: {
            query: {
              q: q || undefined,
              category_id: categoryId ? Number(categoryId) : undefined,
              size: size || undefined,
              low_stock_only: lowOnly,
              offset,
              limit: LIMIT,
            },
          },
        }),
      ),
    placeholderData: keepPreviousData,
  });

  return (
    <Card>
      <div className="mb-4 grid items-center gap-3 sm:grid-cols-4">
        <Input placeholder="Search name, SKU, barcode" value={q} onChange={(e) => (setQ(e.target.value), setOffset(0))} />
        <Select value={categoryId} onChange={(e) => (setCategoryId(e.target.value), setOffset(0))}>
          <option value="">All categories</option>
          {categories.data?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </Select>
        <Input placeholder="Size (e.g. M, 32)" value={size} onChange={(e) => (setSize(e.target.value), setOffset(0))} />
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            className="h-4 w-4 accent-brand-600"
            checked={lowOnly}
            onChange={(e) => (setLowOnly(e.target.checked), setOffset(0))}
          />
          Low stock only
        </label>
      </div>
      {stock.isLoading ? (
        <Spinner />
      ) : !stock.data?.items.length ? (
        <Empty>No matching stock.</Empty>
      ) : (
        <>
          <Table>
            <thead>
              <tr>
                <Th>Product</Th>
                <Th>Size</Th>
                <Th>Colour</Th>
                <Th>SKU</Th>
                <Th>Category</Th>
                <Th className="text-right">Price</Th>
                <Th className="text-right">On hand</Th>
                <Th className="text-right">Reorder at</Th>
                {user?.role === "admin" && <Th />}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {stock.data.items.map((s) => (
                <tr key={s.variant_id}>
                  <Td>
                    <Link href={`/products/${s.product_id}`} className="font-medium hover:text-brand-600">
                      {s.product_name}
                    </Link>
                  </Td>
                  <Td>{s.size}</Td>
                  <Td>{s.color}</Td>
                  <Td className="font-mono text-xs">{s.sku}</Td>
                  <Td>{s.category ?? "—"}</Td>
                  <Td className="text-right tabular-nums">{inr(s.selling_price)}</Td>
                  <Td className="text-right">
                    <Badge tone={s.quantity_on_hand === 0 ? "red" : s.low_stock ? "amber" : "green"}>
                      {s.quantity_on_hand}
                    </Badge>
                  </Td>
                  <Td className="text-right tabular-nums">{s.reorder_level}</Td>
                  {user?.role === "admin" && (
                    <Td className="text-right">
                      <Button variant="ghost" size="sm" onClick={() => setAdjusting(s)}>
                        <SlidersHorizontal size={14} /> Adjust
                      </Button>
                    </Td>
                  )}
                </tr>
              ))}
            </tbody>
          </Table>
          <Pagination offset={offset} limit={LIMIT} total={stock.data.total} onChange={setOffset} />
        </>
      )}
      <AdjustModal variant={adjusting} onClose={() => setAdjusting(null)} />
    </Card>
  );
}

const REASONS = ["Damaged", "Lost / theft", "Stock count correction", "Sample / display", "Returned to supplier"];

function AdjustModal({ variant, onClose }: { variant: StockLevel | null; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [delta, setDelta] = useState("");
  const [reason, setReason] = useState(REASONS[0]);
  const adjust = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/inventory/adjustments", {
          body: { variant_id: variant!.variant_id, qty_delta: Number(delta), reason },
        }),
      ),
    onSuccess: () => {
      toast.success("Stock adjusted");
      queryClient.invalidateQueries({ queryKey: ["stock"] });
      setDelta("");
      onClose();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <Modal open={!!variant} onClose={onClose} title="Adjust stock">
      {variant && (
        <form
          className="space-y-3"
          onSubmit={(e) => {
            e.preventDefault();
            adjust.mutate();
          }}
        >
          <p className="text-sm">
            {variant.product_name} · {variant.size} · {variant.color} — currently <b>{variant.quantity_on_hand}</b>
          </p>
          <Field label="Change" hint="Negative to remove, e.g. -2">
            <Input required inputMode="numeric" value={delta} onChange={(e) => setDelta(e.target.value)} autoFocus />
          </Field>
          <Field label="Reason">
            <Select value={reason} onChange={(e) => setReason(e.target.value)}>
              {REASONS.map((r) => (
                <option key={r}>{r}</option>
              ))}
            </Select>
          </Field>
          <div className="flex justify-end">
            <Button type="submit" disabled={!Number(delta) || adjust.isPending}>
              Save adjustment
            </Button>
          </div>
        </form>
      )}
    </Modal>
  );
}

function ReceiptsTab() {
  const [offset, setOffset] = useState(0);
  const [open, setOpen] = useState<number | null>(null);
  const receipts = useQuery({
    queryKey: ["receipts", offset],
    queryFn: async () => unwrap(await api.GET("/api/v1/inventory/receipts", { params: { query: { offset, limit: 25 } } })),
    placeholderData: keepPreviousData,
  });
  if (receipts.isLoading) return <Spinner />;
  if (!receipts.data?.items.length) return <Card><Empty>No goods received yet.</Empty></Card>;
  return (
    <Card>
      <Table>
        <thead>
          <tr>
            <Th>GRN</Th>
            <Th>Date</Th>
            <Th>Supplier</Th>
            <Th>Supplier invoice</Th>
            <Th>Received by</Th>
            <Th className="text-right">Units</Th>
            <Th className="text-right">Cost</Th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {receipts.data.items.map((r) => (
            <Fragment key={r.id}>
              <tr className="cursor-pointer hover:bg-slate-50" onClick={() => setOpen(open === r.id ? null : r.id)}>
                <Td className="font-medium text-brand-600">GRN-{r.id}</Td>
                <Td>{formatDateTime(r.received_at)}</Td>
                <Td>{r.supplier_name ?? "—"}</Td>
                <Td>{r.invoice_ref ?? "—"}</Td>
                <Td>{r.created_by_name}</Td>
                <Td className="text-right tabular-nums">{r.total_qty}</Td>
                <Td className="text-right tabular-nums">{inr(r.total_cost)}</Td>
              </tr>
              {open === r.id &&
                r.items.map((i) => (
                  <tr key={`${r.id}-${i.id}`} className="bg-slate-50 text-xs">
                    <Td />
                    <Td colSpan={3}>
                      {i.product_name} · {i.size} · {i.color} <span className="text-slate-500">({i.sku})</span>
                    </Td>
                    <Td />
                    <Td className="text-right">{i.qty}</Td>
                    <Td className="text-right">@ {inr(i.unit_cost)}</Td>
                  </tr>
                ))}
            </Fragment>
          ))}
        </tbody>
      </Table>
      <Pagination offset={offset} limit={25} total={receipts.data.total} onChange={setOffset} />
    </Card>
  );
}

function MovementsTab() {
  const [offset, setOffset] = useState(0);
  const [type, setType] = useState<Schemas["MovementType"] | "">("");
  const movements = useQuery({
    queryKey: ["movements", offset, type],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/inventory/movements", {
          params: { query: { offset, limit: 50, type: type || undefined } },
        }),
      ),
    placeholderData: keepPreviousData,
  });
  return (
    <Card>
      <div className="mb-4 w-48">
        <Select value={type} onChange={(e) => (setType(e.target.value as Schemas["MovementType"] | ""), setOffset(0))}>
          <option value="">All movements</option>
          <option value="purchase">Purchases</option>
          <option value="sale">Sales</option>
          <option value="return">Returns</option>
          <option value="adjustment">Adjustments</option>
        </Select>
      </div>
      {movements.isLoading ? (
        <Spinner />
      ) : !movements.data?.items.length ? (
        <Empty>No movements.</Empty>
      ) : (
        <>
          <Table>
            <thead>
              <tr>
                <Th>When</Th>
                <Th>Item</Th>
                <Th>Type</Th>
                <Th className="text-right">Change</Th>
                <Th>Reference</Th>
                <Th>By</Th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {movements.data.items.map((m) => (
                <tr key={m.id}>
                  <Td>{formatDateTime(m.created_at)}</Td>
                  <Td>
                    {m.product_name} <span className="font-mono text-xs text-slate-500">{m.sku}</span>
                  </Td>
                  <Td>
                    <Badge tone={m.type === "sale" ? "brand" : m.type === "adjustment" ? "amber" : "green"}>{m.type}</Badge>
                  </Td>
                  <Td className={clsx("text-right font-medium tabular-nums", m.qty_delta < 0 ? "text-red-600" : "text-green-700")}>
                    {m.qty_delta > 0 ? `+${m.qty_delta}` : m.qty_delta}
                  </Td>
                  <Td className="text-slate-500">
                    {m.ref_type === "sale" ? (
                      <Link href={`/sales/${m.ref_id}`} className="text-brand-600 hover:underline">
                        Sale #{m.ref_id}
                      </Link>
                    ) : m.ref_type === "stock_receipt" ? (
                      `GRN-${m.ref_id}`
                    ) : m.ref_type === "sale_return" ? (
                      `Return #${m.ref_id}`
                    ) : (
                      m.reason
                    )}
                  </Td>
                  <Td>{m.user_name ?? "—"}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
          <Pagination offset={offset} limit={50} total={movements.data.total} onChange={setOffset} />
        </>
      )}
    </Card>
  );
}
