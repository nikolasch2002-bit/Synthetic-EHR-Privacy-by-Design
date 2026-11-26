"""Load the dataset: `python -m loader [--data data]`."""

import argparse
import time
from pathlib import Path

from loader.load import database_url, load


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load the generated CSV files into Postgres."
    )
    parser.add_argument("--data", type=Path, default=Path("data"))
    args = parser.parse_args()
    started = time.perf_counter()
    for table, rows in load(args.data, database_url()).items():
        print(f"{rows:>10,}  {table}")
    print(f"Loaded in {time.perf_counter() - started:.1f} s")


if __name__ == "__main__":
    main()
