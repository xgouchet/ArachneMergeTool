#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sys
import argparse
from amtutils import *


def parse_arguments():
    """Parses the arguments passed on invocation in a dict and return it"""
    parser = argparse.ArgumentParser(description="A tool to resolve dummy conflicts")

    parser.add_argument('-m', '--merged', required=True)
    parser.add_argument(
        '-r',
        '--report',
        choices=[REPORT_NONE, REPORT_SOLVED, REPORT_UNSOLVED, REPORT_FULL],
        default=REPORT_NONE,
        required=False)

    return parser.parse_args()


def handle_conflict(conflict):
    """Handles a conflict which can be simplified"""
    # Here we look at space resistant substrings (eg : "ab cd" is equal to "ab      cd")
    # TODO 1 : get  the  LCS between B, L and M
    # TODO 2 : split conflicts

    print("The base side of the conflict was :\n" + conflict.base)
    print("The local side of the conflict is :\n" + conflict.local)
    print("The remote side of the conflict is :\n" + conflict.remote)

    # Here's where you'd try to handle the conflict.
    # If it's possible to fix the conflict, call `conflict.resolve(resolution)`
    # Where resolution is the conflict's resolution, as it should appear in the final file
    # If you can't (or don't want to) resolve the conflict, leave the conflict as is


if __name__ == '__main__':
    args = parse_arguments()
    walker = ConflictsWalker(args.merged, 'mwc', args.report)
    while walker.has_more_conflicts():
        handle_conflict(walker.next_conflict())
    walker.end()
    sys.exit(walker.get_merge_status())
