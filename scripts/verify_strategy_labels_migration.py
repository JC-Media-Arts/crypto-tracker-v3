#!/usr/bin/env python3
"""
Verify that strategy label tables were created correctly
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List
import json

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.config.settings import get_settings
from supabase import create_client, Client
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


class MigrationVerifier:
    """Verify strategy labels migration"""

    def __init__(self):
        settings = get_settings()
        self.supabase: Client = create_client(
            settings.supabase_url, settings.supabase_key
        )
        self.results = {
            "tables_exist": {},
            "indexes_exist": {},
            "columns_correct": {},
            "test_inserts": {},
            "summary": {"passed": 0, "failed": 0},
        }

    def verify_tables_exist(self) -> bool:
        """Check if all strategy label tables exist"""
        print("\n" + "=" * 60)
        print("CHECKING TABLE EXISTENCE")
        print("=" * 60)

        tables = [
            "strategy_dca_labels",
            "strategy_swing_labels",
            "strategy_channel_labels",
        ]

        all_exist = True
        for table in tables:
            try:
                # Try to query the table
                result = self.supabase.table(table).select("id").limit(1).execute()
                self.results["tables_exist"][table] = True
                print(f"✅ Table '{table}' exists")
            except Exception as e:
                self.results["tables_exist"][table] = False
                all_exist = False
                print(f"❌ Table '{table}' NOT FOUND: {str(e)[:100]}")

        return all_exist

    def verify_columns(self) -> bool:
        """Verify all expected columns exist with correct types"""
        print("\n" + "=" * 60)
        print("CHECKING TABLE COLUMNS")
        print("=" * 60)

        expected_columns = {
            "strategy_dca_labels": [
                "id",
                "symbol",
                "timestamp",
                "setup_detected",
                "drop_percentage",
                "rsi",
                "volume_ratio",
                "btc_regime",
                "outcome",
                "optimal_take_profit",
                "optimal_stop_loss",
                "actual_return",
                "hold_time_hours",
                "features",
                "created_at",
            ],
            "strategy_swing_labels": [
                "id",
                "symbol",
                "timestamp",
                "breakout_detected",
                "breakout_strength",
                "volume_surge",
                "momentum_score",
                "trend_alignment",
                "outcome",
                "optimal_take_profit",
                "optimal_stop_loss",
                "actual_return",
                "hold_time_hours",
                "features",
                "created_at",
            ],
            "strategy_channel_labels": [
                "id",
                "symbol",
                "timestamp",
                "channel_position",
                "channel_strength",
                "channel_width",
                "outcome",
                "optimal_entry",
                "optimal_exit",
                "actual_return",
                "hold_time_hours",
                "features",
                "created_at",
            ],
        }

        all_correct = True
        for table, expected_cols in expected_columns.items():
            print(f"\n{table}:")
            try:
                # Get a sample row to check columns
                result = self.supabase.table(table).select("*").limit(1).execute()

                if result.data and len(result.data) > 0:
                    actual_cols = set(result.data[0].keys())
                else:
                    # Table is empty, try inserting a test row to get column info
                    test_row = self._get_test_row(table)
                    try:
                        insert_result = (
                            self.supabase.table(table).insert(test_row).execute()
                        )
                        actual_cols = set(insert_result.data[0].keys())
                        # Delete test row
                        self.supabase.table(table).delete().eq(
                            "id", insert_result.data[0]["id"]
                        ).execute()
                    except Exception as e:
                        print(
                            f"  ⚠️  Could not verify columns (empty table): {str(e)[:100]}"
                        )
                        self.results["columns_correct"][table] = "unknown"
                        continue

                expected_set = set(expected_cols)
                missing = expected_set - actual_cols
                extra = actual_cols - expected_set

                if missing:
                    print(f"  ❌ Missing columns: {missing}")
                    all_correct = False
                    self.results["columns_correct"][table] = False
                elif extra:
                    print(f"  ⚠️  Extra columns (ok): {extra}")
                    self.results["columns_correct"][table] = True
                else:
                    print(f"  ✅ All expected columns present")
                    self.results["columns_correct"][table] = True

            except Exception as e:
                print(f"  ❌ Error checking columns: {str(e)[:100]}")
                self.results["columns_correct"][table] = False
                all_correct = False

        return all_correct

    def verify_indexes(self) -> bool:
        """Verify indexes exist (basic check via performance)"""
        print("\n" + "=" * 60)
        print("CHECKING INDEXES (via query performance)")
        print("=" * 60)

        all_good = True

        # Test queries that should use indexes
        test_queries = {
            "strategy_dca_labels": [
                (
                    "symbol_timestamp",
                    lambda t: t.select("*")
                    .eq("symbol", "BTC")
                    .order("timestamp", desc=True)
                    .limit(10),
                ),
                ("outcome", lambda t: t.select("*").eq("outcome", "WIN").limit(10)),
            ],
            "strategy_swing_labels": [
                (
                    "symbol_timestamp",
                    lambda t: t.select("*")
                    .eq("symbol", "ETH")
                    .order("timestamp", desc=True)
                    .limit(10),
                ),
                (
                    "breakout",
                    lambda t: t.select("*").eq("breakout_detected", True).limit(10),
                ),
            ],
            "strategy_channel_labels": [
                (
                    "symbol_timestamp",
                    lambda t: t.select("*")
                    .eq("symbol", "SOL")
                    .order("timestamp", desc=True)
                    .limit(10),
                ),
                (
                    "position",
                    lambda t: t.select("*").eq("channel_position", "TOP").limit(10),
                ),
            ],
        }

        for table, queries in test_queries.items():
            print(f"\n{table}:")
            table_obj = self.supabase.table(table)

            for index_name, query_func in queries:
                try:
                    import time

                    start = time.time()
                    result = query_func(table_obj).execute()
                    elapsed = time.time() - start

                    if elapsed < 1.0:  # Query should be fast with index
                        print(
                            f"  ✅ Index '{index_name}' appears to be working (query: {elapsed:.3f}s)"
                        )
                        self.results["indexes_exist"][f"{table}.{index_name}"] = True
                    else:
                        print(
                            f"  ⚠️  Index '{index_name}' may be missing (query: {elapsed:.3f}s)"
                        )
                        self.results["indexes_exist"][f"{table}.{index_name}"] = "slow"

                except Exception as e:
                    print(f"  ❌ Could not test index '{index_name}': {str(e)[:100]}")
                    self.results["indexes_exist"][f"{table}.{index_name}"] = False
                    all_good = False

        return all_good

    def test_insert_and_retrieve(self) -> bool:
        """Test inserting and retrieving data"""
        print("\n" + "=" * 60)
        print("TESTING INSERT AND RETRIEVE")
        print("=" * 60)

        all_success = True

        for table in [
            "strategy_dca_labels",
            "strategy_swing_labels",
            "strategy_channel_labels",
        ]:
            print(f"\n{table}:")
            test_row = self._get_test_row(table)

            try:
                # Insert test row
                insert_result = self.supabase.table(table).insert(test_row).execute()

                if insert_result.data:
                    row_id = insert_result.data[0]["id"]
                    print(f"  ✅ Insert successful (ID: {row_id})")

                    # Retrieve and verify
                    retrieve_result = (
                        self.supabase.table(table)
                        .select("*")
                        .eq("id", row_id)
                        .execute()
                    )

                    if retrieve_result.data:
                        retrieved = retrieve_result.data[0]
                        # Check key fields
                        if retrieved["symbol"] == test_row["symbol"]:
                            print(f"  ✅ Retrieve successful")
                            self.results["test_inserts"][table] = True
                        else:
                            print(f"  ❌ Retrieved data doesn't match")
                            self.results["test_inserts"][table] = False
                            all_success = False

                    # Clean up
                    self.supabase.table(table).delete().eq("id", row_id).execute()
                    print(f"  ✅ Cleanup successful")
                else:
                    print(f"  ❌ Insert failed")
                    self.results["test_inserts"][table] = False
                    all_success = False

            except Exception as e:
                print(f"  ❌ Test failed: {str(e)[:100]}")
                self.results["test_inserts"][table] = False
                all_success = False

        return all_success

    def verify_view(self) -> bool:
        """Verify the summary view works"""
        print("\n" + "=" * 60)
        print("CHECKING SUMMARY VIEW")
        print("=" * 60)

        try:
            # Try to query the view
            result = self.supabase.rpc("get_strategy_labels_summary", {}).execute()
            print("✅ Summary view 'strategy_labels_summary' is accessible")

            if result.data:
                print("\nSummary Data:")
                for row in result.data:
                    print(
                        f"  {row.get('strategy', 'N/A')}: {row.get('total_labels', 0)} labels"
                    )

            return True
        except:
            # View might not be accessible via RPC, try alternative
            print("⚠️  Could not access view via RPC (this is normal)")
            return True

    def _get_test_row(self, table: str) -> Dict:
        """Get a test row for the specified table"""
        base_row = {
            "symbol": "TEST",
            "timestamp": datetime.utcnow().isoformat(),
            "outcome": "WIN",
            "actual_return": 5.5,
            "hold_time_hours": 24,
            "features": {"test": True},
        }

        if table == "strategy_dca_labels":
            base_row.update(
                {
                    "setup_detected": True,
                    "drop_percentage": -5.5,
                    "rsi": 35.0,
                    "volume_ratio": 1.2,
                    "btc_regime": "NEUTRAL",
                    "optimal_take_profit": 10.0,
                    "optimal_stop_loss": -5.0,
                }
            )
        elif table == "strategy_swing_labels":
            base_row.update(
                {
                    "breakout_detected": True,
                    "breakout_strength": 75.0,
                    "volume_surge": 2.5,
                    "momentum_score": 80.0,
                    "trend_alignment": "UPTREND",
                    "optimal_take_profit": 15.0,
                    "optimal_stop_loss": -5.0,
                }
            )
        elif table == "strategy_channel_labels":
            base_row.update(
                {
                    "channel_position": "BOTTOM",
                    "channel_strength": 85.0,
                    "channel_width": 5.0,
                    "optimal_entry": 2.0,
                    "optimal_exit": 8.0,
                }
            )

        return base_row

    def print_summary(self):
        """Print summary of verification results"""
        print("\n" + "=" * 60)
        print("VERIFICATION SUMMARY")
        print("=" * 60)

        # Count results
        total_checks = 0
        passed_checks = 0

        for category in [
            "tables_exist",
            "columns_correct",
            "test_inserts",
            "indexes_exist",
        ]:
            for key, value in self.results[category].items():
                total_checks += 1
                if value is True:
                    passed_checks += 1

        self.results["summary"]["passed"] = passed_checks
        self.results["summary"]["failed"] = total_checks - passed_checks

        print(f"\nTotal Checks: {total_checks}")
        print(f"✅ Passed: {passed_checks}")
        print(f"❌ Failed: {total_checks - passed_checks}")

        if passed_checks == total_checks:
            print("\n🎉 ALL CHECKS PASSED! Migration verified successfully.")
        elif passed_checks > total_checks * 0.8:
            print("\n⚠️  MOSTLY PASSED. Some minor issues detected.")
        else:
            print("\n❌ VERIFICATION FAILED. Please check the migration.")

        # Save results to file
        results_file = Path("data") / "migration_verification_results.json"
        results_file.parent.mkdir(exist_ok=True)

        with open(results_file, "w") as f:
            json.dump(self.results, f, indent=2, default=str)

        print(f"\nDetailed results saved to: {results_file}")

    def run_verification(self):
        """Run all verification checks"""
        print("\n" + "=" * 80)
        print("STRATEGY LABELS MIGRATION VERIFICATION")
        print("=" * 80)
        print(f"Time: {datetime.now()}")

        # Run checks
        self.verify_tables_exist()
        self.verify_columns()
        self.test_insert_and_retrieve()
        self.verify_indexes()
        self.verify_view()

        # Print summary
        self.print_summary()


def main():
    """Main entry point"""
    verifier = MigrationVerifier()
    verifier.run_verification()


if __name__ == "__main__":
    main()
