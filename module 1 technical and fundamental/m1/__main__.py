"""Module 1 command-line interface."""

import argparse
import json
import os
import sys
from dataclasses import replace

import pandas as pd
from sqlalchemy.exc import SQLAlchemyError

from .features import as_of, build_dataset, research_rows
from .predict import predict_stock, prepare_scores
from .settings import ROOT, Settings
from .sources import DataUnavailable, compare_prices, database, fetch_pypsx, read_sources, ticker
from .training import train_all, validate_version, write_json

PROCESSED = ROOT / "data" / "processed"


def print_json(value):
    print(json.dumps(value, indent=2, default=str))


def evidence():
    import importlib.util

    from .sources import project_config

    config = project_config()
    return {
        "sdk_installed": importlib.util.find_spec("pypsx") is not None,
        "credentials_configured": all(config.get(key) for key in ("PYPSX_API_KEY_ID", "PYPSX_API_SECRET_KEY")),
        "policy": "Raw OHLCV overlap and gap audit only. Database supplies prediction and training prices.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("inspect", "build", "train"):
        command = commands.add_parser(name)
        command.add_argument("--as-of", help="ISO 8601 timestamp with UTC offset")
        if name != "inspect":
            command.add_argument("--version", required=True)
            command.add_argument("--bearish", type=float, default=-3.0)
            command.add_argument("--bullish", type=float, default=3.0)
    command = commands.add_parser("check-pypsx")
    command.add_argument("ticker")
    command.add_argument("--start", required=True)
    command.add_argument("--end", required=True)
    command.add_argument("--version", required=True)
    for name in ("predict", "explain"):
        command = commands.add_parser(name)
        command.add_argument("ticker")
        command.add_argument("--as-of")
        command.add_argument("--version", default=os.getenv("MODULE1_MODEL_VERSION", "combined_v1"))
        command.add_argument("--check-pypsx", action="store_true")
    command = commands.add_parser("scores")
    command.add_argument("ticker")
    command.add_argument("--as-of")
    args = parser.parse_args()
    try:
        if args.command == "scores":
            print_json(prepare_scores(args.ticker, args.as_of))
            return 0
        if args.command in {"predict", "explain"}:
            result = predict_stock(args.ticker, args.as_of, version=args.version, check_pypsx=args.check_pypsx)
            if args.command == "explain":
                path = ROOT / "artifacts" / "plots" / result["model_version"] / "local"
                path.mkdir(parents=True, exist_ok=True)
                date = result["prediction_timestamp"].date()
                destination = path / f"{result['ticker']}_{date}.json"
                write_json(destination, result)
                print(destination)
            else:
                print_json(result)
            return 0
        if args.command == "check-pypsx":
            symbol = ticker(args.ticker)
            version = validate_version(args.version)
            start, end = pd.Timestamp(args.start).date(), pd.Timestamp(args.end).date()
            with database() as conn:
                primary, *_ = read_sources(conn, symbol, end)
            secondary = fetch_pypsx(symbol, start, end)
            primary = primary[pd.to_datetime(primary["trading_date"]).ge(pd.Timestamp(start))]
            audit, conflicts = compare_prices(primary, secondary)
            output = ROOT / "data" / "pypsx" / version
            output.mkdir(parents=True, exist_ok=False)
            secondary.to_csv(output / f"{symbol}.csv", index=False)
            conflicts.to_csv(output / "conflicts.csv", index=False)
            write_json(output / "audit.json", {"ticker": symbol, "start": start, "end": end, **audit})
            print_json(audit)
            return 0
        cutoff = as_of(args.as_of)
        if cutoff > as_of():
            raise ValueError("as-of date is in the future")
        settings = Settings()
        if args.command != "inspect":
            validate_version(args.version)
            settings = replace(settings, bearish=args.bearish, bullish=args.bullish)
        with database() as conn:
            sources = read_sources(conn, cutoff=cutoff.date())
        data, metadata = build_dataset(sources, cutoff, settings, research_only=True)
        metadata.update(as_of=cutoff, pypsx=evidence())
        if args.command == "inspect":
            print_json(metadata)
        elif args.command == "build":
            output = PROCESSED / args.version
            output.mkdir(parents=True, exist_ok=False)
            usable = research_rows(data)
            usable.rename(columns={"symbol": "ticker"}).to_csv(output / "combined.csv.gz", index=False)
            write_json(output / "coverage.json", metadata)
            print_json(metadata)
            if usable.empty:
                raise DataUnavailable("Combined dataset has zero eligible rows. See coverage.json.")
        else:
            print_json(train_all(data, metadata, args.version, settings))
        return 0
    except KeyError:
        print("Unknown PSX ticker or missing required source field.", file=sys.stderr)
    except (DataUnavailable, FileExistsError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
    except SQLAlchemyError:
        print("Read-only data source query failed.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
