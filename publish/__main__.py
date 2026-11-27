"""Publish marts_public: `python -m publish`.

Needs HOSTED_DATABASE_URL in .env (set up in week 8). Never printed.
"""

import os

from dotenv import load_dotenv

from loader.load import database_url
from publish.publish import publish


def main() -> None:
    load_dotenv()
    target = os.environ.get("HOSTED_DATABASE_URL")
    if not target:
        raise SystemExit("HOSTED_DATABASE_URL is not set (see README, 'Publish')")
    for table, rows in publish(database_url(), target).items():
        print(f"{rows:>6}  marts_public.{table}")


if __name__ == "__main__":
    main()
