-- Task assegnabili durante una videochiamata tramite menzioni (@nome, @everyone).
-- assignee_id NULL indica una task di gruppo (creata con @everyone).
create table if not exists public.tasks (
	id uuid primary key default gen_random_uuid(),
	created_at timestamptz not null default now(),
	created_by uuid not null references auth.users (id) on delete cascade,
	assignee_id uuid references auth.users (id) on delete cascade,
	room_name text not null,
	title text not null check (char_length(title) > 0),
	done boolean not null default false
);

alter table public.tasks enable row level security;

-- Visibili a: assegnatario, tutti (se di gruppo) o creatore
-- (drop policy if exists rende lo script rieseguibile senza errori)
drop policy if exists "tasks_select" on public.tasks;
create policy "tasks_select" on public.tasks for select using (
	assignee_id = (select auth.uid())
	or assignee_id is null
	or created_by = (select auth.uid())
);

-- Ognuno può creare task a proprio nome
drop policy if exists "tasks_insert" on public.tasks;
create policy "tasks_insert" on public.tasks for insert with check (created_by = (select auth.uid()));

-- L'assegnatario (o chiunque per le task di gruppo) può aggiornarla, es. completarla
drop policy if exists "tasks_update" on public.tasks;
create policy "tasks_update" on public.tasks for update using (
	assignee_id = (select auth.uid())
	or assignee_id is null
) with check (
	assignee_id = (select auth.uid())
	or assignee_id is null
);

-- PostgREST espone nell'API solo le tabelle su cui i ruoli hanno privilegi:
-- senza questi GRANT l'API risponde "Could not find the table ... in the schema cache"
grant select, insert, update on public.tasks to authenticated;
