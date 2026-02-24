"""
CLI Runner for the Auto-Discovery Agent.

Usage:
    # Chạy cào 10 công thức mới từ tất cả website
    python run_auto_discovery.py --max-recipes 10

    # Chạy với website cụ thể
    python run_auto_discovery.py --sites cooky savoury --max-recipes 5

    # Chạy dry-run (chỉ tìm + trích xuất, KHÔNG insert)
    python run_auto_discovery.py --dry-run --max-recipes 3
"""
import asyncio
import argparse
import os
import sys

sys.path.append(os.getcwd())


async def main():
    parser = argparse.ArgumentParser(
        description="🤖 Menu Green Auto-Discovery Agent — Tự động cào công thức nấu ăn"
    )
    parser.add_argument(
        "--sites",
        nargs="+",
        default=None,
        choices=["cooky", "savoury", "cookpad"],
        help="Website mục tiêu (mặc định: tất cả)",
    )
    parser.add_argument(
        "--max-recipes",
        type=int,
        default=10,
        help="Số công thức tối đa (mặc định: 10)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Thời gian chờ giữa các request (giây, mặc định: 2.0)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Chỉ tìm + trích xuất, KHÔNG insert vào database",
    )

    args = parser.parse_args()

    from app.data_pipeline.auto_discovery import AutoDiscoveryAgent

    agent = AutoDiscoveryAgent(
        sites=args.sites,
        delay_seconds=args.delay,
        max_recipes_per_run=args.max_recipes,
    )

    stats = await agent.run(
        max_recipes=args.max_recipes,
        dry_run=args.dry_run,
    )

    # Exit code: 0 if any recipes stored, 1 otherwise
    sys.exit(0 if stats["stored"] > 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
