-- Chợ Trời UIT: DB-6C moderator workflow, audit and listing holds.
-- Additive and idempotent SQL Server migration. Never run the base schema over an
-- existing database. This migration does not grant any user a role.
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO
SET NOCOUNT ON;
SET XACT_ABORT ON;
GO
IF OBJECT_ID(N'dbo.USERS', N'U') IS NULL
    THROW 51040, 'dbo.USERS does not exist; apply the base schema first.', 1;
IF OBJECT_ID(N'dbo.PRODUCTS', N'U') IS NULL
    THROW 51041, 'dbo.PRODUCTS does not exist; apply the base schema first.', 1;
IF OBJECT_ID(N'dbo.PRODUCT_REPORTS', N'U') IS NULL
    THROW 51042, 'dbo.PRODUCT_REPORTS does not exist; apply DB-6B first.', 1;
BEGIN TRANSACTION;
IF OBJECT_ID(N'dbo.ROLES', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.ROLES (
        role_code VARCHAR(32) NOT NULL,
        description NVARCHAR(100) NOT NULL,
        CONSTRAINT PK_Roles PRIMARY KEY CLUSTERED (role_code)
    );
END;
IF NOT EXISTS (SELECT 1 FROM dbo.ROLES WHERE role_code = 'MODERATOR')
    INSERT INTO dbo.ROLES (role_code, description)
    VALUES ('MODERATOR', N'Can review and action product reports within the moderator workflow.');
IF NOT EXISTS (SELECT 1 FROM dbo.ROLES WHERE role_code = 'ADMIN')
    INSERT INTO dbo.ROLES (role_code, description)
    VALUES ('ADMIN', N'Can review escalated reports and perform moderator workflow administration.');
IF OBJECT_ID(N'dbo.USER_ROLE_ASSIGNMENTS', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.USER_ROLE_ASSIGNMENTS (
        assignment_id BIGINT IDENTITY(1,1) NOT NULL,
        user_id INT NOT NULL,
        role_code VARCHAR(32) NOT NULL,
        granted_at DATETIME2(0) NOT NULL CONSTRAINT DF_UserRoleAssignments_Granted DEFAULT SYSUTCDATETIME(),
        granted_by_user_id INT NULL,
        grant_reason NVARCHAR(250) NOT NULL,
        revoked_at DATETIME2(0) NULL,
        revoked_by_user_id INT NULL,
        revoke_reason NVARCHAR(250) NULL,
        CONSTRAINT PK_UserRoleAssignments PRIMARY KEY CLUSTERED (assignment_id),
        CONSTRAINT FK_UserRoleAssignments_User FOREIGN KEY (user_id) REFERENCES dbo.USERS (user_id),
        CONSTRAINT FK_UserRoleAssignments_Role FOREIGN KEY (role_code) REFERENCES dbo.ROLES (role_code),
        CONSTRAINT FK_UserRoleAssignments_GrantedBy FOREIGN KEY (granted_by_user_id) REFERENCES dbo.USERS (user_id),
        CONSTRAINT FK_UserRoleAssignments_RevokedBy FOREIGN KEY (revoked_by_user_id) REFERENCES dbo.USERS (user_id),
        CONSTRAINT CHK_UserRoleAssignments_Revocation CHECK (
            (revoked_at IS NULL AND revoked_by_user_id IS NULL AND revoke_reason IS NULL)
            OR (revoked_at IS NOT NULL AND revoke_reason IS NOT NULL)
        )
    );
END;
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.USER_ROLE_ASSIGNMENTS')
      AND name = N'UX_UserRoleAssignments_UserRoleActive'
)
    CREATE UNIQUE INDEX UX_UserRoleAssignments_UserRoleActive
        ON dbo.USER_ROLE_ASSIGNMENTS (user_id, role_code) WHERE revoked_at IS NULL;
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.USER_ROLE_ASSIGNMENTS')
      AND name = N'IX_UserRoleAssignments_UserActive'
)
    CREATE INDEX IX_UserRoleAssignments_UserActive
        ON dbo.USER_ROLE_ASSIGNMENTS (user_id, revoked_at);
IF COL_LENGTH(N'dbo.PRODUCT_REPORTS', N'assigned_moderator_user_id') IS NULL
    ALTER TABLE dbo.PRODUCT_REPORTS ADD assigned_moderator_user_id INT NULL;
IF COL_LENGTH(N'dbo.PRODUCT_REPORTS', N'review_started_at') IS NULL
    ALTER TABLE dbo.PRODUCT_REPORTS ADD review_started_at DATETIME2(0) NULL;
IF COL_LENGTH(N'dbo.PRODUCT_REPORTS', N'resolved_at') IS NULL
    ALTER TABLE dbo.PRODUCT_REPORTS ADD resolved_at DATETIME2(0) NULL;
IF COL_LENGTH(N'dbo.PRODUCT_REPORTS', N'resolution_code') IS NULL
    ALTER TABLE dbo.PRODUCT_REPORTS ADD resolution_code VARCHAR(32) NULL;
IF NOT EXISTS (
    SELECT 1 FROM sys.foreign_keys WHERE parent_object_id = OBJECT_ID(N'dbo.PRODUCT_REPORTS')
      AND name = N'FK_ProductReports_AssignedModerator'
)
    ALTER TABLE dbo.PRODUCT_REPORTS ADD CONSTRAINT FK_ProductReports_AssignedModerator
        FOREIGN KEY (assigned_moderator_user_id) REFERENCES dbo.USERS (user_id);
IF EXISTS (
    SELECT 1 FROM sys.check_constraints WHERE parent_object_id = OBJECT_ID(N'dbo.PRODUCT_REPORTS')
      AND name = N'CHK_ProductReports_Status'
)
    ALTER TABLE dbo.PRODUCT_REPORTS DROP CONSTRAINT CHK_ProductReports_Status;
ALTER TABLE dbo.PRODUCT_REPORTS WITH CHECK ADD CONSTRAINT CHK_ProductReports_Status CHECK (
    status IN ('Submitted', 'InReview', 'Escalated', 'Dismissed', 'Actioned')
);
ALTER TABLE dbo.PRODUCT_REPORTS CHECK CONSTRAINT CHK_ProductReports_Status;
IF EXISTS (
    SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.PRODUCT_REPORTS')
      AND name = N'UX_ProductReports_ReporterTargetOpen'
)
    DROP INDEX UX_ProductReports_ReporterTargetOpen ON dbo.PRODUCT_REPORTS;
CREATE UNIQUE INDEX UX_ProductReports_ReporterTargetOpen
    ON dbo.PRODUCT_REPORTS (reporter_user_id ASC, target_product_id ASC)
    WHERE status IN ('Submitted', 'InReview', 'Escalated');
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.PRODUCT_REPORTS')
      AND name = N'IX_ProductReports_Queue'
)
    CREATE INDEX IX_ProductReports_Queue ON dbo.PRODUCT_REPORTS (status ASC, submitted_at ASC, report_id ASC)
        INCLUDE (assigned_moderator_user_id);
IF OBJECT_ID(N'dbo.MODERATION_ACTIONS', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.MODERATION_ACTIONS (
        action_id BIGINT IDENTITY(1,1) NOT NULL,
        report_id BIGINT NOT NULL,
        actor_user_id INT NOT NULL,
        actor_role_code VARCHAR(32) NOT NULL,
        action_code VARCHAR(32) NOT NULL,
        from_status VARCHAR(16) NULL,
        to_status VARCHAR(16) NOT NULL,
        resolution_code VARCHAR(32) NULL,
        internal_note NVARCHAR(1000) NULL,
        occurred_at DATETIME2(0) NOT NULL CONSTRAINT DF_ModerationActions_Occurred DEFAULT SYSUTCDATETIME(),
        CONSTRAINT PK_ModerationActions PRIMARY KEY CLUSTERED (action_id),
        CONSTRAINT FK_ModerationActions_Report FOREIGN KEY (report_id) REFERENCES dbo.PRODUCT_REPORTS (report_id),
        CONSTRAINT FK_ModerationActions_Actor FOREIGN KEY (actor_user_id) REFERENCES dbo.USERS (user_id),
        CONSTRAINT FK_ModerationActions_Role FOREIGN KEY (actor_role_code) REFERENCES dbo.ROLES (role_code),
        CONSTRAINT CHK_ModerationActions_ActionCode CHECK (
            action_code IN ('CLAIMED', 'RELEASED', 'DISMISSED', 'ACTIONED', 'ESCALATED', 'HOLD_PLACED', 'HOLD_RELEASED')
        ),
        CONSTRAINT CHK_ModerationActions_FromStatus CHECK (
            from_status IS NULL OR from_status IN ('Submitted', 'InReview', 'Escalated', 'Dismissed', 'Actioned')
        ),
        CONSTRAINT CHK_ModerationActions_ToStatus CHECK (
            to_status IN ('Submitted', 'InReview', 'Escalated', 'Dismissed', 'Actioned')
        ),
        CONSTRAINT CHK_ModerationActions_NoteLength CHECK (
            internal_note IS NULL OR DATALENGTH(internal_note) <= 2000
        )
    );
END;
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.MODERATION_ACTIONS')
      AND name = N'IX_ModerationActions_ReportOccurred'
)
    CREATE INDEX IX_ModerationActions_ReportOccurred
        ON dbo.MODERATION_ACTIONS (report_id, occurred_at, action_id);
IF OBJECT_ID(N'dbo.PRODUCT_MODERATION', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.PRODUCT_MODERATION (
        product_id INT NOT NULL,
        report_id BIGINT NOT NULL,
        is_held BIT NOT NULL CONSTRAINT DF_ProductModeration_IsHeld DEFAULT 1,
        held_at DATETIME2(0) NOT NULL CONSTRAINT DF_ProductModeration_HeldAt DEFAULT SYSUTCDATETIME(),
        held_by_user_id INT NOT NULL,
        released_at DATETIME2(0) NULL,
        released_by_user_id INT NULL,
        CONSTRAINT PK_ProductModeration PRIMARY KEY CLUSTERED (product_id),
        CONSTRAINT FK_ProductModeration_Product FOREIGN KEY (product_id) REFERENCES dbo.PRODUCTS (product_id),
        CONSTRAINT FK_ProductModeration_Report FOREIGN KEY (report_id) REFERENCES dbo.PRODUCT_REPORTS (report_id),
        CONSTRAINT FK_ProductModeration_HeldBy FOREIGN KEY (held_by_user_id) REFERENCES dbo.USERS (user_id),
        CONSTRAINT FK_ProductModeration_ReleasedBy FOREIGN KEY (released_by_user_id) REFERENCES dbo.USERS (user_id),
        CONSTRAINT CHK_ProductModeration_ReleaseState CHECK (
            (is_held = 1 AND released_at IS NULL AND released_by_user_id IS NULL)
            OR (is_held = 0 AND released_at IS NOT NULL AND released_by_user_id IS NOT NULL)
        )
    );
END;
COMMIT TRANSACTION;
