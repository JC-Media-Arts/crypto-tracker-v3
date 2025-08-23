#!/usr/bin/env python3
"""
Updated dashboard endpoint that uses cached strategy status
This replaces the slow calculation with fast cache lookups
"""

UPDATED_ENDPOINT = '''
@app.route("/api/strategy-status")
def get_strategy_status():
    """Get cached strategy status - no more timeouts!"""
    try:
        supabase = SupabaseClient()

        # Get cached strategy status (instant!)
        cache_result = (
            supabase.client.table("strategy_status_cache")
            .select("*")
            .order("strategy_name")
            .order("readiness", desc=True)
            .execute()
        )

        # Get market summary cache
        summary_result = (
            supabase.client.table("market_summary_cache")
            .select("*")
            .order("calculated_at", desc=True)
            .limit(1)
            .execute()
        )

        # Organize results by strategy
        strategy_status = {
            "swing": {
                "name": "SWING",
                "thresholds": {
                    "breakout_threshold": "2.0%",
                    "volume_spike": "1.5x average",
                    "rsi_range": "60-70 optimal",
                },
                "candidates": []
            },
            "channel": {
                "name": "CHANNEL",
                "thresholds": {
                    "buy_zone": "Bottom 35% of channel",
                    "sell_zone": "Top 35% of channel",
                    "channel_width": "3-20% range",
                },
                "candidates": []
            },
            "dca": {
                "name": "DCA",
                "thresholds": {
                    "drop_threshold": "-3.5% from recent high",
                    "lookback": "20 bars",
                },
                "candidates": []
            }
        }

        # Process cached results
        if cache_result.data:
            for entry in cache_result.data:
                candidate = {
                    "symbol": entry["symbol"],
                    "readiness": float(entry["readiness"]),
                    "current_price": f"${float(entry['current_price']):.2f}" if float(entry["current_price"]) > 1 else f"${float(entry['current_price']):.4f}",
                    "details": entry["details"],
                    "status": entry["status"]
                }

                if entry["strategy_name"] == "SWING":
                    strategy_status["swing"]["candidates"].append(candidate)
                elif entry["strategy_name"] == "CHANNEL":
                    strategy_status["channel"]["candidates"].append(candidate)
                elif entry["strategy_name"] == "DCA":
                    strategy_status["dca"]["candidates"].append(candidate)

            # Limit to top 5 per strategy
            strategy_status["swing"]["candidates"] = strategy_status["swing"]["candidates"][:5]
            strategy_status["channel"]["candidates"] = strategy_status["channel"]["candidates"][:5]
            strategy_status["dca"]["candidates"] = strategy_status["dca"]["candidates"][:5]

        # Add market summary
        if summary_result.data:
            summary = summary_result.data[0]
            strategy_status["market_summary"] = {
                "condition": summary["condition"],
                "best_strategy": summary["best_strategy"],
                "notes": summary["notes"]
            }
        else:
            strategy_status["market_summary"] = {
                "condition": "CALCULATING",
                "best_strategy": "WAIT",
                "notes": "Pre-calculator is warming up..."
            }

        return jsonify(strategy_status)

    except Exception as e:
        logger.error(f"Error getting cached strategy status: {e}")

        # Return empty status on error
        return jsonify({
            "swing": {"name": "SWING", "thresholds": {}, "candidates": []},
            "channel": {"name": "CHANNEL", "thresholds": {}, "candidates": []},
            "dca": {"name": "DCA", "thresholds": {}, "candidates": []},
            "market_summary": {
                "condition": "ERROR",
                "best_strategy": "WAIT",
                "notes": f"Error: {str(e)[:100]}"
            }
        })
'''

print("=" * 60)
print("DASHBOARD UPDATE INSTRUCTIONS")
print("=" * 60)
print("\n1. First, run the migration in Supabase SQL Editor:")
print("   migrations/025_fix_dashboard_performance.sql")
print("\n2. Test the pre-calculator locally:")
print("   python scripts/strategy_precalculator.py")
print("\n3. Replace the get_strategy_status() function in live_dashboard.py")
print("   with the code above")
print("\n4. Deploy the pre-calculator to Railway as a new service")
print("\n5. Push changes to GitHub for Railway to update dashboard")
print("\n" + "=" * 60)
