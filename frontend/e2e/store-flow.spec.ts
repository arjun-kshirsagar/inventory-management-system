import { type Page, expect, test } from "@playwright/test";

async function login(page: Page, email: string, password: string) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

test("admin creates a product, receives stock, sells it and sees it in reports", async ({ page }) => {
  const name = `E2E Linen Shirt ${Date.now()}`;
  await login(page, "admin@store.local", "admin123");
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();

  // Create a product with a 2 x 1 size/colour matrix.
  await page.goto("/products/new");
  await page.getByLabel("Product name").fill(name);
  await page.getByLabel("HSN code").fill("6205");
  await page.getByLabel("Sizes").fill("M, L");
  await page.getByLabel("Colours").fill("Sage");
  await page.getByLabel("MRP (₹)").fill("1799");
  await page.getByLabel("Selling price (₹)").fill("1599");
  await page.getByLabel("Cost price (₹)").fill("700");
  await page.getByRole("button", { name: "Create product" }).click();
  await expect(page.getByRole("heading", { name })).toBeVisible();
  await expect(page.getByRole("cell", { name: "Sage" })).toHaveCount(2);

  // Receive 5 units of size M.
  await page.goto("/inventory/receive");
  await page.getByPlaceholder("Scan barcode or search product to add").fill(name);
  await page.keyboard.press("Enter");
  await page.getByRole("button", { name: new RegExp(`${name} M · Sage`) }).click();
  await page.getByLabel("Quantity").fill("5");
  await page.getByRole("button", { name: /Save GRN · 5 units/ }).click();
  await expect(page.getByText(/received 5 units/)).toBeVisible();

  // Sell 2 at the POS, paid by UPI.
  await page.goto("/pos");
  const search = page.getByLabel("Search products");
  await search.fill(name);
  await search.press("Enter");
  await page.getByRole("button", { name: new RegExp(`${name} M · Sage`) }).click();
  await page.getByLabel("Increase").click();
  // 2 x 1599 = 3198, GST 5% (per-piece value under Rs 2,500).
  await expect(page.getByRole("button", { name: /Charge ₹3,198.00/ })).toBeEnabled();
  await expect(page.getByText("GST 5%")).toBeVisible();
  await page.getByRole("button", { name: /Charge/ }).click();
  await page.getByRole("dialog").getByRole("combobox").selectOption("upi");
  await page.getByRole("button", { name: "Complete sale" }).click();
  const done = page.getByRole("dialog", { name: "Sale complete" });
  await expect(done).toBeVisible();
  const invoiceNo = (await done.getByText(/^Invoice /).textContent())!.replace("Invoice ", "");

  // Invoice PDF opens in a new tab.
  const popup = page.waitForEvent("popup");
  await done.getByRole("button", { name: "A4 invoice" }).click();
  await (await popup).close();
  await done.getByRole("button", { name: "New sale" }).click();

  // Stock went 5 -> 3.
  await page.goto("/inventory");
  await page.getByPlaceholder("Search name, SKU, barcode").fill(name);
  const row = page.getByRole("row", { name: new RegExp(`${name} M Sage`) });
  await expect(row.getByText("3", { exact: true })).toBeVisible();

  // Sale is listed, and today's sales report includes it.
  await page.goto("/sales");
  await page.getByPlaceholder("Invoice no, customer name or phone").fill(invoiceNo);
  await expect(page.getByRole("link", { name: invoiceNo })).toBeVisible();
  await page.getByRole("link", { name: invoiceNo }).click();
  await expect(page.getByText("UPI")).toBeVisible();

  await page.goto("/reports");
  await page.getByRole("button", { name: "GST summary" }).click();
  await expect(page.getByRole("cell", { name: "6205" }).first()).toBeVisible();
});

test("cashier only sees cashier pages", async ({ page }) => {
  await login(page, "cashier@store.local", "cashier123");
  await expect(page).toHaveURL(/\/pos$/);
  await expect(page.getByRole("link", { name: "Reports" })).toHaveCount(0);
  await page.goto("/reports");
  await expect(page).toHaveURL(/\/pos$/);
});
