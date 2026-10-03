"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Button, Field, Input, Modal } from "@/components/ui";
import { api, errorMessage, type Schemas } from "@/lib/api/client";

type Customer = Schemas["CustomerOut"];

export function CustomerPicker({
  customer,
  onChange,
}: {
  customer: Customer | null;
  onChange: (c: Customer | null) => void;
}) {
  const [phone, setPhone] = useState("");
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ name: "", email: "", gstin: "", state_code: "", address: "" });

  async function lookup(e: React.FormEvent) {
    e.preventDefault();
    if (!phone) return;
    const { data, response } = await api.GET("/api/v1/customers/by-phone/{phone}", {
      params: { path: { phone } },
    });
    if (data) onChange(data);
    else if (response.status === 404) setCreating(true);
  }

  async function create(e: React.FormEvent) {
    e.preventDefault();
    const { data, error } = await api.POST("/api/v1/customers", {
      body: {
        phone,
        name: form.name,
        email: form.email || null,
        gstin: form.gstin || null,
        state_code: form.state_code || (form.gstin ? form.gstin.slice(0, 2) : null),
        address: form.address || null,
      },
    });
    if (!data) return toast.error(errorMessage(error));
    onChange(data);
    setCreating(false);
  }

  if (customer) {
    return (
      <div className="flex items-center justify-between rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
        <div>
          <div className="font-medium">{customer.name}</div>
          <div className="text-xs text-slate-500">
            {customer.phone}
            {customer.gstin && ` · GSTIN ${customer.gstin}`}
            {customer.state_code && ` · State ${customer.state_code}`}
          </div>
        </div>
        <Button variant="ghost" size="sm" onClick={() => onChange(null)}>
          Remove
        </Button>
      </div>
    );
  }

  return (
    <>
      <form onSubmit={lookup} className="flex gap-2">
        <Input
          placeholder="Customer phone (optional)"
          inputMode="tel"
          value={phone}
          onChange={(e) => setPhone(e.target.value.replace(/[^\d+]/g, ""))}
        />
        <Button type="submit" variant="secondary">
          Find
        </Button>
      </form>
      <Modal open={creating} onClose={() => setCreating(false)} title={`New customer · ${phone}`}>
        <form onSubmit={create} className="space-y-3">
          <Field label="Name">
            <Input required autoFocus value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </Field>
          <Field label="Email">
            <Input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="GSTIN (B2B)">
              <Input
                value={form.gstin}
                maxLength={15}
                onChange={(e) => setForm({ ...form, gstin: e.target.value.toUpperCase() })}
              />
            </Field>
            <Field label="State code" hint="Blank = same state as store">
              <Input
                value={form.state_code}
                maxLength={2}
                placeholder="27"
                onChange={(e) => setForm({ ...form, state_code: e.target.value.replace(/\D/g, "") })}
              />
            </Field>
          </div>
          <Field label="Address">
            <Input value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} />
          </Field>
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="secondary" onClick={() => setCreating(false)}>
              Cancel
            </Button>
            <Button type="submit">Save customer</Button>
          </div>
        </form>
      </Modal>
    </>
  );
}
