import type { Condition } from "../types";

export const money = new Intl.NumberFormat("vi-VN", { style: "currency", currency: "VND" });
export const conditions: Condition[] = ["Brand New", "Like New", "Good", "Fair"];

/** Format SQL Server DATETIME2 values that the API serializes as UTC without a suffix. */
export function formatUtcDateTime(value: string): string {
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value);
  const date = new Date(hasTimezone ? value : `${value}Z`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("vi-VN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}
