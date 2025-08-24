#!/usr/bin/env python3
"""
Manual script to retrain CHANNEL strategy model
"""

from src.data.supabase_client import SupabaseClient
from src.ml.simple_retrainer import SimpleRetrainer
from loguru import logger
import json


def main():
    print("\n" + "=" * 60)
    print("MANUAL CHANNEL MODEL RETRAINING")
    print("=" * 60)

    # Initialize components
    supabase = SupabaseClient()
    retrainer = SimpleRetrainer(supabase, model_dir="models")

    # Check current status
    should_retrain, count = retrainer.should_retrain("CHANNEL")
    print(f"\nCHANNEL Strategy Status:")
    print(f"  - Completed trades available: {count}")
    print(f"  - Ready to retrain: {'✅ Yes' if should_retrain else '❌ No'}")

    if not should_retrain:
        print(
            f"\nNot enough data to retrain (need {retrainer.min_new_samples} minimum)"
        )
        return

    # Perform retraining
    print(f"\n🚀 Starting CHANNEL model training with {count} trades...")
    result = retrainer.retrain("CHANNEL")

    print(f"\n📊 Result: {result}")

    # If successful, show model details
    if "Model updated" in result or "Initial model trained" in result:
        print("\n✅ SUCCESS! Model trained successfully!")

        # Load and display metadata
        import os

        metadata_file = os.path.join("models", "channel_metadata.json")
        if os.path.exists(metadata_file):
            with open(metadata_file, "r") as f:
                metadata = json.load(f)
                print("\n📈 Model Performance:")
                print(f"  - Accuracy: {metadata.get('accuracy', 'N/A'):.2%}")
                print(f"  - Precision: {metadata.get('precision', 'N/A'):.2%}")
                print(f"  - Recall: {metadata.get('recall', 'N/A'):.2%}")
                print(f"  - F1 Score: {metadata.get('f1_score', 'N/A'):.2%}")
                print(
                    f"  - Training samples: {metadata.get('training_samples', 'N/A')}"
                )
                print(f"  - Trained at: {metadata.get('trained_at', 'N/A')}")

        print("\n🎯 What happens next:")
        print("  1. ML Analyzer will use this new model for predictions")
        print("  2. It runs continuously, analyzing 1000 scans every 5 minutes")
        print("  3. Predictions are saved to ml_predictions table")
        print("  4. You'll see improved accuracy in future trades")

        # Check Slack notification status
        from src.notifications.slack_notifier import SlackNotifier

        slack = SlackNotifier()
        if slack.enabled:
            print("\n📬 Slack notification will be sent to #reports channel")
    else:
        print(f"\n⚠️ Training did not complete: {result}")


if __name__ == "__main__":
    main()
