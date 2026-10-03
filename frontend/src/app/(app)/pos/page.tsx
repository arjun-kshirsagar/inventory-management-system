"use client";

import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";
import { CheckCircle2, Minus, Plus, Printer, ScanBarcode, Trash2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { CustomerPicker } from "@/components/pos/CustomerPicker";
import { Badge, Button, Card, Empty, Input, Modal, Select } from "@/components/ui";
import { api, errorMessage, unwrap, type Schemas } from "@/lib/api/client";
import { openInvoice } from "@/lib/documents";
import { inr, num } from "@/lib/format";

type Variant = Schemas["VariantLookup"];
type Customer = Schemas["CustomerOut"];
type Sale = Schemas["SaleOut"];
type Method = Schemas["PaymentMethod"];
type Line = { variant: Variant; qty: number; discount: string };
type PaymentLine = { method: Method; amount: string; reference: string };

const METHODS: Method[] = ["cash", "card", "upi"];

export default function PosPage() {
  const searchRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Variant[]>([]);
  const [lines, setLines] = useState<Line[]>([]);
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [billDiscount, setBillDiscount] = useState("");
  const [paying, setPaying] = useState(false);
  const [payments, setPayments] = useState<PaymentLine[]>([]);
  const [completed, setCompleted] = useState<Sale | null>(null);
  const [idempotencyKey, setIdempotencyKey] = useState(() => crypto.randomUUID());

  const cartItems = useMemo(
    () => lines.map((l) => ({ variant_id: l.variant.id, qty: l.qty, discount: l.discount || "0" })),
    [lines],
  );

  const quote = useQuery({
    queryKey: ["quote", cartItems, customer?.id, billDiscount],
    queryFn: async () =>
      unwrap(
        await api.POST("/api/v1/sales/quote", {
          body: { items: cartItems, customer_id: customer?.id ?? null, bill_discount: billDiscount || "0" },
        }),
      ),
    enabled: cartItems.length > 0,
    placeholderData: keepPreviousData,
    retry: false,
  });

  useEffect(() => searchRef.current?.focus(), []);

  function addVariant(v: Variant) {
    const inCart = lines.find((l) => l.variant.id === v.id)?.qty ?? 0;
    if (inCart + 1 > v.quantity_on_hand) toast.warning(`Only ${v.quantity_on_hand} of ${v.sku} in stock`);
    setLines((prev) => {
      const existing = prev.find((l) => l.variant.id === v.id);
      if (existing) return prev.map((l) => (l === existing ? { ...l, qty: l.qty + 1 } : l));
      return [...prev, { variant: v, qty: 1, discount: "" }];
    });
    setResults([]);
    setQuery("");
    searchRef.current?.focus();
  }

  async function search(e: React.FormEvent) {
    e.preventDefault();
    const q = query.trim();
    if (!q) return;
    const { data } = await api.GET("/api/v1/variants/lookup", { params: { query: { q } } });
    if (!data || data.length === 0) {
      toast.error(`No product found for “${q}”`);
      setResults([]);
    } else if (data.length === 1) {
      addVariant(data[0]);
    } else {
      setResults(data);
    }
  }

  function updateLine(id: number, patch: Partial<Line>) {
    setLines((prev) => prev.map((l) => (l.variant.id === id ? { ...l, ...patch } : l)));
  }

  function resetSale() {
    setLines([]);
    setCustomer(null);
    setBillDiscount("");
    setPayments([]);
    setCompleted(null);
    setIdempotencyKey(crypto.randomUUID());
    searchRef.current?.focus();
  }

  const checkout = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/sales", {
          body: {
            items: cartItems,
            customer_id: customer?.id ?? null,
            bill_discount: billDiscount || "0",
            idempotency_key: idempotencyKey,
            payments: payments.map((p) => ({ method: p.method, amount: p.amount, reference: p.reference || null })),
          },
        }),
      ),
    onSuccess: (sale) => {
      setPaying(false);
      setCompleted(sale);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  const total = quote.data ? num(quote.data.grand_total) : 0;
  const paid = payments.reduce((s, p) => s + num(p.amount), 0);
  const stockProblems = lines.filter((l) => l.qty > l.variant.quantity_on_hand);

  function openPayment() {
    setPayments([{ method: "cash", amount: total.toFixed(2), reference: "" }]);
    setPaying(true);
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[1fr_380px]">
      <div className="space-y-4">
        <form onSubmit={search} className="relative">
          <ScanBarcode className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={20} />
          <Input
            ref={searchRef}
            className="h-12 pl-11 text-base"
            placeholder="Scan barcode, or type SKU / product name and press Enter"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Search products"
          />
          {results.length > 0 && (
            <ul className="absolute z-10 mt-1 max-h-80 w-full overflow-y-auto rounded-md border border-slate-200 bg-white shadow-lg">
              {results.map((v) => (
                <li key={v.id}>
                  <button
                    type="button"
                    onClick={() => addVariant(v)}
                    className="flex w-full items-center justify-between px-4 py-2 text-left text-sm hover:bg-brand-50"
                  >
                    <span>
                      <span className="font-medium">{v.product_name}</span>{" "}
                      <span className="text-slate-500">
                        {v.size} · {v.color} · {v.sku}
                      </span>
                    </span>
                    <span className="flex items-center gap-3">
                      <Badge tone={v.quantity_on_hand > 0 ? "green" : "red"}>{v.quantity_on_hand} in stock</Badge>
                      <span className="font-medium tabular-nums">{inr(v.selling_price)}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </form>

        <Card title={`Cart (${lines.reduce((s, l) => s + l.qty, 0)} items)`}>
          {lines.length === 0 ? (
            <Empty>Scan an item to start a sale.</Empty>
          ) : (
            <div className="divide-y divide-slate-100">
              {lines.map((l) => {
                const quoted = quote.data?.items.find((i) => i.variant_id === l.variant.id);
                return (
                  <div key={l.variant.id} className="flex flex-wrap items-center gap-4 py-3">
                    <div className="min-w-48 flex-1">
                      <div className="font-medium">{l.variant.product_name}</div>
                      <div className="text-xs text-slate-500">
                        {l.variant.size} · {l.variant.color} · {l.variant.sku} · {inr(l.variant.selling_price)}
                        {quoted && ` · GST ${num(quoted.gst_rate)}%`}
                      </div>
                      {l.qty > l.variant.quantity_on_hand && (
                        <div className="text-xs text-red-600">Only {l.variant.quantity_on_hand} in stock</div>
                      )}
                    </div>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="secondary"
                        size="sm"
                        aria-label="Decrease"
                        onClick={() => updateLine(l.variant.id, { qty: Math.max(1, l.qty - 1) })}
                      >
                        <Minus size={14} />
                      </Button>
                      <span className="w-8 text-center tabular-nums">{l.qty}</span>
                      <Button
                        variant="secondary"
                        size="sm"
                        aria-label="Increase"
                        onClick={() => updateLine(l.variant.id, { qty: l.qty + 1 })}
                      >
                        <Plus size={14} />
                      </Button>
                    </div>
                    <Input
                      className="w-24"
                      placeholder="Disc ₹"
                      inputMode="decimal"
                      value={l.discount}
                      onChange={(e) => updateLine(l.variant.id, { discount: e.target.value.replace(/[^\d.]/g, "") })}
                      aria-label="Line discount"
                    />
                    <div className="w-24 text-right font-medium tabular-nums">
                      {quoted ? inr(quoted.line_total) : inr(num(l.variant.selling_price) * l.qty)}
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      aria-label="Remove"
                      onClick={() => setLines((p) => p.filter((x) => x.variant.id !== l.variant.id))}
                    >
                      <Trash2 size={16} />
                    </Button>
                  </div>
                );
              })}
            </div>
          )}
        </Card>
      </div>

      <div className="space-y-4">
        <Card title="Customer">
          <CustomerPicker customer={customer} onChange={setCustomer} />
        </Card>
        <Card title="Bill">
          <dl className="space-y-2 text-sm">
            <Row label="Gross" value={inr(quote.data?.subtotal)} />
            <div className="flex items-center justify-between">
              <dt className="text-slate-600">Bill discount</dt>
              <Input
                className="w-28 text-right"
                inputMode="decimal"
                placeholder="0"
                value={billDiscount}
                onChange={(e) => setBillDiscount(e.target.value.replace(/[^\d.]/g, ""))}
              />
            </div>
            <Row label="Total discount" value={`- ${inr(quote.data?.discount)}`} />
            <Row label="Taxable value" value={inr(quote.data?.taxable_value)} />
            {num(quote.data?.igst) > 0 ? (
              <Row label="IGST" value={inr(quote.data?.igst)} />
            ) : (
              <>
                <Row label="CGST" value={inr(quote.data?.cgst)} />
                <Row label="SGST" value={inr(quote.data?.sgst)} />
              </>
            )}
            <Row label="Round off" value={inr(quote.data?.round_off)} />
            <div className="flex items-center justify-between border-t border-slate-200 pt-3 text-lg font-semibold">
              <dt>Total</dt>
              <dd className="tabular-nums">{inr(quote.data?.grand_total)}</dd>
            </div>
          </dl>
          {quote.error && <p className="mt-2 text-sm text-red-600">{errorMessage(quote.error)}</p>}
          <Button
            size="lg"
            className="mt-4 w-full"
            disabled={lines.length === 0 || !quote.data || quote.isFetching || stockProblems.length > 0}
            onClick={openPayment}
          >
            Charge {quote.data ? inr(quote.data.grand_total) : ""}
          </Button>
          {lines.length > 0 && (
            <Button variant="ghost" className="mt-2 w-full" onClick={resetSale}>
              Clear sale
            </Button>
          )}
        </Card>
      </div>

      <Modal open={paying} onClose={() => setPaying(false)} title={`Payment · ${inr(total)}`}>
        <div className="space-y-3">
          {payments.map((p, i) => (
            <div key={i} className="flex gap-2">
              <Select
                className="w-28"
                value={p.method}
                onChange={(e) =>
                  setPayments(payments.map((x, j) => (j === i ? { ...x, method: e.target.value as Method } : x)))
                }
              >
                {METHODS.map((m) => (
                  <option key={m} value={m}>
                    {m.toUpperCase()}
                  </option>
                ))}
              </Select>
              <Input
                inputMode="decimal"
                value={p.amount}
                onChange={(e) =>
                  setPayments(payments.map((x, j) => (j === i ? { ...x, amount: e.target.value.replace(/[^\d.]/g, "") } : x)))
                }
                aria-label="Amount"
              />
              {p.method !== "cash" && (
                <Input
                  placeholder="Txn ref"
                  value={p.reference}
                  onChange={(e) => setPayments(payments.map((x, j) => (j === i ? { ...x, reference: e.target.value } : x)))}
                />
              )}
              {payments.length > 1 && (
                <Button variant="ghost" onClick={() => setPayments(payments.filter((_, j) => j !== i))} aria-label="Remove payment">
                  <Trash2 size={16} />
                </Button>
              )}
            </div>
          ))}
          <Button
            variant="secondary"
            size="sm"
            onClick={() =>
              setPayments([...payments, { method: "upi", amount: Math.max(0, total - paid).toFixed(2), reference: "" }])
            }
          >
            <Plus size={14} /> Split payment
          </Button>
          <div className="flex justify-between text-sm">
            <span>Paid {inr(paid)}</span>
            <span className={Math.abs(paid - total) < 0.005 ? "text-green-700" : "text-red-600"}>
              {paid < total ? `Due ${inr(total - paid)}` : paid > total ? `Over by ${inr(paid - total)}` : "Balanced"}
            </span>
          </div>
          <Button
            size="lg"
            className="w-full"
            disabled={Math.abs(paid - total) >= 0.005 || checkout.isPending}
            onClick={() => checkout.mutate()}
          >
            {checkout.isPending ? "Completing…" : "Complete sale"}
          </Button>
        </div>
      </Modal>

      <Modal open={!!completed} onClose={resetSale} title="Sale complete">
        {completed && (
          <div className="space-y-4 text-center">
            <CheckCircle2 className="mx-auto text-green-600" size={48} />
            <div>
              <div className="text-2xl font-semibold">{inr(completed.grand_total)}</div>
              <div className="text-sm text-slate-500">Invoice {completed.invoice_no}</div>
            </div>
            <div className="flex justify-center gap-2">
              <Button variant="secondary" onClick={() => openInvoice(completed.id, "a4")}>
                <Printer size={16} /> A4 invoice
              </Button>
              <Button variant="secondary" onClick={() => openInvoice(completed.id, "thermal")}>
                <Printer size={16} /> Receipt
              </Button>
            </div>
            <Button className="w-full" onClick={resetSale} autoFocus>
              New sale
            </Button>
          </div>
        )}
      </Modal>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <dt className="text-slate-600">{label}</dt>
      <dd className="tabular-nums">{value}</dd>
    </div>
  );
}
