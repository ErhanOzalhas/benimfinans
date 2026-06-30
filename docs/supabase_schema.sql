-- Benim Finans V6.1 Cloud Engine
-- Supabase SQL Editor > New Query içinde çalıştır.

create table if not exists assets (
    id bigint generated always as identity primary key,
    name text not null,
    symbol text not null unique,
    category text not null,
    currency text default 'TRY',
    manual_price_try numeric default 0,
    active boolean default true,
    archived boolean default false,
    created_at timestamptz default now()
);

create table if not exists transactions (
    id bigint generated always as identity primary key,
    tx_date date not null,
    asset_symbol text not null references assets(symbol) on delete cascade,
    action text not null,
    quantity numeric not null default 0,
    price_try numeric not null default 0,
    commission_try numeric default 0,
    note text default '',
    created_at timestamptz default now()
);

create table if not exists price_cache (
    symbol text primary key references assets(symbol) on delete cascade,
    price_try numeric default 0,
    source text default '',
    updated_at timestamptz default now()
);

create table if not exists daily_snapshots (
    snapshot_date date primary key,
    total_value_try numeric default 0,
    total_pl_try numeric default 0,
    note text default '',
    created_at timestamptz default now()
);

create table if not exists alerts (
    id bigint generated always as identity primary key,
    asset_symbol text references assets(symbol) on delete cascade,
    target_price_try numeric not null,
    direction text default 'above',
    active boolean default true,
    created_at timestamptz default now()
);

create index if not exists idx_transactions_asset_symbol on transactions(asset_symbol);
create index if not exists idx_transactions_tx_date on transactions(tx_date);
