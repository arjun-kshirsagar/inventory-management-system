"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Printer, Undo2 } from "lucide-react";
import { useParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { SaleStatusBadge } from "@/components/SaleStatusBadge";
import { Button, Card, Field, Input, Modal, PageHeader, Spinner, Table, Td, Th } from "@/components/ui";
import { api, errorMessage, unwrap } from "@/lib/api/client";
import { openCreditNote, openInvoice } from "@/lib/documents";
import { formatDateTime, inr, num } from "@/lib/format";

export default function SaleDetailPage() {
  const { id } = useParams<{ id: string }>();
  const saleId = Number(id);
  const queryClient = useQueryClient();
  const [returning, setReturning] = useState(false);
  const [returnQty, setReturnQty] = useState<Record<number, number>>({});
  const [restock, setRestock] = useState<Record<number, boolean>>({});
  const [reason, setReason] = useState("");

  const sale = useQuery({
    queryKey: ["sale", saleId],
    queryFn: async () => unwrap(await api.GET("/api/v1/sales/{sale_id}", { params: { path: { sale_id: saleId } } })),
  });

  const createReturn = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/sales/{sale_id}/returns", {
          params: { path: { sale_id: saleId } },
          body: {
            reason: reason || null,
            items: Object.entries(returnQty)
              .filter(([, qty]) => qty > 0)
              .map(([itemId, qty]) => ({
                sale_item_id: Number(itemId),
                qty,
                restock: restock[Number(itemId)] ?? true,
              })),
          },
        }),
      ),
    onSuccess: (ret) => {
      toast.success(`Credit note ${ret.credit_note_no} · refund ${inr(ret.refund_amount)}`);
      setReturning(false);
      setReturnQty({});
      setReason("");
      queryClient.invalidateQueries({ queryKey: ["sale", saleId] });
      queryClient.invalidateQueries({ queryKey: ["sales"] });
      openCreditNote(ret.id);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (sale.isLoading || !sale.data) return <Spinner />;
  const s = sale.data;
  const interstate = num(s.igst) > 0;
  const returnable = s.items.some((i) => i.qty > i.returned_qty);

  return (
    <>
      <PageHeader
        title={s.invoice_no}
        description={`${formatDateTime(s.created_at)} · by ${s.cashier_name}`}
        actions={
          <>
            <Button variant="secondary" onClick={() => openInvoice(s.id, "a4")}>
              <Printer size={16} /> A4 invoice
            </Button>
            <Button variant="secondary" onClick={() => openInvoice(s.id, "thermal")}>
              <Printer size={16} /> Receipt
            </Button>
            {returnable && (
              <Button variant="danger" onClick={() => setReturning(true)}>
                <Undo2 size={16} /> Return / exchange
              </Button>
            )}
          </>
        }
      />
      <div className="grid gap-6 lg:grid-cols-3">
        <Card title="Items" className="lg:col-span-2">
          <Table>
            <thead>
              <tr>
                <Th>Item</Th>
                <Th>HSN</Th>
                <Th className="text-right">Qty</Th>
                <Th className="text-right">Price</Th>
                <Th className="text-right">Disc.</Th>
                <Th className="text-right">GST</Th>
                <Th className="text-right">Amount</Th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {s.items.map((i) => (
                <tr key={i.id}>
                  <Td>
                    <div className="font-medium">{i.product_name}</div>
                    <div className="text-xs text-slate-500">
                      {i.size} · {i.color} · {i.sku}
                      {i.returned_qty > 0 && <span className="text-red-600"> · {i.returned_qty} returned</span>}
                    </div>
                  </Td>
                  <Td>{i.hsn_code}</Td>
                  <Td className="text-right tabular-nums">{i.qty}</Td>
                  <Td className="text-right tabular-nums">{inr(i.unit_price)}</Td>
                  <Td className="text-right tabular-nums">{inr(i.discount)}</Td>
                  <Td className="text-right tabular-nums">{num(i.gst_rate)}%</Td>
                  <Td className="text-right font-medium tabular-nums">{inr(i.line_total)}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>
        <div className="space-y-6">
          <Card title="Summary" actions={<SaleStatusBadge status={s.status} />}>
            <dl className="space-y-1 text-sm">
              {[
                ["Gross", inr(s.subtotal)],
                ["Discount", `- ${inr(s.discount)}`],
                ["Taxable value", inr(s.taxable_value)],
                ...(interstate ? [["IGST", inr(s.igst)]] : [["CGST", inr(s.cgst)], ["SGST", inr(s.sgst)]]),
                ["Round off", inr(s.round_off)],
              ].map(([k, v]) => (
                <div key={k} className="flex justify-between">
                  <dt className="text-slate-600">{k}</dt>
                  <dd className="tabular-nums">{v}</dd>
                </div>
              ))}
              <div className="flex justify-between border-t border-slate-200 pt-2 text-base font-semibold">
                <dt>Total</dt>
                <dd className="tabular-nums">{inr(s.grand_total)}</dd>
              </div>
            </dl>
            <div className="mt-3 space-y-1 border-t border-slate-200 pt-3 text-sm">
              {s.payments.map((p, i) => (
                <div key={i} className="flex justify-between text-slate-600">
                  <span className="uppercase">
                    {p.method}
                    {p.reference && ` · ${p.reference}`}
                  </span>
                  <span className="tabular-nums">{inr(p.amount)}</span>
                </div>
              ))}
            </div>
          </Card>
          <Card title="Customer">
            {s.customer ? (
              <div className="text-sm">
                <div className="font-medium">{s.customer.name}</div>
                <div className="text-slate-500">{s.customer.phone}</div>
                {s.customer.gstin && <div className="text-slate-500">GSTIN {s.customer.gstin}</div>}
                <div className="text-slate-500">Place of supply: {s.place_of_supply}</div>
              </div>
            ) : (
              <p className="text-sm text-slate-500">Walk-in customer</p>
            )}
          </Card>
          {s.returns.length > 0 && (
            <Card title="Returns">
              <ul className="space-y-2 text-sm">
                {s.returns.map((r) => (
                  <li key={r.id} className="flex items-center justify-between">
                    <div>
                      <button className="font-medium text-brand-600 hover:underline" onClick={() => openCreditNote(r.id)}>
                        {r.credit_note_no}
                      </button>
                      <div className="text-xs text-slate-500">{formatDateTime(r.created_at)}</div>
                    </div>
                    <span className="tabular-nums">{inr(r.refund_amount)}</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>
      </div>

      <Modal open={returning} onClose={() => setReturning(false)} title="Return items" wide>
        <p className="mb-3 text-sm text-slate-600">
          A credit note is issued for the returned amount. For an exchange, process the return and then ring up the new
          item at the POS.
        </p>
        <Table>
          <thead>
            <tr>
              <Th>Item</Th>
              <Th className="text-right">Returnable</Th>
              <Th>Qty to return</Th>
              <Th>Back to stock</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {s.items
              .filter((i) => i.qty > i.returned_qty)
              .map((i) => (
                <tr key={i.id}>
                  <Td>
                    {i.product_name}{" "}
                    <span className="text-slate-500">
                      ({i.size}/{i.color})
                    </span>
                  </Td>
                  <Td className="text-right">{i.qty - i.returned_qty}</Td>
                  <Td>
                    <Input
                      type="number"
                      min={0}
                      max={i.qty - i.returned_qty}
                      className="w-20"
                      value={returnQty[i.id] ?? 0}
                      onChange={(e) =>
                        setReturnQty({
                          ...returnQty,
                          [i.id]: Math.min(i.qty - i.returned_qty, Math.max(0, Number(e.target.value))),
                        })
                      }
                    />
                  </Td>
                  <Td>
                    <input
                      type="checkbox"
                      className="h-4 w-4 accent-brand-600"
                      checked={restock[i.id] ?? true}
                      onChange={(e) => setRestock({ ...restock, [i.id]: e.target.checked })}
                      aria-label="Restock"
                    />
                  </Td>
                </tr>
              ))}
          </tbody>
        </Table>
        <Field label="Reason" className="mt-4">
          <Input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. size exchange, defect" />
        </Field>
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setReturning(false)}>
            Cancel
          </Button>
          <Button
            variant="danger"
            disabled={!Object.values(returnQty).some((q) => q > 0) || createReturn.isPending}
            onClick={() => createReturn.mutate()}
          >
            Issue credit note
          </Button>
        </div>
      </Modal>
    </>
  );
}
