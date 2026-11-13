"""ORM models - phản chiếu đúng schema trong database_scripts/01_init_schema.sql.

Nguồn sự thật của schema là file SQL (đã có index, trigger, filtered unique index).
Backend KHÔNG tự tạo bảng; các CheckConstraint bên dưới chỉ để model khớp với DB
và để unit test (SQLite) kiểm tra được ràng buộc.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    desc,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Unicode,
    UnicodeText,
    text,
)
from sqlalchemy.orm import relationship

from database import Base


def utcnow() -> datetime:
    """Giờ UTC, không kèm tzinfo (khớp DATETIME2 + SYSUTCDATETIME() trong SQL)."""
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


class Category(Base):
    __tablename__ = "categories"

    category_id = Column(Integer, primary_key=True, autoincrement=True)
    category_name = Column(Unicode(50), unique=True, nullable=False)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("email LIKE '%@gm.uit.edu.vn'", name="CHK_User_Email"),
    )

    user_id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String(8), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(100), nullable=False)
    full_name = Column(Unicode(100), nullable=False)
    major = Column(Unicode(50))
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("price >= 0", name="CHK_Product_Price"),
        CheckConstraint(
            "condition IN ('Brand New', 'Like New', 'Good', 'Fair')", name="CHK_Product_Condition"
        ),
        CheckConstraint("status IN ('Available', 'Reserved', 'Sold', 'Hidden')", name="CHK_Product_Status"),
    )

    product_id = Column(Integer, primary_key=True, autoincrement=True)
    seller_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.category_id"), nullable=False)
    title = Column(Unicode(200), nullable=False)
    description = Column(UnicodeText, nullable=True)
    price = Column(Numeric(10, 2), nullable=False)
    condition = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default="Available")
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    seller = relationship("User")
    category = relationship("Category")
    moderation = relationship("ProductModeration", back_populates="product", uselist=False)

    @property
    def moderation_status(self) -> str | None:
        """Safe seller-facing state; never includes reporter or moderator details."""
        if self.moderation is not None and self.moderation.is_held:
            return "Held"
        return None


class UserFavorite(Base):
    """A private saved-product relation; duplicate prevention is the composite PK."""

    __tablename__ = "user_favorites"
    __table_args__ = (
        Index(
            "IX_UserFavorites_UserCreated",
            "user_id",
            desc("created_at"),
            desc("product_id"),
        ),
    )

    user_id = Column(Integer, ForeignKey("users.user_id"), primary_key=True)
    product_id = Column(Integer, ForeignKey("products.product_id"), primary_key=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)


class ProductReport(Base):
    """Private product-report intake. Only the submitting user owns the report."""

    __tablename__ = "product_reports"
    __table_args__ = (
        CheckConstraint(
            "reason_code IN ('PROHIBITED_ITEM', 'MISLEADING_LISTING', "
            "'SUSPECTED_SCAM', 'SPAM_OR_DUPLICATE', 'OTHER')",
            name="CHK_ProductReports_ReasonCode",
        ),
        CheckConstraint(
            "status IN ('Submitted', 'InReview', 'Escalated', 'Dismissed', 'Actioned')",
            name="CHK_ProductReports_Status",
        ),
        Index(
            "IX_ProductReports_ReporterSubmitted",
            "reporter_user_id",
            desc("submitted_at"),
            desc("report_id"),
        ),
        Index(
            "IX_ProductReports_StatusSubmitted",
            "status",
            "submitted_at",
            "report_id",
        ),
        Index(
            "UX_ProductReports_ReporterTargetOpen",
            "reporter_user_id",
            "target_product_id",
            unique=True,
            mssql_where=text("status <> 'Dismissed' AND status <> 'Actioned'"),
            sqlite_where=text("status <> 'Dismissed' AND status <> 'Actioned'"),
        ),
    )

    # SQLite uses INTEGER for rowid-backed autoincrement in unit tests.
    report_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    reporter_user_id = Column(
        Integer,
        ForeignKey("users.user_id", name="FK_ProductReports_Reporter"),
        nullable=False,
    )
    target_product_id = Column(
        Integer,
        ForeignKey("products.product_id", name="FK_ProductReports_Product"),
        nullable=False,
    )
    reason_code = Column(String(32), nullable=False)
    description = Column(Unicode(500), nullable=True)
    status = Column(String(16), nullable=False, default="Submitted")
    assigned_moderator_user_id = Column(
        Integer,
        ForeignKey("users.user_id", name="FK_ProductReports_AssignedModerator"),
        nullable=True,
    )
    review_started_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolution_code = Column(String(32), nullable=True)
    submitted_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)


class Role(Base):
    __tablename__ = "roles"

    role_code = Column(String(32), primary_key=True)
    description = Column(Unicode(100), nullable=False)


class UserRoleAssignment(Base):
    __tablename__ = "user_role_assignments"
    __table_args__ = (
        Index(
            "UX_UserRoleAssignments_UserRoleActive",
            "user_id",
            "role_code",
            unique=True,
            mssql_where=text("revoked_at IS NULL"),
            sqlite_where=text("revoked_at IS NULL"),
        ),
        Index("IX_UserRoleAssignments_UserActive", "user_id", "revoked_at"),
    )

    assignment_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    role_code = Column(String(32), ForeignKey("roles.role_code"), nullable=False)
    granted_at = Column(DateTime, nullable=False, default=utcnow)
    granted_by_user_id = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    grant_reason = Column(Unicode(250), nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    revoked_by_user_id = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    revoke_reason = Column(Unicode(250), nullable=True)


class ProductModeration(Base):
    """One current moderation-hold row per product; history lives in ModerationAction."""

    __tablename__ = "product_moderation"
    __table_args__ = (
        CheckConstraint(
            "(is_held = 1 AND released_at IS NULL AND released_by_user_id IS NULL) OR "
            "(is_held = 0 AND released_at IS NOT NULL AND released_by_user_id IS NOT NULL)",
            name="CHK_ProductModeration_ReleaseState",
        ),
    )

    product_id = Column(Integer, ForeignKey("products.product_id"), primary_key=True)
    report_id = Column(BigInteger, ForeignKey("product_reports.report_id"), nullable=False)
    is_held = Column(Boolean, nullable=False, default=True)
    held_at = Column(DateTime, nullable=False, default=utcnow)
    held_by_user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    released_at = Column(DateTime, nullable=True)
    released_by_user_id = Column(Integer, ForeignKey("users.user_id"), nullable=True)

    product = relationship("Product", back_populates="moderation")


class ModerationAction(Base):
    """Moderation audit event; written in the same transaction as each state change."""

    __tablename__ = "moderation_actions"
    __table_args__ = (
        CheckConstraint(
            "action_code IN ('CLAIMED', 'RELEASED', 'DISMISSED', 'ACTIONED', "
            "'ESCALATED', 'HOLD_PLACED', 'HOLD_RELEASED')",
            name="CHK_ModerationActions_ActionCode",
        ),
        CheckConstraint(
            "from_status IS NULL OR from_status IN "
            "('Submitted', 'InReview', 'Escalated', 'Dismissed', 'Actioned')",
            name="CHK_ModerationActions_FromStatus",
        ),
        CheckConstraint(
            "to_status IN ('Submitted', 'InReview', 'Escalated', 'Dismissed', 'Actioned')",
            name="CHK_ModerationActions_ToStatus",
        ),
        CheckConstraint(
            "internal_note IS NULL OR length(internal_note) <= 1000",
            name="CHK_ModerationActions_NoteLength",
        ),
        Index("IX_ModerationActions_ReportOccurred", "report_id", "occurred_at", "action_id"),
    )

    action_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    report_id = Column(BigInteger, ForeignKey("product_reports.report_id"), nullable=False)
    actor_user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    actor_role_code = Column(String(32), ForeignKey("roles.role_code"), nullable=False)
    action_code = Column(String(32), nullable=False)
    from_status = Column(String(16), nullable=True)
    to_status = Column(String(16), nullable=False)
    resolution_code = Column(String(32), nullable=True)
    internal_note = Column(Unicode(1000), nullable=True)
    occurred_at = Column(DateTime, nullable=False, default=utcnow)


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="CHK_Transaction_Amount"),
        CheckConstraint(
            "status IN ('Pending', 'Accepted', 'Completed', 'Cancelled')", name="CHK_Transaction_Status"
        ),
    )

    transaction_id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.product_id"), nullable=False)
    buyer_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    status = Column(String(20), nullable=False, default="Pending")
    transaction_date = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)
    buyer_confirmed_at = Column(DateTime, nullable=True)
    seller_confirmed_at = Column(DateTime, nullable=True)

    product = relationship("Product")
    buyer = relationship("User")



class TransactionEvent(Base):
    """Append-only transaction timeline event; application code only inserts and reads."""

    __tablename__ = "transaction_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('REQUEST_CREATED', 'SELLER_ACCEPTED', 'SELLER_REJECTED', "
            "'BUYER_CANCELLED', 'SELLER_CANCELLED', 'BUYER_CONFIRMED', "
            "'SELLER_CONFIRMED', 'TRANSACTION_COMPLETED')",
            name="CHK_TransactionEvents_EventType",
        ),
        CheckConstraint(
            "from_status IS NULL OR from_status IN ('Pending', 'Accepted', 'Completed', 'Cancelled')",
            name="CHK_TransactionEvents_FromStatus",
        ),
        CheckConstraint(
            "to_status IN ('Pending', 'Accepted', 'Completed', 'Cancelled')",
            name="CHK_TransactionEvents_ToStatus",
        ),
        Index(
            "IX_TransactionEvents_TransactionOccurred",
            "transaction_id",
            "occurred_at",
            "event_id",
        ),
    )

    # SQLite needs INTEGER (not BIGINT) to provide rowid-backed autoincrement in unit tests.
    event_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    transaction_id = Column(
        Integer,
        ForeignKey("transactions.transaction_id"),
        nullable=False,
    )
    actor_user_id = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    event_type = Column(String(32), nullable=False)
    from_status = Column(String(20), nullable=True)
    to_status = Column(String(20), nullable=False)
    occurred_at = Column(DateTime, nullable=False, default=utcnow)


class Review(Base):
    """Đánh giá hai chiều giữa buyer và seller sau một giao dịch hoàn tất."""

    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint(
            "transaction_id", "reviewer_id", name="UQ_Reviews_Transaction_Reviewer"
        ),
        CheckConstraint("rating >= 1 AND rating <= 5", name="CHK_Review_Rating"),
    )

    review_id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_id = Column(
        Integer, ForeignKey("transactions.transaction_id"), nullable=False
    )
    reviewer_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    reviewee_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    rating = Column(Integer, nullable=False)
    comment = Column(Unicode(1000), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    transaction = relationship("Transaction")
    reviewer = relationship("User", foreign_keys=[reviewer_id])
    reviewee = relationship("User", foreign_keys=[reviewee_id])
