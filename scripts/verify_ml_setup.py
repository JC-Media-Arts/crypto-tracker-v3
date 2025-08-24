#!/usr/bin/env python3
"""
Script to verify ML setup after migration 026
"""

from src.data.supabase_client import SupabaseClient
from collections import Counter


def main():
    db = SupabaseClient()

    print("=== DCA TRADE DETAILS ===\n")

    # Get the DCA trade
    dca_trade = (
        db.client.table("paper_trades").select("*").eq("strategy_name", "DCA").execute()
    )
    if dca_trade.data:
        trade = dca_trade.data[0]
        print("DCA Trade found:")
        print(f"  - Symbol: {trade.get('symbol')}")
        print(f"  - Side: {trade.get('side')}")
        print(f"  - Created: {trade.get('created_at')}")
        print(f"  - Price: ${trade.get('price')}")
        print(f"  - Amount: {trade.get('amount')}")
        print(f"  - Status: {trade.get('status', 'OPEN')}")
        print(f"  - Exit Reason: {trade.get('exit_reason', 'None - still open')}")

    print("\n=== TESTING ML VIEWS ===\n")

    # Test the completed_trades_for_ml view
    completed = db.client.table("completed_trades_for_ml").select("*").execute()
    print(f"completed_trades_for_ml view: {len(completed.data)} trades")

    # Group by strategy
    if completed.data:
        strategies = Counter([t.get("strategy_name") for t in completed.data])
        for strat, count in strategies.items():
            print(f"  - {strat}: {count}")

    # Test ml_training_feedback view
    feedback = db.client.table("ml_training_feedback").select("*").limit(5).execute()
    print(f"\nml_training_feedback view: {len(feedback.data)} sample records")

    print("\n=== ML RETRAINER READINESS ===\n")

    for strategy in ["DCA", "SWING", "CHANNEL"]:
        # This matches what the ML Retrainer will see
        query = db.client.table("completed_trades_for_ml").select("*", count="exact")
        query = query.eq("strategy_name", strategy)
        result = query.execute()
        count = result.count if hasattr(result, "count") else len(result.data)

        print(f"{strategy} Strategy:")
        print(f"  Completed trades: {count}")
        print(f"  Minimum required: 20")
        status = "✅ Ready to retrain!" if count >= 20 else "❌ Needs more trades"
        print(f"  Status: {status}\n")

    # Test if ML Retrainer can trigger
    print("=== TESTING ML RETRAINER TRIGGER ===\n")
    from src.ml.simple_retrainer import SimpleRetrainer

    retrainer = SimpleRetrainer(db)
    for strategy in ["DCA", "SWING", "CHANNEL"]:
        should_retrain, count = retrainer.should_retrain(strategy)
        print(f"{strategy}: should_retrain={should_retrain}, new_trades={count}")


if __name__ == "__main__":
    main()
