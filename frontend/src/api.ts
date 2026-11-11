import type {
  Category,
  Condition,
  Pagination,
  Product,
  ProductUpdatePayload,
  PublicProfile,
  Review,
  ReviewMine,
  SellerReputation,
  TransactionHistory,
  User,
} from "./types";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

type Envelope<T> = { status: string; data: T; message?: string; pagination?: Pagination };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
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

export async function login(email: string, password: string): Promise<{ user_id: number; major?: string | null }> {
  return (await request<Envelope<{ user_id: number; major?: string | null }>>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  })).data;
}

export async function logout(): Promise<void> {
  await request("/api/auth/logout", { method: "POST" });
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

export async function getProduct(productId: number): Promise<Product> {
  return (await request<Envelope<Product>>(`/api/products/${productId}`)).data;
}

export async function buyProduct(product_id: number, amount: number): Promise<void> {
  await request(`/api/transactions`, {
    method: "POST",
    body: JSON.stringify({ product_id, amount }),
  });
}

export async function acceptTransaction(transactionId: number): Promise<void> {
  await request(`/api/transactions/${transactionId}/accept`, { method: "POST" });
}

export async function rejectTransaction(transactionId: number): Promise<void> {
  await request(`/api/transactions/${transactionId}/reject`, { method: "POST" });
}

export async function cancelTransaction(transactionId: number): Promise<void> {
  await request(`/api/transactions/${transactionId}/cancel`, { method: "POST" });
}

export async function confirmTransactionCompletion(transactionId: number): Promise<void> {
  await request(`/api/transactions/${transactionId}/confirm-completion`, { method: "POST" });
}

export async function getMyProducts(): Promise<Product[]> {
  return (await request<Envelope<Product[]>>("/api/products/mine?page_size=100")).data;
}

export async function getPurchases(): Promise<TransactionHistory[]> {
  return (await request<Envelope<TransactionHistory[]>>("/api/transactions/purchases")).data;
}

export async function getSales(): Promise<TransactionHistory[]> {
  return (await request<Envelope<TransactionHistory[]>>("/api/transactions/sales")).data;
}

export async function getSellerReputation(userId: number): Promise<SellerReputation> {
  return (await request<Envelope<SellerReputation>>(`/api/users/${userId}/reputation`)).data;
}

export async function getUserReviews(userId: number): Promise<Review[]> {
  return (await request<Envelope<Review[]>>(`/api/users/${userId}/reviews`)).data;
}

export async function createTransactionReview(
  transactionId: number,
  body: { rating: number; comment?: string | null },
): Promise<ReviewMine> {
  return (await request<Envelope<ReviewMine>>(`/api/transactions/${transactionId}/reviews`, {
    method: "POST",
    body: JSON.stringify(body),
  })).data;
}

export async function updateReview(
  reviewId: number,
  body: { rating?: number; comment?: string | null },
): Promise<ReviewMine> {
  return (await request<Envelope<ReviewMine>>(`/api/reviews/${reviewId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  })).data;
}


export async function updateMyProfile(body: {
  full_name?: string;
  major?: string | null;
}): Promise<User> {
  return (await request<Envelope<User>>("/api/users/me", {
    method: "PATCH",
    body: JSON.stringify(body),
  })).data;
}

export async function changeMyPassword(body: {
  current_password: string;
  new_password: string;
}): Promise<void> {
  await request("/api/users/me/change-password", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function updateProduct(
  productId: number,
  body: ProductUpdatePayload,
): Promise<Product> {
  return (await request<Envelope<Product>>(`/api/products/${productId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  })).data;
}

export async function getPublicProfile(userId: number): Promise<PublicProfile> {
  return (await request<Envelope<PublicProfile>>(`/api/users/${userId}/public-profile`)).data;
}

export async function getPublicProducts(userId: number, status?: "Available" | "Sold"): Promise<Product[]> {
  const query = new URLSearchParams({ page: "1", page_size: "100" });
  if (status) query.set("status", status);
  return (await request<Envelope<Product[]>>(`/api/users/${userId}/products?${query}`)).data;
}
