import { toast } from "sonner";

import { fetchFile, openBlob } from "@/lib/api/client";

export async function openInvoice(saleId: number, layout: "a4" | "thermal" = "a4") {
  try {
    openBlob(await fetchFile(`/api/v1/sales/${saleId}/invoice.pdf?layout=${layout}`));
  } catch (e) {
    toast.error(e instanceof Error ? e.message : "Could not open invoice");
  }
}

export async function openCreditNote(returnId: number) {
  try {
    openBlob(await fetchFile(`/api/v1/returns/${returnId}/credit-note.pdf`));
  } catch (e) {
    toast.error(e instanceof Error ? e.message : "Could not open credit note");
  }
}
