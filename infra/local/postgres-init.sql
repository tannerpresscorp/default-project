-- Development only. The application role must not own tables or bypass RLS.
CREATE ROLE platform_app LOGIN PASSWORD 'local_app_only' NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
CREATE DATABASE platform_test;
\connect platform
GRANT CONNECT ON DATABASE platform TO platform_app;
GRANT USAGE ON SCHEMA public TO platform_app;
ALTER DEFAULT PRIVILEGES FOR ROLE platform_migrator IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO platform_app;
\connect platform_test
GRANT CONNECT ON DATABASE platform_test TO platform_app;
GRANT USAGE ON SCHEMA public TO platform_app;
ALTER DEFAULT PRIVILEGES FOR ROLE platform_migrator IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO platform_app;
