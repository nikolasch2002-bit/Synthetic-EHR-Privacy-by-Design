"""Generate the dataset: `python -m generator [--population N] [--out data]`."""

import argparse
import time
from pathlib import Path

from generator.config import DEFAULT_CONFIG, load_config
from generator.output import MANIFEST, write_dataset


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Write the synthetic EHR as CSV files."
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--population", type=int, help="override the config's population"
    )
    parser.add_argument("--out", type=Path, default=Path("data"))
    args = parser.parse_args()

    config = load_config(args.config)
    started = time.perf_counter()
    counts = write_dataset(config, args.out, args.population)
    for name, rows in counts.items():
        print(f"{rows:>10,}  {name}")
    print(
        f"Wrote {args.out / MANIFEST} in {time.perf_counter() - started:.1f} s (seed {config.seed})"
    )


if __name__ == "__main__":
    main()
