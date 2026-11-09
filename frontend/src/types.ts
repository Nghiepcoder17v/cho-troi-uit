export type ProductStatus = "Available" | "Sold" | "Hidden";
export type Condition = "Brand New" | "Like New" | "Good" | "Fair";

export interface Seller {
  user_id: number;
  full_name: string;
}

export interface SellerReputation {
  user_id: number;
  score: number;
  completed_sales: number;
  total_sales: number;
  label: string;
}

export interface Product {
  product_id: number;
  category_id: number;
  title: string;
  description: string | null;
  price: number;
  condition: Condition;
  status: ProductStatus;
  created_at: string;
  seller: Seller;
}

export interface Category {
  category_id: number;
  category_name: string;
}

export interface Pagination {
  current_page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
}

export interface TransactionHistory {
  transaction_id: number;
  product_id: number;
  amount: number;
  status: string;
  transaction_date: string;
  product_title: string;
  buyer: Seller;
  seller: Seller;
}

export interface User {
  user_id: number;
  student_id: string;
  email: string;
  full_name: string;
  major: string | null;
  created_at: string;
}
