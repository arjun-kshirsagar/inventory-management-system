import { Badge } from "@/components/ui";
import type { Schemas } from "@/lib/api/client";

export function SaleStatusBadge({ status }: { status: Schemas["SaleStatus"] }) {
  const tone = status === "completed" ? "green" : status === "returned" ? "red" : "amber";
  return <Badge tone={tone}>{status.replace("_", " ")}</Badge>;
}
