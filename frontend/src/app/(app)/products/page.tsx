"use client";

import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Plus, Upload } from "lucide-react";
import Link from "next/link";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { Badge, Button, Card, Empty, Input, PageHeader, Pagination, Select, Spinner, Table, Td, Th } from "@/components/ui";
import { api, downloadBlob, errorMessage, fetchFile, unwrap } from "@/lib/api/client";
import { useAuth } from "@/lib/auth";
import { inr, num } from "@/lib/format";
import { useBrands, useCategories } from "@/lib/hooks/catalog";

const LIMIT = 25;

export default function ProductsPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const queryClient = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [q, setQ] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [brandId, setBrandId] = useState("");
  const [offset, setOffset] = useState(0);
  const categories = useCategories();
  const brands = useBrands();

  const products = useQuery({
    queryKey: ["products", q, categoryId, brandId, offset],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/products", {
          params: {
            query: {
              q: q || undefined,
              category_id: categoryId ? Number(categoryId) : undefined,
              brand_id: brandId ? Number(brandId) : undefined,
              offset,
              limit: LIMIT,
            },
          },
        }),
      ),
    placeholderData: keepPreviousData,
  });

  async function importCsv(file: File) {
    const body = new FormData();
    body.append("file", file);
    const { data, error } = await api.POST("/api/v1/products/import", {
      body: body as never,
      bodySerializer: (b) => b as unknown as FormData,
    });
    if (fileRef.current) fileRef.current.value = "";
    if (!data) return toast.error(errorMessage(error));
    if (data.errors.length) {
      toast.error(`Import rejected:\n${data.errors.slice(0, 5).join("\n")}`, { duration: 10_000 });
      return;
    }
    toast.success(`Imported ${data.products_created} products, ${data.variants_created} variants`);
    queryClient.invalidateQueries({ queryKey: ["products"] });
  }

  return (
    <>
      <PageHeader
        title="Products"
        description="Each product has size × colour variants; stock is tracked per variant."
        actions={
          isAdmin && (
            <>
              <Button
                variant="ghost"
                onClick={async () =>
                  downloadBlob(await fetchFile("/api/v1/products/import/template"), "product_import_template.csv")
                }
              >
                <Download size={16} /> CSV template
              </Button>
              <Button variant="secondary" onClick={() => fileRef.current?.click()}>
                <Upload size={16} /> Import CSV
              </Button>
              <input
                ref={fileRef}
                type="file"
                accept=".csv,text/csv"
                className="hidden"
                onChange={(e) => e.target.files?.[0] && importCsv(e.target.files[0])}
              />
              <Link href="/products/new">
                <Button>
                  <Plus size={16} /> New product
                </Button>
              </Link>
            </>
          )
        }
      />
      <Card>
        <div className="mb-4 grid gap-3 sm:grid-cols-3">
          <Input
            placeholder="Search name, SKU or barcode"
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setOffset(0);
            }}
          />
          <Select value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
            <option value="">All categories</option>
            {categories.data?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </Select>
          <Select value={brandId} onChange={(e) => setBrandId(e.target.value)}>
            <option value="">All brands</option>
            {brands.data?.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </Select>
        </div>
        {products.isLoading ? (
          <Spinner />
        ) : !products.data?.items.length ? (
          <Empty>No products yet.</Empty>
        ) : (
          <>
            <Table>
              <thead>
                <tr>
                  <Th>Product</Th>
                  <Th>Category</Th>
                  <Th>Brand</Th>
                  <Th>HSN</Th>
                  <Th>Sizes</Th>
                  <Th>Colours</Th>
                  <Th className="text-right">Price</Th>
                  <Th className="text-right">Stock</Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {products.data.items.map((p) => {
                  const stock = p.variants.reduce((s, v) => s + v.quantity_on_hand, 0);
                  const prices = p.variants.map((v) => num(v.selling_price));
                  const sizes = [...new Set(p.variants.map((v) => v.size))];
                  const colors = [...new Set(p.variants.map((v) => v.color))];
                  return (
                    <tr key={p.id} className="hover:bg-slate-50">
                      <Td>
                        <Link href={`/products/${p.id}`} className="font-medium text-brand-600 hover:underline">
                          {p.name}
                        </Link>
                      </Td>
                      <Td>{p.category?.name ?? "—"}</Td>
                      <Td>{p.brand?.name ?? "—"}</Td>
                      <Td>{p.hsn_code}</Td>
                      <Td className="max-w-40 truncate">{sizes.join(", ")}</Td>
                      <Td className="max-w-40 truncate">{colors.join(", ")}</Td>
                      <Td className="text-right tabular-nums">
                        {prices.length
                          ? Math.min(...prices) === Math.max(...prices)
                            ? inr(prices[0])
                            : `${inr(Math.min(...prices))}–${inr(Math.max(...prices))}`
                          : "—"}
                      </Td>
                      <Td className="text-right">
                        <Badge tone={stock === 0 ? "red" : "slate"}>{stock}</Badge>
                      </Td>
                    </tr>
                  );
                })}
              </tbody>
            </Table>
            <Pagination offset={offset} limit={LIMIT} total={products.data.total} onChange={setOffset} />
          </>
        )}
      </Card>
    </>
  );
}
