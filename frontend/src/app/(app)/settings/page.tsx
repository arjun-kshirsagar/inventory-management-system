"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Badge, Button, Card, Field, Input, Modal, PageHeader, Select, Spinner, Table, Td, Textarea, Th } from "@/components/ui";
import { api, errorMessage, unwrap, type Schemas } from "@/lib/api/client";
import { useAuth } from "@/lib/auth";
import { formatDate, inr, num } from "@/lib/format";

export default function SettingsPage() {
  return (
    <>
      <PageHeader title="Settings" />
      <div className="space-y-6">
        <StoreCard />
        <TaxSlabsCard />
        <UsersCard />
      </div>
    </>
  );
}

type Store = Schemas["StoreSettingsIn"];

function StoreCard() {
  const queryClient = useQueryClient();
  const store = useQuery({
    queryKey: ["store"],
    queryFn: async () => unwrap(await api.GET("/api/v1/settings/store")),
  });
  const [edits, setForm] = useState<Store | null>(null);
  const form = edits ?? store.data ?? null;

  const save = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.PUT("/api/v1/settings/store", {
          body: { ...form!, gstin: form!.gstin || null, phone: form!.phone || null, email: form!.email || null },
        }),
      ),
    onSuccess: () => {
      toast.success("Store details saved");
      queryClient.invalidateQueries({ queryKey: ["store"] });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (!form) return <Spinner />;
  const set = (k: keyof Store) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm({ ...form, [k]: e.target.value });

  return (
    <Card
      title="Store details (printed on invoices)"
      actions={
        <Button size="sm" onClick={() => save.mutate()} disabled={save.isPending}>
          Save
        </Button>
      }
    >
      <div className="grid gap-4 md:grid-cols-3">
        <Field label="Store name">
          <Input value={form.name} onChange={set("name")} />
        </Field>
        <Field label="GSTIN">
          <Input value={form.gstin ?? ""} maxLength={15} onChange={(e) => setForm({ ...form, gstin: e.target.value.toUpperCase() })} />
        </Field>
        <Field label="Phone">
          <Input value={form.phone ?? ""} onChange={set("phone")} />
        </Field>
        <Field label="Address" className="md:col-span-2">
          <Input value={form.address} onChange={set("address")} />
        </Field>
        <Field label="Email">
          <Input value={form.email ?? ""} onChange={set("email")} />
        </Field>
        <Field label="State" hint="Sales to customers in other states are charged IGST">
          <Input value={form.state_name} onChange={set("state_name")} />
        </Field>
        <Field label="State code" hint="First two digits of your GSTIN">
          <Input value={form.state_code} maxLength={2} onChange={set("state_code")} />
        </Field>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Invoice prefix">
            <Input value={form.invoice_prefix} onChange={set("invoice_prefix")} />
          </Field>
          <Field label="Credit note prefix">
            <Input value={form.credit_note_prefix} onChange={set("credit_note_prefix")} />
          </Field>
        </div>
        <Field label="Invoice footer / terms" className="md:col-span-3">
          <Textarea rows={2} value={form.footer_terms ?? ""} onChange={set("footer_terms")} />
        </Field>
      </div>
    </Card>
  );
}

type SlabForm = { name: string; hsn_prefix: string; price_threshold: string; rate_below: string; rate_above: string; effective_from: string };

function TaxSlabsCard() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<SlabForm | null>(null);
  const slabs = useQuery({
    queryKey: ["tax-slabs"],
    queryFn: async () => unwrap(await api.GET("/api/v1/settings/tax-slabs")),
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["tax-slabs"] });

  const create = useMutation({
    mutationFn: async (f: SlabForm) =>
      unwrap(
        await api.POST("/api/v1/settings/tax-slabs", {
          body: {
            name: f.name,
            hsn_prefix: f.hsn_prefix,
            price_threshold: f.price_threshold || null,
            rate_below: f.rate_below,
            rate_above: f.rate_above || f.rate_below,
            effective_from: f.effective_from,
          },
        }),
      ),
    onSuccess: () => {
      setForm(null);
      refresh();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  async function remove(id: number) {
    if (!window.confirm("Delete this GST rule? Past invoices are not affected.")) return;
    await api.DELETE("/api/v1/settings/tax-slabs/{slab_id}", { params: { path: { slab_id: id } } });
    refresh();
  }

  return (
    <Card
      title="GST rates"
      actions={
        <Button
          size="sm"
          onClick={() =>
            setForm({ name: "", hsn_prefix: "", price_threshold: "", rate_below: "", rate_above: "", effective_from: new Date().toISOString().slice(0, 10) })
          }
        >
          <Plus size={14} /> Add rule
        </Button>
      }
    >
      <p className="mb-3 text-sm text-slate-500">
        Each product&apos;s HSN code is matched to the longest prefix below. With a price threshold, the lower rate applies when
        the per-piece value (excluding GST) is at or below the threshold. To change a rate, add a new rule with a later
        &ldquo;effective from&rdquo; date so past invoices keep their rates.
      </p>
      {slabs.isLoading ? (
        <Spinner />
      ) : (
        <Table>
          <thead>
            <tr>
              <Th>Rule</Th>
              <Th>HSN prefix</Th>
              <Th className="text-right">Threshold / piece</Th>
              <Th className="text-right">Rate ≤ threshold</Th>
              <Th className="text-right">Rate above</Th>
              <Th>Effective from</Th>
              <Th />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {slabs.data?.map((s) => (
              <tr key={s.id}>
                <Td className="font-medium">{s.name}</Td>
                <Td>{s.hsn_prefix || <Badge>all</Badge>}</Td>
                <Td className="text-right">{s.price_threshold ? inr(s.price_threshold) : "—"}</Td>
                <Td className="text-right">{num(s.rate_below)}%</Td>
                <Td className="text-right">{s.price_threshold ? `${num(s.rate_above)}%` : "—"}</Td>
                <Td>{formatDate(s.effective_from)}</Td>
                <Td className="text-right">
                  <Button variant="ghost" size="sm" onClick={() => remove(s.id)} aria-label="Delete rule">
                    <Trash2 size={14} />
                  </Button>
                </Td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
      <Modal open={!!form} onClose={() => setForm(null)} title="Add GST rule">
        {form && (
          <form
            className="grid grid-cols-2 gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              create.mutate(form);
            }}
          >
            <Field label="Name" className="col-span-2">
              <Input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Apparel - woven" />
            </Field>
            <Field label="HSN prefix" hint="Blank = default for everything">
              <Input value={form.hsn_prefix} onChange={(e) => setForm({ ...form, hsn_prefix: e.target.value.replace(/\D/g, "") })} />
            </Field>
            <Field label="Effective from">
              <Input type="date" required value={form.effective_from} onChange={(e) => setForm({ ...form, effective_from: e.target.value })} />
            </Field>
            <Field label="Price threshold (₹)" hint="Optional">
              <Input inputMode="decimal" value={form.price_threshold} onChange={(e) => setForm({ ...form, price_threshold: e.target.value })} />
            </Field>
            <div />
            <Field label="Rate (%)" hint={form.price_threshold ? "At or below threshold" : undefined}>
              <Input required inputMode="decimal" value={form.rate_below} onChange={(e) => setForm({ ...form, rate_below: e.target.value })} />
            </Field>
            {form.price_threshold && (
              <Field label="Rate above threshold (%)">
                <Input required inputMode="decimal" value={form.rate_above} onChange={(e) => setForm({ ...form, rate_above: e.target.value })} />
              </Field>
            )}
            <div className="col-span-2 flex justify-end">
              <Button type="submit" disabled={create.isPending}>
                Save rule
              </Button>
            </div>
          </form>
        )}
      </Modal>
    </Card>
  );
}

function UsersCard() {
  const { user: me } = useAuth();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<{ name: string; email: string; password: string; role: Schemas["Role"] } | null>(null);
  const users = useQuery({ queryKey: ["users"], queryFn: async () => unwrap(await api.GET("/api/v1/users")) });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["users"] });

  const create = useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/v1/users", { body: form! })),
    onSuccess: () => {
      setForm(null);
      refresh();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  async function update(id: number, body: Schemas["UserUpdate"]) {
    const { error } = await api.PATCH("/api/v1/users/{user_id}", { params: { path: { user_id: id } }, body });
    if (error) toast.error(errorMessage(error));
    else {
      toast.success("User updated");
      refresh();
    }
  }

  return (
    <Card
      title="Users"
      actions={
        <Button size="sm" onClick={() => setForm({ name: "", email: "", password: "", role: "cashier" })}>
          <Plus size={14} /> Add user
        </Button>
      }
    >
      <Table>
        <thead>
          <tr>
            <Th>Name</Th>
            <Th>Email</Th>
            <Th>Role</Th>
            <Th>Status</Th>
            <Th />
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {users.data?.map((u) => (
            <tr key={u.id}>
              <Td className="font-medium">{u.name}</Td>
              <Td>{u.email}</Td>
              <Td>
                <Select
                  className="w-32"
                  value={u.role}
                  disabled={u.id === me?.id}
                  onChange={(e) => update(u.id, { role: e.target.value as Schemas["Role"] })}
                >
                  <option value="admin">Admin</option>
                  <option value="cashier">Cashier</option>
                </Select>
              </Td>
              <Td>{u.is_active ? <Badge tone="green">active</Badge> : <Badge tone="red">disabled</Badge>}</Td>
              <Td className="space-x-2 text-right">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    const password = window.prompt(`New password for ${u.name} (min 6 characters)`);
                    if (password) update(u.id, { password });
                  }}
                >
                  Reset password
                </Button>
                {u.id !== me?.id && (
                  <Button variant="ghost" size="sm" onClick={() => update(u.id, { is_active: !u.is_active })}>
                    {u.is_active ? "Disable" : "Enable"}
                  </Button>
                )}
              </Td>
            </tr>
          ))}
        </tbody>
      </Table>
      <Modal open={!!form} onClose={() => setForm(null)} title="Add user">
        {form && (
          <form
            className="space-y-3"
            onSubmit={(e) => {
              e.preventDefault();
              create.mutate();
            }}
          >
            <Field label="Name">
              <Input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </Field>
            <Field label="Email">
              <Input type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
            </Field>
            <Field label="Password">
              <Input type="password" minLength={6} required value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
            </Field>
            <Field label="Role">
              <Select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as Schemas["Role"] })}>
                <option value="cashier">Cashier — POS, sales, receive stock</option>
                <option value="admin">Admin — everything incl. reports & settings</option>
              </Select>
            </Field>
            <div className="flex justify-end">
              <Button type="submit" disabled={create.isPending}>
                Create user
              </Button>
            </div>
          </form>
        )}
      </Modal>
    </Card>
  );
}
