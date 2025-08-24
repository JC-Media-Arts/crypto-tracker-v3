#!/usr/bin/env python3
"""
Simplified test for Strategy Manager
Uses mock components to test orchestration logic
"""

import asyncio
import json
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional
from loguru import logger

# Configure logger
logger.add("logs/strategy_manager_simple_test.log", rotation="10 MB")


class StrategyType(Enum):
    DCA = "DCA"
    SWING = "SWING"


@dataclass
class StrategySignal:
    """Represents a trading signal from any strategy"""

    strategy_type: StrategyType
    symbol: str
    confidence: float
    expected_value: float
    required_capital: float
    setup_data: Dict
    timestamp: datetime
    expires_at: datetime
    priority_score: float = 0.0

    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at


class SimpleStrategyManager:
    """Simplified Strategy Manager for testing orchestration logic"""

    def __init__(self, config: Dict):
        self.config = config
        self.total_capital = config.get("total_capital", 1000)
        self.dca_allocation = config.get("dca_allocation", 0.6)
        self.swing_allocation = config.get("swing_allocation", 0.4)

        self.dca_used = 0.0
        self.swing_used = 0.0
        self.active_positions = {}

        self.performance = {
            StrategyType.DCA: {"wins": 0, "losses": 0, "pnl": 0},
            StrategyType.SWING: {"wins": 0, "losses": 0, "pnl": 0},
        }

        logger.info(f"Manager initialized with ${self.total_capital} capital")
        logger.info(
            f"Allocation: DCA {self.dca_allocation:.0%}, Swing {self.swing_allocation:.0%}"
        )

    def create_mock_signals(self) -> List[StrategySignal]:
        """Create mock signals for testing"""
        signals = []

        # DCA signal for BTC (oversold)
        signals.append(
            StrategySignal(
                strategy_type=StrategyType.DCA,
                symbol="BTC",
                confidence=0.68,
                expected_value=5.2,
                required_capital=500,  # 5 levels x $100
                setup_data={"drop": -5.5, "rsi": 28},
                timestamp=datetime.now(),
                expires_at=datetime.now() + timedelta(minutes=15),
                priority_score=0.72,
            )
        )

        # Swing signal for ETH (breakout)
        signals.append(
            StrategySignal(
                strategy_type=StrategyType.SWING,
                symbol="ETH",
                confidence=0.71,
                expected_value=8.5,
                required_capital=200,
                setup_data={"breakout": 3.2, "volume": 2.5},
                timestamp=datetime.now(),
                expires_at=datetime.now() + timedelta(minutes=5),
                priority_score=0.78,
            )
        )

        # Conflicting Swing signal for BTC (to test conflict resolution)
        signals.append(
            StrategySignal(
                strategy_type=StrategyType.SWING,
                symbol="BTC",
                confidence=0.65,  # Lower than DCA
                expected_value=6.0,
                required_capital=200,
                setup_data={"breakout": 2.1, "volume": 1.8},
                timestamp=datetime.now(),
                expires_at=datetime.now() + timedelta(minutes=5),
                priority_score=0.68,
            )
        )

        # DCA signal for SOL (very oversold)
        signals.append(
            StrategySignal(
                strategy_type=StrategyType.DCA,
                symbol="SOL",
                confidence=0.75,
                expected_value=7.8,
                required_capital=500,
                setup_data={"drop": -6.2, "rsi": 25},
                timestamp=datetime.now(),
                expires_at=datetime.now() + timedelta(minutes=15),
                priority_score=0.82,
            )
        )

        return signals

    def resolve_conflicts(self, signals: List[StrategySignal]) -> List[StrategySignal]:
        """Resolve conflicts between signals"""
        resolved = []
        symbol_signals = {}

        # Group by symbol
        for signal in signals:
            if signal.symbol not in symbol_signals:
                symbol_signals[signal.symbol] = []
            symbol_signals[signal.symbol].append(signal)

        # Resolve conflicts
        for symbol, sigs in symbol_signals.items():
            if len(sigs) == 1:
                resolved.append(sigs[0])
            else:
                # Higher confidence wins (as per MASTER_PLAN)
                winner = max(sigs, key=lambda x: x.confidence)
                logger.info(
                    f"Conflict for {symbol}: {len(sigs)} signals, "
                    f"{winner.strategy_type.value} wins with {winner.confidence:.2f} confidence"
                )
                resolved.append(winner)

        return resolved

    def apply_capital_constraints(
        self, signals: List[StrategySignal]
    ) -> List[StrategySignal]:
        """Apply capital allocation constraints"""
        approved = []
        temp_dca = self.dca_used
        temp_swing = self.swing_used

        # Sort by priority
        signals.sort(key=lambda x: x.priority_score, reverse=True)

        for signal in signals:
            if signal.strategy_type == StrategyType.DCA:
                available = (self.total_capital * self.dca_allocation) - temp_dca
                if signal.required_capital <= available:
                    approved.append(signal)
                    temp_dca += signal.required_capital
                    logger.info(
                        f"Approved DCA for {signal.symbol}: ${signal.required_capital:.0f} "
                        f"(${available - signal.required_capital:.0f} remaining)"
                    )
                else:
                    logger.warning(
                        f"Rejected DCA for {signal.symbol}: needs ${signal.required_capital:.0f}, "
                        f"only ${available:.0f} available"
                    )

            elif signal.strategy_type == StrategyType.SWING:
                available = (self.total_capital * self.swing_allocation) - temp_swing
                if signal.required_capital <= available:
                    approved.append(signal)
                    temp_swing += signal.required_capital
                    logger.info(
                        f"Approved Swing for {signal.symbol}: ${signal.required_capital:.0f} "
                        f"(${available - signal.required_capital:.0f} remaining)"
                    )
                else:
                    logger.warning(
                        f"Rejected Swing for {signal.symbol}: needs ${signal.required_capital:.0f}, "
                        f"only ${available:.0f} available"
                    )

        return approved

    def execute_signals(self, signals: List[StrategySignal]) -> Dict:
        """Simulate signal execution"""
        results = {"executed": [], "skipped": []}

        for signal in signals:
            if signal.symbol in self.active_positions:
                results["skipped"].append(signal)
                logger.info(f"Skipped {signal.symbol}: position already exists")
            else:
                self.active_positions[signal.symbol] = signal
                if signal.strategy_type == StrategyType.DCA:
                    self.dca_used += signal.required_capital
                else:
                    self.swing_used += signal.required_capital
                results["executed"].append(signal)
                logger.info(
                    f"Executed {signal.strategy_type.value} for {signal.symbol}: "
                    f"${signal.required_capital:.0f}"
                )

        return results

    def update_performance(self, symbol: str, pnl: float, is_win: bool):
        """Update performance metrics"""
        if symbol in self.active_positions:
            signal = self.active_positions[symbol]
            strategy = signal.strategy_type

            if is_win:
                self.performance[strategy]["wins"] += 1
            else:
                self.performance[strategy]["losses"] += 1

            self.performance[strategy]["pnl"] += pnl

            # Free capital
            if strategy == StrategyType.DCA:
                self.dca_used -= signal.required_capital
            else:
                self.swing_used -= signal.required_capital

            del self.active_positions[symbol]

            logger.info(
                f"{strategy.value} trade closed for {symbol}: "
                f"{'WIN' if is_win else 'LOSS'} ${pnl:+.2f}"
            )

    def get_status(self) -> Dict:
        """Get manager status"""
        return {
            "capital": {
                "total": self.total_capital,
                "dca_allocated": self.total_capital * self.dca_allocation,
                "dca_used": self.dca_used,
                "dca_available": (self.total_capital * self.dca_allocation)
                - self.dca_used,
                "swing_allocated": self.total_capital * self.swing_allocation,
                "swing_used": self.swing_used,
                "swing_available": (self.total_capital * self.swing_allocation)
                - self.swing_used,
            },
            "positions": len(self.active_positions),
            "performance": self.performance,
        }


def test_orchestration():
    """Test the orchestration logic"""
    logger.info("=" * 60)
    logger.info("STRATEGY MANAGER ORCHESTRATION TEST")
    logger.info("=" * 60)

    # Configuration from MASTER_PLAN.md
    config = {
        "total_capital": 1000,
        "dca_allocation": 0.6,  # 60% = $600
        "swing_allocation": 0.4,  # 40% = $400
    }

    manager = SimpleStrategyManager(config)

    # Test 1: Create signals
    logger.info("\n📊 TEST 1: Signal Generation")
    logger.info("-" * 40)
    signals = manager.create_mock_signals()
    logger.info(f"Generated {len(signals)} signals:")
    for sig in signals:
        logger.info(
            f"  {sig.symbol} - {sig.strategy_type.value}: "
            f"conf={sig.confidence:.2f}, EV=${sig.expected_value:.1f}, "
            f"capital=${sig.required_capital:.0f}"
        )

    # Test 2: Conflict resolution
    logger.info("\n⚔️ TEST 2: Conflict Resolution")
    logger.info("-" * 40)
    resolved = manager.resolve_conflicts(signals)
    logger.info(f"After conflict resolution: {len(resolved)} signals")

    # Test 3: Capital constraints
    logger.info("\n💰 TEST 3: Capital Constraints")
    logger.info("-" * 40)
    approved = manager.apply_capital_constraints(resolved)
    logger.info(f"After capital constraints: {len(approved)} signals approved")

    # Test 4: Execute signals
    logger.info("\n🚀 TEST 4: Signal Execution")
    logger.info("-" * 40)
    results = manager.execute_signals(approved)
    logger.info(
        f"Executed: {len(results['executed'])}, Skipped: {len(results['skipped'])}"
    )

    # Test 5: Show status
    logger.info("\n📈 TEST 5: Current Status")
    logger.info("-" * 40)
    status = manager.get_status()
    logger.info("Capital Status:")
    logger.info(
        f"  DCA: ${status['capital']['dca_used']:.0f} used of ${status['capital']['dca_allocated']:.0f} "
        f"(${status['capital']['dca_available']:.0f} available)"
    )
    logger.info(
        f"  Swing: ${status['capital']['swing_used']:.0f} used of ${status['capital']['swing_allocated']:.0f} "
        f"(${status['capital']['swing_available']:.0f} available)"
    )
    logger.info(f"  Active positions: {status['positions']}")

    # Test 6: Simulate trade outcomes
    logger.info("\n💸 TEST 6: Trade Outcomes")
    logger.info("-" * 40)
    manager.update_performance("BTC", 50.0, True)  # DCA win
    manager.update_performance("ETH", -30.0, False)  # Swing loss
    manager.update_performance("SOL", 80.0, True)  # DCA win

    # Final status
    logger.info("\n🏁 FINAL STATUS")
    logger.info("-" * 40)
    final_status = manager.get_status()

    for strategy in [StrategyType.DCA, StrategyType.SWING]:
        perf = final_status["performance"][strategy]
        total = perf["wins"] + perf["losses"]
        win_rate = perf["wins"] / total if total > 0 else 0
        logger.info(f"{strategy.value} Performance:")
        logger.info(f"  Trades: {total} (W:{perf['wins']}, L:{perf['losses']})")
        logger.info(f"  Win Rate: {win_rate:.1%}")
        logger.info(f"  P&L: ${perf['pnl']:+.2f}")

    logger.info("\n✅ TEST COMPLETE!")
    logger.info("=" * 60)


if __name__ == "__main__":
    test_orchestration()
