USE master;
GO

IF DB_ID(N'NorthstarSource') IS NULL
BEGIN
    CREATE DATABASE NorthstarSource;
END
GO

USE NorthstarSource;
GO

IF OBJECT_ID(N'dbo.users', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.users (
        user_id nvarchar(255) NOT NULL PRIMARY KEY,
        role nvarchar(255) NOT NULL,
        full_name nvarchar(255) NOT NULL,
        team_id nvarchar(255) NULL,
        active bit NOT NULL CONSTRAINT df_users_active DEFAULT (1)
    );
END
GO

IF OBJECT_ID(N'dbo.providers', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.providers (
        provider_id nvarchar(255) NOT NULL PRIMARY KEY,
        user_id nvarchar(255) NOT NULL UNIQUE,
        specialty nvarchar(255) NOT NULL,
        clinic_location nvarchar(255) NOT NULL,
        active bit NOT NULL CONSTRAINT df_providers_active DEFAULT (1)
    );
END
GO

IF OBJECT_ID(N'dbo.patients', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.patients (
        patient_id nvarchar(255) NOT NULL PRIMARY KEY,
        display_name nvarchar(255) NOT NULL,
        birth_year int NULL,
        contact_preference nvarchar(255) NOT NULL,
        created_at datetimeoffset(7) NOT NULL,
        updated_at datetimeoffset(7) NOT NULL
    );
END
GO

IF OBJECT_ID(N'dbo.care_team_assignments', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.care_team_assignments (
        assignment_id nvarchar(255) NOT NULL PRIMARY KEY,
        patient_id nvarchar(255) NOT NULL UNIQUE,
        nurse_user_id nvarchar(255) NULL,
        provider_id nvarchar(255) NULL,
        assigned_at datetimeoffset(7) NOT NULL,
        updated_at datetimeoffset(7) NOT NULL
    );
END
GO

IF OBJECT_ID(N'dbo.appointments', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.appointments (
        appointment_id nvarchar(255) NOT NULL PRIMARY KEY,
        patient_id nvarchar(255) NOT NULL
            REFERENCES dbo.patients(patient_id),
        provider_id nvarchar(255) NOT NULL
            REFERENCES dbo.providers(provider_id),
        scheduled_start_at datetimeoffset(7) NOT NULL,
        status nvarchar(255) NOT NULL,
        reason_code nvarchar(255) NULL,
        updated_at datetimeoffset(7) NOT NULL
    );
END
GO

IF OBJECT_ID(N'dbo.referrals', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.referrals (
        referral_id nvarchar(255) NOT NULL PRIMARY KEY,
        patient_id nvarchar(255) NOT NULL
            REFERENCES dbo.patients(patient_id),
        requested_by_provider_id nvarchar(255) NOT NULL
            REFERENCES dbo.providers(provider_id),
        receiving_specialty nvarchar(255) NOT NULL,
        status nvarchar(255) NOT NULL,
        requested_at datetimeoffset(7) NOT NULL,
        scheduled_for_at datetimeoffset(7) NULL,
        updated_at datetimeoffset(7) NOT NULL
    );
END
GO

IF OBJECT_ID(N'dbo.care_tasks', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.care_tasks (
        task_id nvarchar(255) NOT NULL PRIMARY KEY,
        patient_id nvarchar(255) NOT NULL REFERENCES dbo.patients(patient_id),
        appointment_id nvarchar(255) NULL,
        referral_id nvarchar(255) NULL,
        task_type nvarchar(255) NOT NULL,
        status nvarchar(255) NOT NULL,
        assigned_to_user_id nvarchar(255) NULL,
        due_at datetimeoffset(7) NULL,
        priority nvarchar(255) NOT NULL,
        priority_reason nvarchar(255) NOT NULL,
        created_at datetimeoffset(7) NOT NULL,
        updated_at datetimeoffset(7) NOT NULL
    );
END
GO

IF NOT EXISTS (SELECT 1 FROM dbo.users)
BEGIN
    DECLARE @seed_at datetimeoffset(7) = TODATETIMEOFFSET(SYSUTCDATETIME(), '+00:00');

    INSERT dbo.users (user_id, role, full_name, team_id)
    VALUES
        (N'admin', N'admin', N'Avery Morgan', N'operations'),
        (N'reception-1', N'receptionist', N'Morgan Lee', N'front-desk'),
        (N'reception-2', N'receptionist', N'Casey Rowan', N'front-desk'),
        (N'nurse-a', N'nurse', N'Riley Chen', N'team-a'),
        (N'nurse-b', N'nurse', N'Jordan Blake', N'team-b'),
        (N'doctor-a', N'doctor', N'Taylor Quinn', N'team-a'),
        (N'pa-b', N'pa', N'Cameron Patel', N'team-b');

    INSERT dbo.providers (provider_id, user_id, specialty, clinic_location)
    VALUES
        (N'prov-a', N'doctor-a', N'Primary Care', N'Northstar East'),
        (N'prov-b', N'pa-b', N'Primary Care', N'Northstar West');

    INSERT dbo.patients
        (patient_id, display_name, birth_year, contact_preference, created_at, updated_at)
    VALUES
        (N'p1', N'Arden Vale', 1981, N'portal', @seed_at, @seed_at),
        (N'p2', N'Briar Finch', 1982, N'portal', @seed_at, @seed_at),
        (N'p3', N'Cedar North', 1983, N'portal', @seed_at, @seed_at),
        (N'p4', N'Dara Sol', 1984, N'portal', @seed_at, @seed_at),
        (N'p5', N'Ember Lake', 1985, N'portal', @seed_at, @seed_at),
        (N'p6', N'Flint Gray', 1986, N'portal', @seed_at, @seed_at),
        (N'p7', N'Gale Winter', 1987, N'portal', @seed_at, @seed_at),
        (N'p8', N'Harbor Reed', 1988, N'portal', @seed_at, @seed_at),
        (N'p9', N'Indigo Moss', 1989, N'portal', @seed_at, @seed_at),
        (N'p10', N'Juniper Hale', 1990, N'portal', @seed_at, @seed_at);

    INSERT dbo.care_team_assignments
        (assignment_id, patient_id, nurse_user_id, provider_id, assigned_at, updated_at)
    VALUES
        (N'a1', N'p1', N'nurse-a', N'prov-a', @seed_at, @seed_at),
        (N'a2', N'p2', N'nurse-a', N'prov-a', @seed_at, @seed_at),
        (N'a3', N'p3', N'nurse-a', N'prov-a', @seed_at, @seed_at),
        (N'a4', N'p4', N'nurse-a', N'prov-a', @seed_at, @seed_at),
        (N'a5', N'p5', N'nurse-a', N'prov-a', @seed_at, @seed_at),
        (N'a6', N'p6', N'nurse-b', N'prov-b', @seed_at, @seed_at),
        (N'a7', N'p7', N'nurse-b', N'prov-b', @seed_at, @seed_at),
        (N'a8', N'p8', N'nurse-b', N'prov-b', @seed_at, @seed_at),
        (N'a9', N'p9', N'nurse-b', N'prov-b', @seed_at, @seed_at),
        (N'a10', N'p10', N'nurse-b', N'prov-b', @seed_at, @seed_at);

    INSERT dbo.appointments
        (appointment_id, patient_id, provider_id, scheduled_start_at, status, reason_code, updated_at)
    VALUES
        (N'appt1', N'p1', N'prov-a', DATEADD(day, -4, @seed_at), N'completed', NULL, DATEADD(hour, -1, @seed_at)),
        (N'appt2', N'p2', N'prov-a', DATEADD(day, -3, @seed_at), N'no_show', NULL, DATEADD(hour, -2, @seed_at)),
        (N'appt3', N'p3', N'prov-a', DATEADD(day, -2, @seed_at), N'scheduled', NULL, DATEADD(hour, -3, @seed_at)),
        (N'appt4', N'p4', N'prov-a', DATEADD(day, -1, @seed_at), N'canceled', N'admin_follow_up', DATEADD(hour, -4, @seed_at)),
        (N'appt5', N'p5', N'prov-a', @seed_at, N'scheduled', NULL, DATEADD(hour, -5, @seed_at)),
        (N'appt6', N'p6', N'prov-b', DATEADD(day, 1, @seed_at), N'completed', NULL, DATEADD(hour, -6, @seed_at)),
        (N'appt7', N'p7', N'prov-b', DATEADD(day, 2, @seed_at), N'scheduled', NULL, DATEADD(hour, -7, @seed_at)),
        (N'appt8', N'p8', N'prov-b', DATEADD(day, 3, @seed_at), N'scheduled', NULL, DATEADD(hour, -8, @seed_at)),
        (N'appt9', N'p9', N'prov-b', DATEADD(day, 4, @seed_at), N'completed', NULL, DATEADD(hour, -9, @seed_at)),
        (N'appt10', N'p10', N'prov-b', DATEADD(day, 5, @seed_at), N'scheduled', NULL, DATEADD(hour, -10, @seed_at));

    INSERT dbo.referrals
        (referral_id, patient_id, requested_by_provider_id, receiving_specialty, status,
         requested_at, scheduled_for_at, updated_at)
    VALUES
        (N'ref1', N'p3', N'prov-a', N'Mobility Services', N'pending', DATEADD(day, -10, @seed_at), NULL, @seed_at),
        (N'ref2', N'p4', N'prov-a', N'Scheduling Office', N'requested', DATEADD(day, -2, @seed_at), NULL, @seed_at),
        (N'ref3', N'p6', N'prov-b', N'Community Support', N'scheduled', DATEADD(day, -4, @seed_at), DATEADD(day, 7, @seed_at), @seed_at),
        (N'ref4', N'p7', N'prov-b', N'Mobility Services', N'closed', DATEADD(day, -12, @seed_at), NULL, @seed_at),
        (N'ref5', N'p8', N'prov-b', N'Scheduling Office', N'pending', DATEADD(day, -8, @seed_at), NULL, @seed_at),
        (N'ref6', N'p1', N'prov-a', N'Community Support', N'closed', DATEADD(day, -3, @seed_at), NULL, @seed_at);

    INSERT dbo.care_tasks
        (task_id, patient_id, appointment_id, referral_id, task_type, status, assigned_to_user_id,
         due_at, priority, priority_reason, created_at, updated_at)
    VALUES
        (N'task1', N'p2', N'appt2', NULL, N'reschedule', N'open', N'nurse-a', DATEADD(day, -2, @seed_at), N'high', N'seed scenario', @seed_at, @seed_at),
        (N'task2', N'p3', NULL, NULL, N'referral_follow_up', N'open', N'nurse-a', DATEADD(day, 2, @seed_at), N'normal', N'seed scenario', @seed_at, @seed_at),
        (N'task3', N'p4', N'appt4', NULL, N'contact_patient', N'completed', N'nurse-a', DATEADD(day, -1, @seed_at), N'high', N'seed scenario', @seed_at, @seed_at),
        (N'task4', N'p5', NULL, NULL, N'follow_up', N'open', N'nurse-a', @seed_at, N'normal', N'seed scenario', @seed_at, @seed_at),
        (N'task5', N'p6', NULL, NULL, N'follow_up', N'open', N'nurse-b', DATEADD(day, 3, @seed_at), N'normal', N'seed scenario', @seed_at, @seed_at),
        (N'task6', N'p7', NULL, NULL, N'contact_patient', N'in_progress', N'nurse-b', DATEADD(day, 1, @seed_at), N'normal', N'seed scenario', @seed_at, @seed_at),
        (N'task7', N'p8', NULL, NULL, N'referral_follow_up', N'open', N'nurse-b', DATEADD(day, -3, @seed_at), N'high', N'seed scenario', @seed_at, @seed_at),
        (N'task8', N'p9', NULL, NULL, N'follow_up', N'completed', N'nurse-b', DATEADD(day, -2, @seed_at), N'high', N'seed scenario', @seed_at, @seed_at),
        (N'task9', N'p10', NULL, NULL, N'contact_patient', N'open', N'nurse-b', DATEADD(day, 1, @seed_at), N'normal', N'seed scenario', @seed_at, @seed_at),
        (N'task10', N'p1', NULL, NULL, N'follow_up', N'completed', N'nurse-a', DATEADD(day, -5, @seed_at), N'high', N'seed scenario', @seed_at, @seed_at);
END
GO

DECLARE @cdc_enable_attempt int = 1;
DECLARE @cdc_enable_error nvarchar(4000);

WHILE @cdc_enable_attempt <= 5
BEGIN
    IF EXISTS (
        SELECT 1 FROM sys.databases
        WHERE name = N'NorthstarSource' AND is_cdc_enabled = 1
    )
        BREAK;

    BEGIN TRY
        EXEC sys.sp_cdc_enable_db;
    END TRY
    BEGIN CATCH
        SET @cdc_enable_error = ERROR_MESSAGE();
        IF @cdc_enable_attempt = 5 OR ERROR_NUMBER() NOT IN (1205, 22830)
            THROW;

        PRINT CONCAT(
            N'CDC database enable attempt ',
            @cdc_enable_attempt,
            N' failed with a transient error: ',
            @cdc_enable_error,
            N'. Retrying...'
        );
        WAITFOR DELAY '00:00:05';
    END CATCH;

    SET @cdc_enable_attempt += 1;
END
GO

IF NOT EXISTS (
    SELECT 1
    FROM cdc.change_tables
    WHERE source_object_id = OBJECT_ID(N'dbo.appointments')
)
BEGIN
    EXEC sys.sp_cdc_enable_table
        @source_schema = N'dbo',
        @source_name = N'appointments',
        @capture_instance = N'app_appointments',
        @role_name = NULL,
        @supports_net_changes = 0;
END
GO
