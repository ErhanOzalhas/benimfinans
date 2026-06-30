from database.supabase_client import get_supabase


def list_assets():
    supabase = get_supabase()
    result = (
        supabase
        .table("assets")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []


def add_asset(name, symbol, category, quantity=0, avg_cost=0, manual_price=0):
    supabase = get_supabase()
    payload = {
        "name": name,
        "symbol": symbol,
        "category": category,
        "quantity": quantity,
        "avg_cost": avg_cost,
        "manual_price": manual_price,
    }
    result = supabase.table("assets").insert(payload).execute()
    return result.data


def delete_asset(asset_id):
    supabase = get_supabase()
    result = supabase.table("assets").delete().eq("id", asset_id).execute()
    return result.data
