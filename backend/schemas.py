import re
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Condition = Literal["Brand New", "Like New", "Good", "Fair"]
ProductStatus = Literal["Available", "Reserved", "Sold", "Hidden"]
ProductVisibility = Literal["Available", "Hidden"]
PublicProductStatus = Literal["Available", "Sold"]
ProductSort = Literal["newest", "price_asc", "price_desc"]
TransactionEventType = Literal[
    "REQUEST_CREATED",
    "SELLER_ACCEPTED",
    "SELLER_REJECTED",
    "BUYER_CANCELLED",
    "SELLER_CANCELLED",
    "BUYER_CONFIRMED",
    "SELLER_CONFIRMED",
    "TRANSACTION_COMPLETED",
]

_EMAIL_RE = re.compile(r"^[a-z0-9._+-]+@gm\.uit\.edu\.vn$")
_STUDENT_ID_RE = re.compile(r"^\d{8}$")
MAX_PRICE = Decimal("99999999.99")  # khớp DECIMAL(10,2)


# ---------------------------------------------------------------- AUTH
class RegisterRequest(BaseModel):
    email: str = Field(..., description="Email trường, VD: 25520001@gm.uit.edu.vn")
    student_id: str = Field(..., description="MSSV 8 chữ số, phải trùng phần trước @ của email")
    full_name: str = Field(..., min_length=2, max_length=100)
    major: Optional[str] = Field(None, max_length=50)
    password: str = Field(..., min_length=8, description="Tối thiểu 8 ký tự (tối đa 72 byte UTF-8)")

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValueError("Chỉ chấp nhận email sinh viên UIT (@gm.uit.edu.vn)")
        return v

    @field_validator("student_id")
    @classmethod
    def _student_id(cls, v: str) -> str:
        v = v.strip()
        if not _STUDENT_ID_RE.match(v):
            raise ValueError("MSSV phải gồm đúng 8 chữ số")
        return v

    @field_validator("full_name", "major")
    @classmethod
    def _strip(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if isinstance(v, str) else v

    @field_validator("password")
    @classmethod
    def _password(cls, v: str) -> str:
        if len(v.encode("utf-8")) > 72:  # giới hạn của bcrypt
            raise ValueError("Mật khẩu tối đa 72 byte")
        return v

    @model_validator(mode="after")
    def _email_matches_student_id(self):
        if self.email.split("@")[0] != self.student_id:
            raise ValueError("MSSV phải trùng với phần trước @ của email")
        return self


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return v.strip().lower()


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    student_id: str
    email: str
    full_name: str
    major: Optional[str] = None
    created_at: datetime


class UserProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    major: Optional[str] = Field(None, max_length=50)

    @field_validator("full_name", mode="before")
    @classmethod
    def _validate_full_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            raise ValueError("Họ tên không được để trống")
        value = value.strip()
        if not value:
            raise ValueError("Họ tên không được để trống")
        return value

    @field_validator("major")
    @classmethod
    def _normalize_major(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @model_validator(mode="after")
    def _require_changes(self):
        if not self.model_fields_set:
            raise ValueError("Cần cung cấp ít nhất một trường để cập nhật")
        return self


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8)

    @field_validator("current_password", "new_password")
    @classmethod
    def _password_byte_limit(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Mật khẩu tối đa 72 byte")
        return value

    @model_validator(mode="after")
    def _password_must_change(self):
        if self.current_password == self.new_password:
            raise ValueError("Mật khẩu mới phải khác mật khẩu hiện tại")
        return self


class PublicProfileOut(BaseModel):
    user_id: int
    full_name: str
    major: Optional[str] = None
    created_at: datetime
    score: Optional[float] = None
    review_count: int
    completed_sales: int
    label: str


class SellerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    full_name: str


class ReviewCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = Field(None, max_length=1000)

    @field_validator("comment")
    @classmethod
    def _normalize_comment(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ReviewUpdate(BaseModel):
    rating: Optional[int] = Field(None, ge=1, le=5)
    comment: Optional[str] = Field(None, max_length=1000)

    @field_validator("rating")
    @classmethod
    def _rating_cannot_be_null(cls, value: Optional[int]) -> Optional[int]:
        if value is None:
            raise ValueError("Điểm đánh giá không được để trống")
        return value

    @field_validator("comment")
    @classmethod
    def _normalize_comment(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @model_validator(mode="after")
    def _require_at_least_one_change(self):
        if not self.model_fields_set:
            raise ValueError("Cần cung cấp rating hoặc comment để cập nhật")
        return self


class ReviewMineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    review_id: int
    rating: int
    comment: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ReviewOut(ReviewMineOut):
    transaction_id: int
    reviewer_id: int
    reviewee_id: int
    reviewer: SellerOut
    product_title: str


class SellerReputationOut(BaseModel):
    user_id: int
    score: Optional[float] = None
    review_count: int
    rating_distribution: dict[str, int]
    completed_sales: int
    total_sales: int
    label: str


class SessionOut(BaseModel):
    user_id: int
    major: Optional[str] = None


# ---------------------------------------------------------------- CATEGORY
class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    category_id: int
    category_name: str


# ---------------------------------------------------------------- PRODUCT
class ProductCreate(BaseModel):
    category_id: int
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    price: Decimal = Field(..., ge=0, le=MAX_PRICE, decimal_places=2)
    condition: Condition

    @field_validator("title")
    @classmethod
    def _title(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Tiêu đề không được để trống")
        return v


class ProductUpdate(BaseModel):
    category_id: Optional[int] = None
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    price: Optional[Decimal] = Field(None, ge=0, le=MAX_PRICE, decimal_places=2)
    condition: Optional[Condition] = None
    status: Optional[ProductVisibility] = None

    @field_validator("title")
    @classmethod
    def _title(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("Tiêu đề không được để trống")
        return v


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    category_id: int
    title: str
    description: Optional[str] = None
    price: float
    condition: str
    status: str
    created_at: datetime
    seller: SellerOut


class ProductHistoryOut(ProductOut):
    moderation_status: Optional[Literal["Held"]] = None


class Pagination(BaseModel):
    current_page: int
    page_size: int
    total_items: int
    total_pages: int


class FavoriteProductOut(BaseModel):
    product_id: int
    title: str
    price: float
    condition: Condition
    status: ProductStatus
    seller: SellerOut


class FavoriteItemOut(BaseModel):
    product_id: int
    created_at: datetime
    status: ProductStatus
    product: Optional[FavoriteProductOut] = None


class ProductCreated(BaseModel):
    product_id: int


# ---------------------------------------------------------------- PRODUCT REPORTS
ProductReportReasonCode = Literal[
    "PROHIBITED_ITEM",
    "MISLEADING_LISTING",
    "SUSPECTED_SCAM",
    "SPAM_OR_DUPLICATE",
    "OTHER",
]


class ProductReportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_product_id: int = Field(..., ge=1)
    reason_code: ProductReportReasonCode
    description: Optional[str] = Field(None, max_length=500)

    @field_validator("description")
    @classmethod
    def _normalize_description(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ProductReportOut(BaseModel):
    report_id: int
    target_product_id: int
    reason_code: ProductReportReasonCode
    status: Literal["Submitted"]
    submitted_at: datetime


class ProductReportEnvelope(BaseModel):
    status: str = "success"
    message: str
    data: ProductReportOut


# ---------------------------------------------------------------- MODERATION (DB-6C)
ModerationReportStatus = Literal["Submitted", "InReview", "Escalated", "Dismissed", "Actioned"]
ModerationDecision = Literal["Dismissed", "Actioned", "Escalated"]
ModerationResolutionCode = Literal[
    "NOT_A_VIOLATION",
    "INSUFFICIENT_EVIDENCE",
    "OUT_OF_SCOPE",
    "TEMPORARY_LISTING_HOLD",
    "NEEDS_ADMIN_REVIEW",
]


class ModerationDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: ModerationDecision
    resolution_code: ModerationResolutionCode
    internal_note: str = Field(..., min_length=1, max_length=1000)

    @field_validator("internal_note")
    @classmethod
    def _normalize_internal_note(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Ghi chú nội bộ không được để trống")
        return value

    @model_validator(mode="after")
    def _decision_code_matches(self):
        allowed = {
            "Dismissed": {"NOT_A_VIOLATION", "INSUFFICIENT_EVIDENCE", "OUT_OF_SCOPE"},
            "Actioned": {"TEMPORARY_LISTING_HOLD"},
            "Escalated": {"NEEDS_ADMIN_REVIEW"},
        }
        if self.resolution_code not in allowed[self.decision]:
            raise ValueError("Mã kết quả không phù hợp với quyết định")
        return self


class ModerationReleaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason_code: Literal["NEEDS_REQUEUE", "ADMIN_REASSIGNMENT", "CLAIMED_IN_ERROR"]
    internal_note: str = Field(..., min_length=1, max_length=1000)

    @field_validator("internal_note")
    @classmethod
    def _normalize_internal_note(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Ghi chú nội bộ không được để trống")
        return value


class ModerationHoldReleaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    internal_note: str = Field(..., min_length=1, max_length=1000)

    @field_validator("internal_note")
    @classmethod
    def _normalize_internal_note(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Ghi chú nội bộ không được để trống")
        return value


class ModerationProductOut(BaseModel):
    product_id: int
    title: str
    description: Optional[str] = None
    price: float
    condition: str
    status: str
    seller_id: int


class ModerationReportOut(BaseModel):
    report_id: int
    target_product_id: int
    reason_code: ProductReportReasonCode
    description: Optional[str] = None
    status: ModerationReportStatus
    submitted_at: datetime
    updated_at: datetime
    assigned_moderator_user_id: Optional[int] = None
    assigned_moderator_name: Optional[str] = None
    review_started_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    resolution_code: Optional[str] = None
    product: ModerationProductOut


class ModerationActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    action_id: int
    actor_user_id: int
    actor_role_code: str
    action_code: str
    from_status: Optional[str] = None
    to_status: str
    resolution_code: Optional[str] = None
    internal_note: Optional[str] = None
    occurred_at: datetime


class ModerationReportDetailOut(ModerationReportOut):
    actions: list[ModerationActionOut]


class ModerationQueueEnvelope(BaseModel):
    status: str = "success"
    data: list[ModerationReportOut]
    pagination: Pagination


class ModerationReportEnvelope(BaseModel):
    status: str = "success"
    data: ModerationReportDetailOut


class ModerationMessageEnvelope(BaseModel):
    status: str = "success"
    message: str


# ---------------------------------------------------------------- ADMIN CONTROLS (DB-6D)
AdminRoleCode = Literal["MODERATOR", "ADMIN"]


class MyPermissionsOut(BaseModel):
    role_codes: list[AdminRoleCode] = Field(default_factory=list)


class MyPermissionsEnvelope(BaseModel):
    status: str = "success"
    data: MyPermissionsOut


class AdminUserSummary(BaseModel):
    user_id: int
    student_id: str
    email: str
    full_name: str
    created_at: datetime


class AdminRoleAssignmentOut(BaseModel):
    assignment_id: int
    user: AdminUserSummary
    role_code: AdminRoleCode
    granted_at: datetime
    granted_by_user_id: Optional[int] = None
    granted_by_name: Optional[str] = None
    grant_reason: str
    revoked_at: Optional[datetime] = None
    revoked_by_user_id: Optional[int] = None
    revoked_by_name: Optional[str] = None
    revoke_reason: Optional[str] = None


class AdminRoleAssignmentEventOut(BaseModel):
    event_id: int
    assignment_id: int
    target_user: AdminUserSummary
    role_code: AdminRoleCode
    actor_user_id: int
    actor_name: str
    actor_role_code: AdminRoleCode
    event_code: Literal["GRANTED", "REVOKED"]
    reason: str
    occurred_at: datetime


class AdminRoleGrantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role_code: AdminRoleCode
    reason: str = Field(..., min_length=8, max_length=250)

    @field_validator("reason")
    @classmethod
    def _normalize_reason(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 8:
            raise ValueError("Lý do phải có ít nhất 8 ký tự")
        return value


class AdminRoleRevokeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(..., min_length=8, max_length=250)

    @field_validator("reason")
    @classmethod
    def _normalize_reason(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 8:
            raise ValueError("Lý do phải có ít nhất 8 ký tự")
        return value


class AdminUserListEnvelope(BaseModel):
    status: str = "success"
    data: list[AdminUserSummary]
    pagination: Pagination


class AdminRoleAssignmentListEnvelope(BaseModel):
    status: str = "success"
    data: list[AdminRoleAssignmentOut]
    pagination: Pagination


class AdminRoleAssignmentEventListEnvelope(BaseModel):
    status: str = "success"
    data: list[AdminRoleAssignmentEventOut]
    pagination: Pagination


class AdminRoleAssignmentEnvelope(BaseModel):
    status: str = "success"
    data: AdminRoleAssignmentOut


# ---------------------------------------------------------------- TRANSACTION
class TransactionCreate(BaseModel):
    product_id: int
    amount: Decimal = Field(..., ge=0, le=MAX_PRICE, decimal_places=2, description="Giá đề nghị (<= giá niêm yết)")


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    transaction_id: int
    product_id: int
    amount: float
    status: str
    transaction_date: datetime
    buyer_confirmed_at: Optional[datetime] = None
    seller_confirmed_at: Optional[datetime] = None


class TransactionEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: int
    event_type: TransactionEventType
    from_status: Optional[str] = None
    to_status: str
    occurred_at: datetime
    actor: Optional[SellerOut] = None


class TransactionHistoryOut(TransactionOut):
    product_title: str
    buyer: SellerOut
    seller: SellerOut
    my_review: Optional[ReviewMineOut] = None
    events: list[TransactionEventOut] = Field(default_factory=list)


# ---------------------------------------------------------------- ENVELOPES (theo API contract)
class UserEnvelope(BaseModel):
    status: str = "success"
    message: Optional[str] = None
    data: UserOut


class SessionEnvelope(BaseModel):
    status: str = "success"
    data: SessionOut


class CategoryListEnvelope(BaseModel):
    status: str = "success"
    data: list[CategoryOut]


class ProductListEnvelope(BaseModel):
    status: str = "success"
    data: list[ProductOut]
    pagination: Pagination


class ProductEnvelope(BaseModel):
    status: str = "success"
    data: ProductOut


class ProductCreatedEnvelope(BaseModel):
    status: str = "success"
    message: str
    data: ProductCreated


class FavoriteListEnvelope(BaseModel):
    status: str = "success"
    data: list[FavoriteItemOut]
    pagination: Pagination


class TransactionEnvelope(BaseModel):
    status: str = "success"
    message: str
    data: TransactionOut


class ProductHistoryListEnvelope(BaseModel):
    status: str = "success"
    data: list[ProductHistoryOut]
    pagination: Pagination


class TransactionHistoryListEnvelope(BaseModel):
    status: str = "success"
    data: list[TransactionHistoryOut]


class SellerReputationEnvelope(BaseModel):
    status: str = "success"
    data: SellerReputationOut



class ReviewEnvelope(BaseModel):
    status: str = "success"
    message: Optional[str] = None
    data: ReviewMineOut


class ReviewListEnvelope(BaseModel):
    status: str = "success"
    data: list[ReviewOut]



class MessageEnvelope(BaseModel):
    status: str = "success"
    message: str


class PublicProfileEnvelope(BaseModel):
    status: str = "success"
    data: PublicProfileOut
