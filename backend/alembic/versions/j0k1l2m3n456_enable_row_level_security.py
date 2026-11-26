"""enable row level security on every public table; no access for the Supabase API roles.

Supabase publishes the `public` schema through its REST API to anyone with the project's anon key. With RLS off,
conversations, messages, leads and student details could be read or changed there directly. The API never uses that
route: it connects to Postgres as the table owner, which RLS does not restrict (no policy is added, RLS is not
forced). So enabling RLS with no policies closes the public route and changes nothing for the API.

On a database without the Supabase roles (local development, CI) only the RLS switch is applied.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "j0k1l2m3n456"
down_revision: Union[str, Sequence[str], None] = "i9j0k1l2m345"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # only tables without RLS: a table that already has RLS (and maybe its own policies) is left as it is
    op.execute("""
DO $$
DECLARE t record;
BEGIN
  FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND NOT rowsecurity LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t.tablename);
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
      EXECUTE format('REVOKE ALL ON public.%I FROM anon', t.tablename);
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
      EXECUTE format('REVOKE ALL ON public.%I FROM authenticated', t.tablename);
    END IF;
  END LOOP;
END $$;
""")
    # Tables created later (by the API at startup, or by a future migration) get RLS too.
    op.execute("""
CREATE OR REPLACE FUNCTION public.sru_enable_rls_on_new_tables() RETURNS event_trigger
LANGUAGE plpgsql AS $$
DECLARE obj record;
BEGIN
  FOR obj IN SELECT * FROM pg_event_trigger_ddl_commands()
             WHERE command_tag = 'CREATE TABLE' AND schema_name = 'public' LOOP
    EXECUTE format('ALTER TABLE %s ENABLE ROW LEVEL SECURITY', obj.object_identity);
  END LOOP;
END $$;
""")
    op.execute("""
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_event_trigger WHERE evtname = 'sru_enable_rls_on_new_tables') THEN
    BEGIN
      CREATE EVENT TRIGGER sru_enable_rls_on_new_tables ON ddl_command_end
        WHEN TAG IN ('CREATE TABLE') EXECUTE FUNCTION public.sru_enable_rls_on_new_tables();
    EXCEPTION WHEN insufficient_privilege THEN
      RAISE NOTICE 'event trigger not created (needs superuser); new tables need RLS enabled by their migration';
    END;
  END IF;
END $$;
""")


def downgrade() -> None:
    op.execute("DROP EVENT TRIGGER IF EXISTS sru_enable_rls_on_new_tables")
    op.execute("DROP FUNCTION IF EXISTS public.sru_enable_rls_on_new_tables()")
    op.execute("""
DO $$
DECLARE t record;
BEGIN
  FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
    EXECUTE format('ALTER TABLE public.%I DISABLE ROW LEVEL SECURITY', t.tablename);
  END LOOP;
END $$;
""")
