import type { Condition } from "../types";

export const money = new Intl.NumberFormat("vi-VN", { style: "currency", currency: "VND" });
export const conditions: Condition[] = ["Brand New", "Like New", "Good", "Fair"];
