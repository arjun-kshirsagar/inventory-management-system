"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Button, Card, Empty, Field, Input, Modal, PageHeader, Select, Table, Td, Th } from "@/components/ui";
import { VariantSearch } from "@/components/VariantSearch";
import { api, errorMessage, unwrap, type Schemas } from "@/lib/api/client";
import { useAuth } from "@/lib/auth";
import { inr, num } from "@/lib/format";
import { useSuppliers } from "@/lib/hooks/catalog";

type Variant = Schemas["VariantLookup"];
type Line = { variant: Variant; qty: string; unit_cost: string };

export default function ReceiveStockPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const suppliers = useSuppliers();
  const [supplierId, setSupplierId] = useState("");
  const [invoiceRef, setInvoiceRef] = useState("");
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<Line[]>([]);
  const [newSupplier, setNewSupplier] = useState(false);
  const [supplierForm, setSupplierForm] = useState({ name: "", gstin: "", phone: "" });

  function add(v: Variant) {
    setLines((prev) => {
      const existing = prev.find((l) => l.variant.id === v.id);
      if (existing) return prev.map((l) => (l === existing ? { ...l, qty: String(Number(l.qty) + 1) } : l));
      return [...prev, { variant: v, qty: "1", unit_cost: v.cost_price }];
    });
  }

  const update = (id: number, patch: Partial<Line>) =>
    setLines((prev) => prev.map((l) => (l.variant.id === id ? { ...l, ...patch } : l)));

  const save = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/inventory/receipts", {
          body: {
            supplier_id: supplierId ? Number(supplierId) : null,
            invoice_ref: invoiceRef || null,
            notes: notes || null,
            update_cost_price: true,
            items: lines.map((l) => ({ variant_id: l.variant.id, qty: Number(l.qty), unit_cost: l.unit_cost || null })),
          },
        }),
      ),
    onSuccess: (r) => {
      toast.success(`GRN-${r.id}: received ${r.total_qty} units`);
      queryClient.invalidateQueries({ queryKey: ["stock"] });
      queryClient.invalidateQueries({ queryKey: ["receipts"] });
      router.push("/inventory");
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  async function createSupplier(e: React.FormEvent) {
    e.preventDefault();
    const { data, error } = await api.POST("/api/v1/suppliers", {
      body: { name: supplierForm.name, gstin: supplierForm.gstin || null, phone: supplierForm.phone || null },
    });
    if (!data) return toast.error(errorMessage(error));
    await queryClient.invalidateQueries({ queryKey: ["suppliers"] });
    setSupplierId(String(data.id));
    setNewSupplier(false);
  }

  const totalQty = lines.reduce((s, l) => s + Number(l.qty || 0), 0);
  const totalCost = lines.reduce((s, l) => s + Number(l.qty || 0) * num(l.unit_cost), 0);
  const valid = lines.length > 0 && lines.every((l) => Number(l.qty) > 0);

  return (
    <>
      <PageHeader
        title="Receive stock"
        description="Record a goods received note (GRN). Stock increases as soon as you save."
        actions={
          <Button disabled={!valid || save.isPending} onClick={() => save.mutate()}>
            Save GRN · {totalQty} units
          </Button>
        }
      />
      <div className="grid gap-6 xl:grid-cols-[1fr_320px]">
        <Card title="Items">
          <div className="mb-4">
            <VariantSearch onSelect={add} placeholder="Scan barcode or search product to add" />
          </div>
          {lines.length === 0 ? (
            <Empty>Add the items you received.</Empty>
          ) : (
            <Table>
              <thead>
                <tr>
                  <Th>Item</Th>
                  <Th className="text-right">Current</Th>
                  <Th>Qty received</Th>
                  <Th>Unit cost (₹)</Th>
                  <Th className="text-right">Line cost</Th>
                  <Th />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {lines.map((l) => (
                  <tr key={l.variant.id}>
                    <Td>
                      <div className="font-medium">{l.variant.product_name}</div>
                      <div className="text-xs text-slate-500">
                        {l.variant.size} · {l.variant.color} · {l.variant.sku}
                      </div>
                    </Td>
                    <Td className="text-right tabular-nums">{l.variant.quantity_on_hand}</Td>
                    <Td>
                      <Input
                        className="w-20"
                        inputMode="numeric"
                        value={l.qty}
                        onChange={(e) => update(l.variant.id, { qty: e.target.value.replace(/\D/g, "") })}
                        aria-label="Quantity"
                      />
                    </Td>
                    <Td>
                      <Input
                        className="w-24"
                        inputMode="decimal"
                        value={l.unit_cost}
                        disabled={user?.role !== "admin"}
                        onChange={(e) => update(l.variant.id, { unit_cost: e.target.value.replace(/[^\d.]/g, "") })}
                        aria-label="Unit cost"
                      />
                    </Td>
                    <Td className="text-right tabular-nums">{inr(Number(l.qty || 0) * num(l.unit_cost))}</Td>
                    <Td>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setLines(lines.filter((x) => x !== l))}
                        aria-label="Remove"
                      >
                        <Trash2 size={16} />
                      </Button>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Card>
        <Card title="Supplier">
          <div className="space-y-3">
            <Field label="Supplier">
              <div className="flex gap-2">
                <Select value={supplierId} onChange={(e) => setSupplierId(e.target.value)}>
                  <option value="">—</option>
                  {suppliers.data?.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </Select>
                {user?.role === "admin" && (
                  <Button type="button" variant="secondary" onClick={() => setNewSupplier(true)}>
                    New
                  </Button>
                )}
              </div>
            </Field>
            <Field label="Supplier invoice no.">
              <Input value={invoiceRef} onChange={(e) => setInvoiceRef(e.target.value)} />
            </Field>
            <Field label="Notes">
              <Input value={notes} onChange={(e) => setNotes(e.target.value)} />
            </Field>
            <div className="border-t border-slate-200 pt-3 text-sm">
              <div className="flex justify-between">
                <span>Units</span>
                <span className="tabular-nums">{totalQty}</span>
              </div>
              <div className="flex justify-between font-medium">
                <span>Total cost</span>
                <span className="tabular-nums">{inr(totalCost)}</span>
              </div>
            </div>
          </div>
        </Card>
      </div>

      <Modal open={newSupplier} onClose={() => setNewSupplier(false)} title="New supplier">
        <form onSubmit={createSupplier} className="space-y-3">
          <Field label="Name">
            <Input required autoFocus value={supplierForm.name} onChange={(e) => setSupplierForm({ ...supplierForm, name: e.target.value })} />
          </Field>
          <Field label="GSTIN">
            <Input
              maxLength={15}
              value={supplierForm.gstin}
              onChange={(e) => setSupplierForm({ ...supplierForm, gstin: e.target.value.toUpperCase() })}
            />
          </Field>
          <Field label="Phone">
            <Input value={supplierForm.phone} onChange={(e) => setSupplierForm({ ...supplierForm, phone: e.target.value })} />
          </Field>
          <div className="flex justify-end">
            <Button type="submit">Save supplier</Button>
          </div>
        </form>
      </Modal>
    </>
  );
}
