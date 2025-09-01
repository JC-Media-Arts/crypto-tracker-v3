#!/usr/bin/env python3
"""
Check which USD pairs from our list are actually available on Kraken
"""

import ccxt
import json

# Initialize Kraken exchange
exchange = ccxt.kraken()

# Load markets from Kraken
print("Fetching available markets from Kraken...")
markets = exchange.load_markets()

# Get all USD pairs available on Kraken
kraken_usd_pairs = [symbol for symbol in markets.keys() if symbol.endswith('/USD')]
print(f"\nKraken has {len(kraken_usd_pairs)} USD pairs available")

# Our current list (before my changes)
our_pairs = [
    "BTC/USD", "ETH/USD", "SOL/USD", "XRP/USD", "ADA/USD",
    "AVAX/USD", "DOGE/USD", "DOT/USD", "LINK/USD", "UNI/USD",
    "ATOM/USD", "NEAR/USD", "ALGO/USD", "AAVE/USD", "SAND/USD",
    "MANA/USD", "SHIB/USD", "TRX/USD", "BCH/USD", "APT/USD",
    "ICP/USD", "ARB/USD", "OP/USD", "CRV/USD", "MKR/USD",
    "LDO/USD", "SUSHI/USD", "COMP/USD", "SNX/USD", "INJ/USD",
    "GRT/USD", "FIL/USD", "IMX/USD", "FLOW/USD", "CHZ/USD",
    "GALA/USD", "XLM/USD", "HBAR/USD", "BNB/USD", "AXS/USD",
    "BAL/USD", "BLUR/USD", "ENS/USD", "FET/USD", "RPL/USD",
    "PEPE/USD", "WIF/USD", "BONK/USD", "FLOKI/USD", "MEME/USD",
    "POPCAT/USD", "MEW/USD", "TURBO/USD", "NEIRO/USD", "PNUT/USD",
    "GOAT/USD", "ACT/USD", "TRUMP/USD", "FARTCOIN/USD", "MOG/USD",
    "PONKE/USD", "TREMP/USD", "GIGA/USD", "HIPPO/USD", "RUNE/USD",
    "LRC/USD", "OCEAN/USD", "QNT/USD", "XMR/USD", "ZEC/USD",
    "DASH/USD", "KSM/USD", "STX/USD", "KAS/USD", "TIA/USD",
    "JTO/USD", "JUP/USD", "PYTH/USD", "WLD/USD", "ONDO/USD",
    "BEAM/USD", "SEI/USD", "PENDLE/USD", "RENDER/USD", "POL/USD",
    "TON/USD"
]

print(f"\nWe have {len(our_pairs)} pairs in our list")

# Check which of our pairs are available on Kraken
available_pairs = []
unavailable_pairs = []

for pair in our_pairs:
    if pair in kraken_usd_pairs:
        available_pairs.append(pair)
    else:
        unavailable_pairs.append(pair)

print(f"\n✅ AVAILABLE on Kraken ({len(available_pairs)} pairs):")
print("-" * 50)
for pair in sorted(available_pairs):
    print(f"  {pair}")

print(f"\n❌ NOT AVAILABLE on Kraken ({len(unavailable_pairs)} pairs):")
print("-" * 50)
for pair in sorted(unavailable_pairs):
    print(f"  {pair}")

print("\n" + "=" * 50)
print("SUMMARY:")
print(f"Keep: {len(available_pairs)} pairs")
print(f"Remove: {len(unavailable_pairs)} pairs")

# Generate the new whitelist
print("\n" + "=" * 50)
print("NEW WHITELIST (copy this to config.json):")
print("-" * 50)
print("        \"pair_whitelist\": [")
for i, pair in enumerate(available_pairs):
    if i < len(available_pairs) - 1:
        print(f'            "{pair}",')
    else:
        print(f'            "{pair}"')
print("        ],")
