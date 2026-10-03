"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui";
import { api, errorMessage } from "@/lib/api/client";

/** Small "+" button that creates a category or brand by name and selects it. */
export function QuickCreate({
  kind,
  onCreated,
}: {
  kind: "categories" | "brands";
  onCreated: (id: number) => void;
}) {
  const queryClient = useQueryClient();
  async function create() {
    const name = window.prompt(`New ${kind === "brands" ? "brand" : "category"} name`)?.trim();
    if (!name) return;
    const { data, error } =
      kind === "brands"
        ? await api.POST("/api/v1/brands", { body: { name } })
        : await api.POST("/api/v1/categories", { body: { name } });
    if (!data) return toast.error(errorMessage(error));
    await queryClient.invalidateQueries({ queryKey: [kind] });
    onCreated(data.id);
  }
  return (
    <Button type="button" variant="secondary" onClick={create} aria-label={`Add ${kind}`}>
      <Plus size={16} />
    </Button>
  );
}
