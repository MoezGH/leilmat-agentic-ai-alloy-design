import { describe, expect, it } from "vitest";

import { BillingHttpError, isBillingUnavailable } from "./client";

describe("billing availability", () => {
  it("treats a 5xx from the billing service as 'not available'", () => {
    expect(isBillingUnavailable(new BillingHttpError("create-portal-session", 500))).toBe(true);
    expect(isBillingUnavailable(new BillingHttpError("purchase-credits", 503))).toBe(true);
  });

  it("does not hide billing for a client error or a non-billing failure", () => {
    expect(isBillingUnavailable(new BillingHttpError("create-checkout-session", 401))).toBe(false);
    expect(isBillingUnavailable(new BillingHttpError("create-checkout-session", 400))).toBe(false);
    expect(isBillingUnavailable(new Error("Failed to fetch"))).toBe(false);
    expect(isBillingUnavailable(undefined)).toBe(false);
  });

  it("keeps the endpoint and status in the message", () => {
    expect(new BillingHttpError("create-portal-session", 500).message).toBe("create-portal-session HTTP 500");
  });
});
