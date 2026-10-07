DO $role$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'debezium') THEN
        CREATE ROLE debezium;
    END IF;
    ALTER ROLE debezium LOGIN REPLICATION PASSWORD 'debezium-lab-only';
END;
$role$;

CREATE TABLE public.users (
    user_id varchar(255) PRIMARY KEY,
    role varchar(255) NOT NULL,
    full_name varchar(255) NOT NULL,
    team_id varchar(255),
    active boolean NOT NULL DEFAULT true
);

CREATE TABLE public.providers (
    provider_id varchar(255) PRIMARY KEY,
    user_id varchar(255) NOT NULL UNIQUE,
    specialty varchar(255) NOT NULL,
    clinic_location varchar(255) NOT NULL,
    active boolean NOT NULL DEFAULT true
);

CREATE TABLE public.patients (
    patient_id varchar(255) PRIMARY KEY,
    display_name varchar(255) NOT NULL,
    birth_year integer,
    contact_preference varchar(255) NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);

CREATE TABLE public.care_team_assignments (
    assignment_id varchar(255) PRIMARY KEY,
    patient_id varchar(255) NOT NULL UNIQUE,
    nurse_user_id varchar(255),
    provider_id varchar(255),
    assigned_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);

CREATE TABLE public.appointments (
    appointment_id varchar(255) PRIMARY KEY,
    patient_id varchar(255) NOT NULL REFERENCES public.patients(patient_id),
    provider_id varchar(255) NOT NULL REFERENCES public.providers(provider_id),
    scheduled_start_at timestamptz NOT NULL,
    status varchar(255) NOT NULL,
    reason_code varchar(255),
    updated_at timestamptz NOT NULL
);

CREATE TABLE public.referrals (
    referral_id varchar(255) PRIMARY KEY,
    patient_id varchar(255) NOT NULL REFERENCES public.patients(patient_id),
    requested_by_provider_id varchar(255) NOT NULL REFERENCES public.providers(provider_id),
    receiving_specialty varchar(255) NOT NULL,
    status varchar(255) NOT NULL,
    requested_at timestamptz NOT NULL,
    scheduled_for_at timestamptz,
    updated_at timestamptz NOT NULL
);

CREATE TABLE public.care_tasks (
    task_id varchar(255) PRIMARY KEY,
    patient_id varchar(255) NOT NULL REFERENCES public.patients(patient_id),
    appointment_id varchar(255),
    referral_id varchar(255),
    task_type varchar(255) NOT NULL,
    status varchar(255) NOT NULL,
    assigned_to_user_id varchar(255),
    due_at timestamptz,
    priority varchar(255) NOT NULL,
    priority_reason varchar(255) NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);

DO $seed$
DECLARE
    seed_at timestamptz := clock_timestamp();
BEGIN
    INSERT INTO public.users (user_id, role, full_name, team_id)
    VALUES
        ('admin', 'admin', 'Avery Morgan', 'operations'),
        ('reception-1', 'receptionist', 'Morgan Lee', 'front-desk'),
        ('reception-2', 'receptionist', 'Casey Rowan', 'front-desk'),
        ('nurse-a', 'nurse', 'Riley Chen', 'team-a'),
        ('nurse-b', 'nurse', 'Jordan Blake', 'team-b'),
        ('doctor-a', 'doctor', 'Taylor Quinn', 'team-a'),
        ('pa-b', 'pa', 'Cameron Patel', 'team-b');

    INSERT INTO public.providers (provider_id, user_id, specialty, clinic_location)
    VALUES
        ('prov-a', 'doctor-a', 'Primary Care', 'Northstar East'),
        ('prov-b', 'pa-b', 'Primary Care', 'Northstar West');

    INSERT INTO public.patients
        (patient_id, display_name, birth_year, contact_preference, created_at, updated_at)
    VALUES
        ('p1', 'Arden Vale', 1981, 'portal', seed_at, seed_at),
        ('p2', 'Briar Finch', 1982, 'portal', seed_at, seed_at),
        ('p3', 'Cedar North', 1983, 'portal', seed_at, seed_at),
        ('p4', 'Dara Sol', 1984, 'portal', seed_at, seed_at),
        ('p5', 'Ember Lake', 1985, 'portal', seed_at, seed_at),
        ('p6', 'Flint Gray', 1986, 'portal', seed_at, seed_at),
        ('p7', 'Gale Winter', 1987, 'portal', seed_at, seed_at),
        ('p8', 'Harbor Reed', 1988, 'portal', seed_at, seed_at),
        ('p9', 'Indigo Moss', 1989, 'portal', seed_at, seed_at),
        ('p10', 'Juniper Hale', 1990, 'portal', seed_at, seed_at);

    INSERT INTO public.care_team_assignments
        (assignment_id, patient_id, nurse_user_id, provider_id, assigned_at, updated_at)
    VALUES
        ('a1', 'p1', 'nurse-a', 'prov-a', seed_at, seed_at),
        ('a2', 'p2', 'nurse-a', 'prov-a', seed_at, seed_at),
        ('a3', 'p3', 'nurse-a', 'prov-a', seed_at, seed_at),
        ('a4', 'p4', 'nurse-a', 'prov-a', seed_at, seed_at),
        ('a5', 'p5', 'nurse-a', 'prov-a', seed_at, seed_at),
        ('a6', 'p6', 'nurse-b', 'prov-b', seed_at, seed_at),
        ('a7', 'p7', 'nurse-b', 'prov-b', seed_at, seed_at),
        ('a8', 'p8', 'nurse-b', 'prov-b', seed_at, seed_at),
        ('a9', 'p9', 'nurse-b', 'prov-b', seed_at, seed_at),
        ('a10', 'p10', 'nurse-b', 'prov-b', seed_at, seed_at);

    INSERT INTO public.appointments
        (appointment_id, patient_id, provider_id, scheduled_start_at, status, reason_code, updated_at)
    VALUES
        ('appt1', 'p1', 'prov-a', seed_at - interval '4 days', 'completed', NULL, seed_at - interval '1 hour'),
        ('appt2', 'p2', 'prov-a', seed_at - interval '3 days', 'no_show', NULL, seed_at - interval '2 hours'),
        ('appt3', 'p3', 'prov-a', seed_at - interval '2 days', 'scheduled', NULL, seed_at - interval '3 hours'),
        ('appt4', 'p4', 'prov-a', seed_at - interval '1 day', 'canceled', 'admin_follow_up', seed_at - interval '4 hours'),
        ('appt5', 'p5', 'prov-a', seed_at, 'scheduled', NULL, seed_at - interval '5 hours'),
        ('appt6', 'p6', 'prov-b', seed_at + interval '1 day', 'completed', NULL, seed_at - interval '6 hours'),
        ('appt7', 'p7', 'prov-b', seed_at + interval '2 days', 'scheduled', NULL, seed_at - interval '7 hours'),
        ('appt8', 'p8', 'prov-b', seed_at + interval '3 days', 'scheduled', NULL, seed_at - interval '8 hours'),
        ('appt9', 'p9', 'prov-b', seed_at + interval '4 days', 'completed', NULL, seed_at - interval '9 hours'),
        ('appt10', 'p10', 'prov-b', seed_at + interval '5 days', 'scheduled', NULL, seed_at - interval '10 hours');

    INSERT INTO public.referrals
        (referral_id, patient_id, requested_by_provider_id, receiving_specialty, status,
         requested_at, scheduled_for_at, updated_at)
    VALUES
        ('ref1', 'p3', 'prov-a', 'Mobility Services', 'pending', seed_at - interval '10 days', NULL, seed_at),
        ('ref2', 'p4', 'prov-a', 'Scheduling Office', 'requested', seed_at - interval '2 days', NULL, seed_at),
        ('ref3', 'p6', 'prov-b', 'Community Support', 'scheduled', seed_at - interval '4 days', seed_at + interval '7 days', seed_at),
        ('ref4', 'p7', 'prov-b', 'Mobility Services', 'closed', seed_at - interval '12 days', NULL, seed_at),
        ('ref5', 'p8', 'prov-b', 'Scheduling Office', 'pending', seed_at - interval '8 days', NULL, seed_at),
        ('ref6', 'p1', 'prov-a', 'Community Support', 'closed', seed_at - interval '3 days', NULL, seed_at);

    INSERT INTO public.care_tasks
        (task_id, patient_id, appointment_id, referral_id, task_type, status, assigned_to_user_id,
         due_at, priority, priority_reason, created_at, updated_at)
    VALUES
        ('task1', 'p2', 'appt2', NULL, 'reschedule', 'open', 'nurse-a', seed_at - interval '2 days', 'high', 'seed scenario', seed_at, seed_at),
        ('task2', 'p3', NULL, NULL, 'referral_follow_up', 'open', 'nurse-a', seed_at + interval '2 days', 'normal', 'seed scenario', seed_at, seed_at),
        ('task3', 'p4', 'appt4', NULL, 'contact_patient', 'completed', 'nurse-a', seed_at - interval '1 day', 'high', 'seed scenario', seed_at, seed_at),
        ('task4', 'p5', NULL, NULL, 'follow_up', 'open', 'nurse-a', seed_at, 'normal', 'seed scenario', seed_at, seed_at),
        ('task5', 'p6', NULL, NULL, 'follow_up', 'open', 'nurse-b', seed_at + interval '3 days', 'normal', 'seed scenario', seed_at, seed_at),
        ('task6', 'p7', NULL, NULL, 'contact_patient', 'in_progress', 'nurse-b', seed_at + interval '1 day', 'normal', 'seed scenario', seed_at, seed_at),
        ('task7', 'p8', NULL, NULL, 'referral_follow_up', 'open', 'nurse-b', seed_at - interval '3 days', 'high', 'seed scenario', seed_at, seed_at),
        ('task8', 'p9', NULL, NULL, 'follow_up', 'completed', 'nurse-b', seed_at - interval '2 days', 'high', 'seed scenario', seed_at, seed_at),
        ('task9', 'p10', NULL, NULL, 'contact_patient', 'open', 'nurse-b', seed_at + interval '1 day', 'normal', 'seed scenario', seed_at, seed_at),
        ('task10', 'p1', NULL, NULL, 'follow_up', 'completed', 'nurse-a', seed_at - interval '5 days', 'high', 'seed scenario', seed_at, seed_at);
END;
$seed$;

GRANT USAGE ON SCHEMA public TO debezium;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO debezium;
ALTER TABLE public.appointments REPLICA IDENTITY FULL;
CREATE PUBLICATION northstar_publication FOR TABLE public.appointments;
