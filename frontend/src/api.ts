import type {
  Category,
  Condition,
  Pagination,
  Product,
  TransactionHistory,
  User,
} from "./types";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

type Envelope<T> = { status: string; data: T; message?: string; pagination?: Pagination };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = localStorage.getItem("access_token");
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
  });
  const payload = (await response.json().catch(() => ({}))) as { detail?: string };
  if (!response.ok) throw new Error(payload.detail ?? "Không thể kết nối đến máy chủ");
  return payload as T;
}

export async function listProducts(params: {
  q?: string;
  category_id?: number;
  page?: number;
}): Promise<Envelope<Product[]>> {
  const search = new URLSearchParams({ page: String(params.page ?? 1), page_size: "12" });
  if (params.q) search.set("q", params.q);
  if (params.category_id) search.set("category_id", String(params.category_id));
  return request(`/api/products?${search}`);
}

export async function listCategories(): Promise<Category[]> {
  return (await request<Envelope<Category[]>>("/api/categories")).data;
}

export async function register(body: {
  email: string;
  student_id: string;
  full_name: string;
  major?: string;
  password: string;
}): Promise<User> {
  return (await request<Envelope<User>>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify(body),
  })).data;
}

export async function login(email: string, password: string): Promise<{ token: string; user_id: number }> {
  return (await request<Envelope<{ token: string; user_id: number }>>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  })).data;
}

export async function getMe(): Promise<User> {
  return (await request<Envelope<User>>("/api/users/me")).data;
}

export async function createProduct(body: {
  category_id: number;
  title: string;
  description?: string;
  price: number;
  condition: Condition;
}): Promise<number> {
  return (await request<Envelope<{ product_id: number }>>("/api/products", {
    method: "POST",
    body: JSON.stringify(body),
  })).data.product_id;
}

export async function buyProduct(product_id: number, amount: number): Promise<void> {
  await request(`/api/transactions`, {
    method: "POST",
    body: JSON.stringify({ product_id, amount }),
  });
}

export async function getMyProducts(): Promise<Product[]> {
  return (await request<Envelope<Product[]>>("/api/products/mine?page_size=100")).data;
}

export async function getPurchases(): Promise<TransactionHistory[]> {
  return (await request<Envelope<TransactionHistory[]>>("/api/transactions/purchases")).data;
}
