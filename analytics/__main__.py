"""Answer the questions: `python -m analytics` writes analytics/RESULTS.md."""

from analytics.run import write_results
from loader.load import database_url

if __name__ == "__main__":
    write_results(database_url())
    print("Wrote analytics/RESULTS.md")
