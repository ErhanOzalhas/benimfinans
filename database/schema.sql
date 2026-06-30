create table if not exists assets (
  id bigint generated always as identity primary key,
  name text not null,
  symbol text not null,
  category text not null,
  quantity numeric default 0,
  avg_cost numeric default 0,
  manual_price numeric default 0,
  archived boolean default false,
  created_at timestamptz default now()
);

create table if not exists transactions (
  id bigint generated always as identity primary key,
  asset_id bigint references assets(id) on delete cascade,
  tx_date date not null,
  tx_type text not null,
  quantity numeric not null,
  price numeric not null,
  commission numeric default 0,
  note text,
  created_at timestamptz default now()
);

create table if not exists price_cache (
  symbol text primary key,
  price numeric,
  currency text default 'TRY',
  updated_at timestamptz default now()
);

create table if not exists daily_snapshots (
  id bigint generated always as identity primary key,
  snapshot_date date not null,
  total_value numeric default 0,
  created_at timestamptz default now()
);

create table if not exists alerts (
  id bigint generated always as identity primary key,
  asset_id bigint references assets(id) on delete cascade,
  target_price numeric not null,
  direction text not null,
  active boolean default true,
  created_at timestamptz default now()
);
