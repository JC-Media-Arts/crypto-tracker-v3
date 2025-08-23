#!/usr/bin/env python3
"""
Updated dashboard function that uses cached strategy status
Replace the get_strategy_status() function in live_dashboard.py with this
"""

CACHED_FUNCTION = '''
@app.route("/api/strategy-status")
def get_strategy_status():
    """Get cached strategy status - instant response!"""
    try:
        supabase = SupabaseClient()

        # Get cached strategy status (instant - no timeouts!)
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

        # Initialize response structure
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
                # Format price based on value
                price = float(entry["current_price"])
                if price > 1000:
                    price_str = f"${price:,.0f}"
                elif price > 1:
                    price_str = f"${price:.2f}"
                elif price > 0.01:
                    price_str = f"${price:.4f}"
                else:
                    price_str = f"${price:.8f}"

                candidate = {
                    "symbol": entry["symbol"],
                    "readiness": float(entry["readiness"]),
                    "current_price": price_str,
                    "details": entry["details"],
                    "status": entry["status"]
                }

                # Add to appropriate strategy list
                if entry["strategy_name"] == "SWING":
                    strategy_status["swing"]["candidates"].append(candidate)
                elif entry["strategy_name"] == "CHANNEL":
                    strategy_status["channel"]["candidates"].append(candidate)
                elif entry["strategy_name"] == "DCA":
                    strategy_status["dca"]["candidates"].append(candidate)

            # Sort by readiness and limit to top candidates
            strategy_status["swing"]["candidates"].sort(key=lambda x: x["readiness"], reverse=True)
            strategy_status["channel"]["candidates"].sort(key=lambda x: x["readiness"], reverse=True)
            strategy_status["dca"]["candidates"].sort(key=lambda x: x["readiness"], reverse=True)

            # Keep top 10 for each strategy
            strategy_status["swing"]["candidates"] = strategy_status["swing"]["candidates"][:10]
            strategy_status["channel"]["candidates"] = strategy_status["channel"]["candidates"][:10]
            strategy_status["dca"]["candidates"] = strategy_status["dca"]["candidates"][:10]

        # Add market summary
        if summary_result.data:
            summary = summary_result.data[0]
            strategy_status["market_summary"] = {
                "condition": summary["condition"],
                "best_strategy": summary["best_strategy"],
                "notes": summary["notes"]
            }

            # Add cache freshness indicator
            from datetime import datetime
            cache_age = datetime.now() - datetime.fromisoformat(summary["calculated_at"].replace('Z', '+00:00').replace('+00:00', ''))
            cache_minutes = int(cache_age.total_seconds() / 60)
            strategy_status["market_summary"]["cache_age"] = f"{cache_minutes} min ago"
        else:
            strategy_status["market_summary"] = {
                "condition": "CALCULATING",
                "best_strategy": "WAIT",
                "notes": "Pre-calculator warming up...",
                "cache_age": "N/A"
            }

        return jsonify(strategy_status)

    except Exception as e:
        logger.error(f"Error getting cached strategy status: {e}")

        # Return minimal status on error
        return jsonify({
            "swing": {"name": "SWING", "thresholds": {}, "candidates": []},
            "channel": {"name": "CHANNEL", "thresholds": {}, "candidates": []},
            "dca": {"name": "DCA", "thresholds": {}, "candidates": []},
            "market_summary": {
                "condition": "ERROR",
                "best_strategy": "WAIT",
                "notes": f"Cache read error: {str(e)[:100]}",
                "cache_age": "N/A"
            }
        })
'''

print("=" * 60)
print("DASHBOARD UPDATE INSTRUCTIONS")
print("=" * 60)
print("\n1. Open live_dashboard.py")
print("\n2. Find the get_strategy_status() function (around line 1465)")
print("\n3. Replace the ENTIRE function with the code above")
print("\n4. The new function:")
print("   - Reads from cache tables (instant response)")
print("   - Shows top 10 candidates per strategy")
print("   - Includes cache age indicator")
print("   - Handles all 94 symbols")
print("\n5. Save and test locally")
print("\n6. Push to GitHub for Railway deployment")
print("\n" + "=" * 60)
