-- Chợ Trời UIT: DB-6D admin-controlled role provisioning audit.
-- Additive and idempotent. Requires DB-6C roles and assignments.
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO
SET NOCOUNT ON;
SET XACT_ABORT ON;
GO
IF OBJECT_ID(N'dbo.ROLES', N'U') IS NULL
    THROW 51060, 'dbo.ROLES does not exist; apply DB-6C first.', 1;
IF OBJECT_ID(N'dbo.USER_ROLE_ASSIGNMENTS', N'U') IS NULL
    THROW 51061, 'dbo.USER_ROLE_ASSIGNMENTS does not exist; apply DB-6C first.', 1;
BEGIN TRANSACTION;
IF OBJECT_ID(N'dbo.USER_ROLE_ASSIGNMENT_EVENTS', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.USER_ROLE_ASSIGNMENT_EVENTS (
        event_id BIGINT IDENTITY(1,1) NOT NULL,
        assignment_id BIGINT NOT NULL,
        target_user_id INT NOT NULL,
        role_code VARCHAR(32) NOT NULL,
        actor_user_id INT NOT NULL,
        actor_role_code VARCHAR(32) NOT NULL,
        event_code VARCHAR(16) NOT NULL,
        reason NVARCHAR(250) NOT NULL,
        occurred_at DATETIME2(0) NOT NULL
            CONSTRAINT DF_UserRoleAssignmentEvents_Occurred DEFAULT SYSUTCDATETIME(),
        CONSTRAINT PK_UserRoleAssignmentEvents PRIMARY KEY CLUSTERED (event_id),
        CONSTRAINT FK_UserRoleAssignmentEvents_Assignment FOREIGN KEY (assignment_id)
            REFERENCES dbo.USER_ROLE_ASSIGNMENTS (assignment_id),
        CONSTRAINT FK_UserRoleAssignmentEvents_Target FOREIGN KEY (target_user_id)
            REFERENCES dbo.USERS (user_id),
        CONSTRAINT FK_UserRoleAssignmentEvents_Role FOREIGN KEY (role_code)
            REFERENCES dbo.ROLES (role_code),
        CONSTRAINT FK_UserRoleAssignmentEvents_Actor FOREIGN KEY (actor_user_id)
            REFERENCES dbo.USERS (user_id),
        CONSTRAINT FK_UserRoleAssignmentEvents_ActorRole FOREIGN KEY (actor_role_code)
            REFERENCES dbo.ROLES (role_code),
        CONSTRAINT CHK_UserRoleAssignmentEvents_EventCode CHECK (
            event_code IN ('GRANTED', 'REVOKED')
        ),
        CONSTRAINT CHK_UserRoleAssignmentEvents_Reason CHECK (
            LEN(LTRIM(RTRIM(reason))) BETWEEN 8 AND 250
        )
    );
END;
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID(N'dbo.USER_ROLE_ASSIGNMENT_EVENTS')
      AND name = N'IX_UserRoleAssignmentEvents_TargetOccurred'
)
    CREATE INDEX IX_UserRoleAssignmentEvents_TargetOccurred
        ON dbo.USER_ROLE_ASSIGNMENT_EVENTS (target_user_id, occurred_at DESC, event_id DESC);
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID(N'dbo.USER_ROLE_ASSIGNMENT_EVENTS')
      AND name = N'IX_UserRoleAssignmentEvents_AssignmentOccurred'
)
    CREATE INDEX IX_UserRoleAssignmentEvents_AssignmentOccurred
        ON dbo.USER_ROLE_ASSIGNMENT_EVENTS (assignment_id, occurred_at, event_id);
COMMIT TRANSACTION;
