"use client";

import { Field, Input } from "@/components/ui";

export type MatrixValues = {
  sizes: string;
  colors: string;
  mrp: string;
  selling_price: string;
  cost_price: string;
  reorder_level: string;
};

export const SIZE_PRESETS: Record<string, string> = {
  Apparel: "XS, S, M, L, XL, XXL",
  Waist: "28, 30, 32, 34, 36, 38",
  Kids: "2-3Y, 4-5Y, 6-7Y, 8-9Y",
  "Free size": "Free",
};

export function splitList(value: string) {
  return value
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

export function toMatrixBody(m: MatrixValues) {
  return {
    sizes: splitList(m.sizes),
    colors: splitList(m.colors),
    mrp: m.mrp,
    selling_price: m.selling_price || m.mrp,
    cost_price: m.cost_price || "0",
    reorder_level: Number(m.reorder_level || 5),
  };
}

export function VariantMatrixFields({
  value,
  onChange,
}: {
  value: MatrixValues;
  onChange: (v: MatrixValues) => void;
}) {
  const set = (k: keyof MatrixValues) => (e: React.ChangeEvent<HTMLInputElement>) =>
    onChange({ ...value, [k]: e.target.value });
  const count = splitList(value.sizes).length * splitList(value.colors).length;
  return (
    <div className="space-y-3">
      <Field label="Sizes" hint="Comma-separated">
        <Input value={value.sizes} onChange={set("sizes")} placeholder="S, M, L, XL" />
      </Field>
      <div className="flex flex-wrap gap-2">
        {Object.entries(SIZE_PRESETS).map(([label, sizes]) => (
          <button
            key={label}
            type="button"
            className="rounded-full border border-slate-300 px-3 py-1 text-xs text-slate-600 hover:bg-slate-100"
            onClick={() => onChange({ ...value, sizes })}
          >
            {label}
          </button>
        ))}
      </div>
      <Field label="Colours" hint="Comma-separated">
        <Input value={value.colors} onChange={set("colors")} placeholder="Black, White, Navy" />
      </Field>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Field label="MRP (₹)">
          <Input inputMode="decimal" required value={value.mrp} onChange={set("mrp")} />
        </Field>
        <Field label="Selling price (₹)" hint="GST inclusive">
          <Input inputMode="decimal" value={value.selling_price} onChange={set("selling_price")} placeholder={value.mrp} />
        </Field>
        <Field label="Cost price (₹)">
          <Input inputMode="decimal" value={value.cost_price} onChange={set("cost_price")} />
        </Field>
        <Field label="Reorder at">
          <Input inputMode="numeric" value={value.reorder_level} onChange={set("reorder_level")} />
        </Field>
      </div>
      <p className="text-sm text-slate-500">
        Will create <b>{count}</b> variant{count === 1 ? "" : "s"}, each with its own SKU and barcode.
      </p>
    </div>
  );
}
