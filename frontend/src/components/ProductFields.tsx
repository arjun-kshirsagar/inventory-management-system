"use client";

import { QuickCreate } from "@/components/QuickCreate";
import { Field, Input, Select, Textarea } from "@/components/ui";
import { useBrands, useCategories } from "@/lib/hooks/catalog";

export type ProductValues = {
  name: string;
  category_id: string;
  brand_id: string;
  hsn_code: string;
  gender: string;
  material: string;
  description: string;
};

export const emptyProduct: ProductValues = {
  name: "",
  category_id: "",
  brand_id: "",
  hsn_code: "",
  gender: "",
  material: "",
  description: "",
};

export function toProductBody(v: ProductValues) {
  return {
    name: v.name,
    hsn_code: v.hsn_code,
    category_id: v.category_id ? Number(v.category_id) : null,
    brand_id: v.brand_id ? Number(v.brand_id) : null,
    gender: v.gender || null,
    material: v.material || null,
    description: v.description || null,
  };
}

const HSN_HINTS = "61xx knitted apparel (e.g. 6109 T-shirts), 62xx woven (6203 men's suits/trousers, 6204 women's, 6205 shirts)";

export function ProductFields({ value, onChange }: { value: ProductValues; onChange: (v: ProductValues) => void }) {
  const categories = useCategories();
  const brands = useBrands();
  const set =
    (k: keyof ProductValues) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
      onChange({ ...value, [k]: e.target.value });

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <Field label="Product name" className="sm:col-span-2">
        <Input required value={value.name} onChange={set("name")} placeholder="Slim Fit Oxford Shirt" />
      </Field>
      <Field label="Category">
        <div className="flex gap-2">
          <Select value={value.category_id} onChange={set("category_id")}>
            <option value="">—</option>
            {categories.data?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </Select>
          <QuickCreate kind="categories" onCreated={(id) => onChange({ ...value, category_id: String(id) })} />
        </div>
      </Field>
      <Field label="Brand">
        <div className="flex gap-2">
          <Select value={value.brand_id} onChange={set("brand_id")}>
            <option value="">—</option>
            {brands.data?.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </Select>
          <QuickCreate kind="brands" onCreated={(id) => onChange({ ...value, brand_id: String(id) })} />
        </div>
      </Field>
      <Field label="HSN code" hint={HSN_HINTS}>
        <Input required pattern="\d{4,8}" value={value.hsn_code} onChange={set("hsn_code")} placeholder="6205" />
      </Field>
      <div className="grid grid-cols-2 gap-4">
        <Field label="Gender">
          <Select value={value.gender} onChange={set("gender")}>
            <option value="">—</option>
            {["Men", "Women", "Unisex", "Boys", "Girls"].map((g) => (
              <option key={g}>{g}</option>
            ))}
          </Select>
        </Field>
        <Field label="Material">
          <Input value={value.material} onChange={set("material")} placeholder="Cotton" />
        </Field>
      </div>
      <Field label="Description" className="sm:col-span-2">
        <Textarea rows={2} value={value.description} onChange={set("description")} />
      </Field>
    </div>
  );
}
