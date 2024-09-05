""" Parser of data output from numeric-received. """

import argparse
import json
from datetime import datetime
from pathlib import Path
import sys


def output(out, data):
    out.write(",".join(data))
    out.write("\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--directory", type=str)
    parser.add_argument("-o", "--output", type=str, default=None)
    parser.add_argument("-f", "--field", type=str, default="Dilithium Ore")
    parser.add_argument("-p", "--per-day", type=int, default=3)
    args = parser.parse_args()


    if args.output:
        out = open(args.output, "w")
    else:
        out = sys.stdout

    output(
        out,
        [
            "Start Date",
            "End Date",
            "Duration",
            args.field,
            "PS",
            "PH",
            "PD",
            "PW",
            "PM",
        ],
    )
    for file in Path(args.directory).glob("*.json"):
        with open(file) as fd:
            data = json.load(fd)
            output(
                out,
                [
                    datetime.fromtimestamp(data["start"]).isoformat(),
                    datetime.fromtimestamp(data["end"]).isoformat(),
                    str(data["duration"]),
                    str(data["rewards"].get(args.field, 0)),
                    str(data["rewards"].get(args.field, 0) / data["duration"]),
                    str(data["rewards"].get(args.field, 0) / data["duration"] * 3600),
                    str(
                        data["rewards"].get(args.field, 0)
                        / data["duration"]
                        * 3600
                        * args.per_day
                    ),
                    str(
                        data["rewards"].get(args.field, 0)
                        / data["duration"]
                        * 3600
                        * args.per_day
                        * 7
                    ),
                    str(
                        data["rewards"].get(args.field, 0)
                        / data["duration"]
                        * 3600
                        * args.per_day
                        * 7
                        * 4
                    ),
                ],
            )


if __name__ == "__main__":
    main()
