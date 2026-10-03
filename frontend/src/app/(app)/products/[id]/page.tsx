"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Tag } from "lucide-react";
import { useParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { type ProductValues, ProductFields, toProductBody } from "@/components/ProductFields";
import { Badge, Button, Card, Input, Modal, PageHeader, Spinner, Table, Td, Th } from "@/components/ui";
import { type MatrixValues, VariantMatrixFields, toMatrixBody } from "@/components/VariantMatrixFields";
import { api, errorMessage, openBlob, postFile, unwrap, type Schemas } from "@/lib/api/client";
import { useAuth } from "@/lib/auth";
import { inr } from "@/lib/format";

type Variant = Schemas["VariantOut"];

export default function ProductDetailPage() {
  const { id } = useParams<{ id: string }>();
  const productId = Number(id);
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const queryClient = useQueryClient();
  // Unsaved edits; null means "show what the server has".
  const [edits, setValues] = useState<ProductValues | null>(null);
  const [adding, setAdding] = useState(false);
  const [matrix, setMatrix] = useState<MatrixValues>({
    sizes: "",
    colors: "",
    mrp: "",
    selling_price: "",
    cost_price: "",
    reorder_level: "5",
  });
  const [labelCopies, setLabelCopies] = useState<Record<number, number>>({});

  const product = useQuery({
    queryKey: ["product", productId],
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/products/{product_id}", { params: { path: { product_id: productId } } })),
  });

  const values: ProductValues | undefined =
    edits ??
    (product.data && {
      name: product.data.name,
      category_id: product.data.category_id ? String(product.data.category_id) : "",
      brand_id: product.data.brand_id ? String(product.data.brand_id) : "",
      hsn_code: product.data.hsn_code,
      gender: product.data.gender ?? "",
      material: product.data.material ?? "",
      description: product.data.description ?? "",
    });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["product", productId] });
    queryClient.invalidateQueries({ queryKey: ["products"] });
  };

  const save = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.PATCH("/api/v1/products/{product_id}", {
          params: { path: { product_id: productId } },
          body: toProductBody(values!),
        }),
      ),
    onSuccess: () => {
      toast.success("Saved");
      setValues(null);
      refresh();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  const addVariants = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/products/{product_id}/variants", {
          params: { path: { product_id: productId } },
          body: { matrix: toMatrixBody(matrix) },
        }),
      ),
    onSuccess: (created) => {
      toast.success(created.length ? `Added ${created.length} variants` : "Those variants already exist");
      setAdding(false);
      refresh();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  async function updateVariant(v: Variant, patch: Partial<Variant>) {
    const { error } = await api.PATCH("/api/v1/variants/{variant_id}", {
      params: { path: { variant_id: v.id } },
      body: patch,
    });
    if (error) toast.error(errorMessage(error));
    else refresh();
  }

  async function printLabels() {
    const items = Object.entries(labelCopies)
      .filter(([, n]) => n > 0)
      .map(([variant_id, copies]) => ({ variant_id: Number(variant_id), copies }));
    if (!items.length) return toast.error("Set the number of labels for at least one variant");
    try {
      openBlob(await postFile("/api/v1/variants/labels.pdf", items));
    } catch (e) {
      toast.error(errorMessage(e));
    }
  }

  if (product.isLoading || !product.data || !values) return <Spinner />;
  const p = product.data;

  return (
    <>
      <PageHeader
        title={p.name}
        description={[p.brand?.name, p.category?.name, `HSN ${p.hsn_code}`].filter(Boolean).join(" · ")}
        actions={
          isAdmin && (
            <Button variant={p.is_active ? "secondary" : "primary"} onClick={() =>
              api
                .PATCH("/api/v1/products/{product_id}", {
                  params: { path: { product_id: productId } },
                  body: { is_active: !p.is_active },
                })
                .then(refresh)
            }>
              {p.is_active ? "Archive product" : "Restore product"}
            </Button>
          )
        }
      />
      <div className="space-y-6">
        <Card
          title={`Variants (${p.variants.length})`}
          actions={
            <>
              <Button variant="secondary" size="sm" onClick={printLabels}>
                <Tag size={14} /> Print labels
              </Button>
              {isAdmin && (
                <Button size="sm" onClick={() => setAdding(true)}>
                  <Plus size={14} /> Add sizes / colours
                </Button>
              )}
            </>
          }
        >
          <Table>
            <thead>
              <tr>
                <Th>Size</Th>
                <Th>Colour</Th>
                <Th>SKU</Th>
                <Th>Barcode</Th>
                <Th className="text-right">MRP</Th>
                <Th className="text-right">Price</Th>
                <Th className="text-right">Cost</Th>
                <Th className="text-right">Reorder at</Th>
                <Th className="text-right">Stock</Th>
                <Th>Labels</Th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {p.variants.map((v) => (
                <tr key={v.id} className={v.is_active ? "" : "opacity-50"}>
                  <Td className="font-medium">{v.size}</Td>
                  <Td>{v.color}</Td>
                  <Td className="font-mono text-xs">{v.sku}</Td>
                  <Td className="font-mono text-xs">{v.barcode}</Td>
                  {(["mrp", "selling_price", "cost_price"] as const).map((k) => (
                    <Td key={k} className="text-right">
                      {isAdmin ? (
                        <Input
                          className="ml-auto w-24 text-right"
                          defaultValue={v[k]}
                          onBlur={(e) => e.target.value !== v[k] && updateVariant(v, { [k]: e.target.value })}
                          aria-label={k}
                        />
                      ) : (
                        inr(v[k])
                      )}
                    </Td>
                  ))}
                  <Td className="text-right">
                    {isAdmin ? (
                      <Input
                        className="ml-auto w-16 text-right"
                        defaultValue={v.reorder_level}
                        onBlur={(e) =>
                          Number(e.target.value) !== v.reorder_level &&
                          updateVariant(v, { reorder_level: Number(e.target.value) })
                        }
                        aria-label="Reorder level"
                      />
                    ) : (
                      v.reorder_level
                    )}
                  </Td>
                  <Td className="text-right">
                    <Badge tone={v.quantity_on_hand <= v.reorder_level ? (v.quantity_on_hand ? "amber" : "red") : "green"}>
                      {v.quantity_on_hand}
                    </Badge>
                  </Td>
                  <Td>
                    <Input
                      type="number"
                      min={0}
                      className="w-16"
                      value={labelCopies[v.id] ?? 0}
                      onChange={(e) => setLabelCopies({ ...labelCopies, [v.id]: Math.max(0, Number(e.target.value)) })}
                      aria-label="Label copies"
                    />
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
          <div className="mt-2 text-right">
            <button
              className="text-xs text-brand-600 hover:underline"
              onClick={() => setLabelCopies(Object.fromEntries(p.variants.map((v) => [v.id, v.quantity_on_hand])))}
            >
              One label per unit in stock
            </button>
          </div>
        </Card>

        {isAdmin && (
          <Card
            title="Details"
            actions={
              <Button size="sm" onClick={() => save.mutate()} disabled={save.isPending}>
                Save details
              </Button>
            }
          >
            <ProductFields value={values} onChange={setValues} />
          </Card>
        )}
      </div>

      <Modal open={adding} onClose={() => setAdding(false)} title="Add variants" wide>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            addVariants.mutate();
          }}
        >
          <VariantMatrixFields value={matrix} onChange={setMatrix} />
          <p className="mt-2 text-xs text-slate-500">Size/colour combinations that already exist are skipped.</p>
          <div className="mt-4 flex justify-end">
            <Button type="submit" disabled={addVariants.isPending}>
              Add variants
            </Button>
          </div>
        </form>
      </Modal>
    </>
  );
}
