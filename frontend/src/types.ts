export type ProductStatus = "Available" | "Reserved" | "Sold" | "Hidden";
export type TransactionStatus = "Pending" | "Accepted" | "Completed" | "Cancelled";
export type OrderAction = "accept" | "reject" | "cancel" | "confirm-completion";
export type Condition = "Brand New" | "Like New" | "Good" | "Fair";

export interface Seller {
  user_id: number;
  full_name: string;
}

export interface SellerReputation {
  user_id: number;
  score: number | null;
  review_count: number;
  rating_distribution: Record<"1" | "2" | "3" | "4" | "5", number>;
  completed_sales: number;
  total_sales: number;
  label: string;
}

export interface ReviewMine {
  review_id: number;
  rating: number;
  comment: string | null;
  created_at: string;
  updated_at: string;
}

export interface Review extends ReviewMine {
  transaction_id: number;
  reviewer_id: number;
  reviewee_id: number;
  reviewer: Seller;
  product_title: string;
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
  status: TransactionStatus;
  transaction_date: string;
  buyer_confirmed_at: string | null;
  seller_confirmed_at: string | null;
  product_title: string;
  buyer: Seller;
  seller: Seller;
  my_review: ReviewMine | null;
}

export interface User {
  user_id: number;
  student_id: string;
  email: string;
  full_name: string;
  major: string | null;
  created_at: string;
}


export interface PublicProfile {
  user_id: number;
  full_name: string;
  major: string | null;
  created_at: string;
  score: number | null;
  review_count: number;
  completed_sales: number;
  label: string;
}

export interface ProductUpdatePayload {
  category_id?: number;
  title?: string;
  description?: string | null;
  price?: number;
  condition?: Condition;
  status?: "Available" | "Hidden";
}
