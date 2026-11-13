-- DB-6C: controlled one-time bootstrap of the first ADMIN reviewer.
-- Operator-run only; this is NOT an application migration. Replace both NULLs.
SET NOCOUNT ON;
SET XACT_ABORT ON;
DECLARE @TargetUserId INT = NULL; -- Required: verified dbo.USERS.user_id
DECLARE @ApprovalReference NVARCHAR(100) = NULL; -- Required: change ticket / approval ID
IF @TargetUserId IS NULL
    THROW 51050, 'Set @TargetUserId to the approved existing user_id before execution.', 1;
IF @ApprovalReference IS NULL OR LEN(LTRIM(RTRIM(@ApprovalReference))) < 4
    THROW 51051, 'Set @ApprovalReference to the approved change reference.', 1;
IF NOT EXISTS (SELECT 1 FROM dbo.USERS WHERE user_id = @TargetUserId)
    THROW 51052, 'The selected user_id does not exist.', 1;
IF NOT EXISTS (SELECT 1 FROM dbo.ROLES WHERE role_code = 'ADMIN')
    THROW 51053, 'Apply the DB-6C migration before bootstrap.', 1;
IF EXISTS (
    SELECT 1 FROM dbo.USER_ROLE_ASSIGNMENTS
    WHERE user_id = @TargetUserId AND role_code = 'ADMIN' AND revoked_at IS NULL
)
    THROW 51054, 'The selected user already has an active ADMIN assignment.', 1;
BEGIN TRANSACTION;
INSERT INTO dbo.USER_ROLE_ASSIGNMENTS (user_id, role_code, granted_by_user_id, grant_reason)
VALUES (@TargetUserId, 'ADMIN', NULL,
        CONCAT(N'Initial ADMIN bootstrap; approval=', @ApprovalReference));
COMMIT TRANSACTION;
SELECT assignment_id, user_id, role_code, granted_at, grant_reason
FROM dbo.USER_ROLE_ASSIGNMENTS
WHERE user_id = @TargetUserId AND role_code = 'ADMIN' AND revoked_at IS NULL;
