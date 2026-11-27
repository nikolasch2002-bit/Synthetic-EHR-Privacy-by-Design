"""Build the marts: `python -m transform`."""

import time

from dotenv import load_dotenv

from loader.load import database_url
from transform.pseudonyms import pseudonym_key
from transform.run import build


def main() -> None:
    load_dotenv()
    started = time.perf_counter()
    linked = build(database_url(), pseudonym_key())
    print(
        f"Pseudonyms for {linked:,} patients; dbt build passed in {time.perf_counter() - started:.1f} s"
    )


if __name__ == "__main__":
    main()
