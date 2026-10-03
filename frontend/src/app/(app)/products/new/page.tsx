"use client";

import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { ProductFields, emptyProduct, toProductBody } from "@/components/ProductFields";
import { Button, Card, PageHeader } from "@/components/ui";
import { type MatrixValues, VariantMatrixFields, toMatrixBody } from "@/components/VariantMatrixFields";
import { api, errorMessage, unwrap } from "@/lib/api/client";

export default function NewProductPage() {
  const router = useRouter();
  const [product, setProduct] = useState(emptyProduct);
  const [matrix, setMatrix] = useState<MatrixValues>({
    sizes: "S, M, L, XL",
    colors: "",
    mrp: "",
    selling_price: "",
    cost_price: "",
    reorder_level: "5",
  });

  const create = useMutation({
    mutationFn: async () =>
      unwrap(await api.POST("/api/v1/products", { body: { ...toProductBody(product), variants: [], matrix: toMatrixBody(matrix) } })),
    onSuccess: (p) => {
      toast.success(`Created ${p.name} with ${p.variants.length} variants`);
      router.push(`/products/${p.id}`);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        create.mutate();
      }}
    >
      <PageHeader
        title="New product"
        actions={
          <Button type="submit" disabled={create.isPending}>
            {create.isPending ? "Saving…" : "Create product"}
          </Button>
        }
      />
      <div className="grid gap-6 xl:grid-cols-2">
        <Card title="Details">
          <ProductFields value={product} onChange={setProduct} />
        </Card>
        <Card title="Variants (size × colour)">
          <VariantMatrixFields value={matrix} onChange={setMatrix} />
        </Card>
      </div>
      <p className="mt-4 text-sm text-slate-500">
        New variants start with zero stock. Use <b>Inventory → Receive stock</b> to add quantities.
      </p>
    </form>
  );
}
