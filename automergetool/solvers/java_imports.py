#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from argparse import ArgumentParser, Namespace
import re
import sys

from automergetool.amt_import_solver import ImportsSolver

IMPORT_REGEX = re.compile('^\s*import\s+(static\s+)?(.*)\s*;\s*$')
EMPTY_REGEX = re.compile('^[\s\n]*$')

IMPORT_GROUPS_ORDER_ANDROID = [("import android.", 0), ("import com.", 1), ("import junit.", 2),
                               ("import net.", 3), ("import org.", 4), ("import java.", 5),
                               ("import javax.", 6), ("import ", 7), ("import static ", 8)]
IMPORT_GROUPS_ORDER_IJ_IDEA = [("import ", 0), ("import javax.", 1), ("import java.", 2),
                               ("import static ", 3)]
IMPORT_GROUPS_ORDER_ECLIPSE = [("import static ", 0), ("import java.", 1), ("import javax.", 2),
                               ("import org.", 3), ("import com.", 4), ("import ", 5)]

ORDER_ANDROID = "android"
ORDER_IJ_IDEA = "idea"
ORDER_ECLIPSE = "eclipse"

IMPORT_PRESETS = {
    ORDER_ANDROID: IMPORT_GROUPS_ORDER_ANDROID,
    ORDER_IJ_IDEA: IMPORT_GROUPS_ORDER_IJ_IDEA,
    ORDER_ECLIPSE: IMPORT_GROUPS_ORDER_ECLIPSE,
}


class JavaImportSolver(ImportsSolver):
    # TODO allow custom order configuration
    def __init__(self, order: str = None):
        super().__init__()
        if order is not None:
            self.set_import_groups(order)
        else:
            self.import_groups = []

    def is_allowed_within_import_section(self, line: str) -> bool:
        if re.match(EMPTY_REGEX, line):
            return True
        else:
            return False

    def is_import_line(self, line: str) -> bool:
        return re.match(IMPORT_REGEX, line) is not None

    def set_import_groups(self, preset: str = None):
        """
        Sets the preferred ordering for imports
        preset -- one of "android", "eclipse", "idea"
        """
        if preset is not None:
            if preset in IMPORT_PRESETS:
                groups = IMPORT_PRESETS[preset]
                self.import_groups = sorted(groups, key=lambda grp: len(grp[0]), reverse=True)

    def get_import_group(self, imp: str):
        """
        Returns the group index the imports belongs to
        imp -- the import line
        """
        for group in self.import_groups:
            if imp.startswith(group[0]):
                return group[1]
        return len(self.import_groups)

    def are_imports_the_same(self, imp: str, other_imp: str):
        match = re.match(IMPORT_REGEX, imp)
        other_match = re.match(IMPORT_REGEX, other_imp)

        canonical = match.group(2).replace(" ", "").replace("\t", "")
        other_canonical = other_match.group(2).replace(" ", "").replace("\t", "")

        if match.group(1) is not None:
            static = match.group(1).replace(" ", "").replace("\t", "")
        else:
            static = ""
        if other_match.group(1) is not None:
            other_static = other_match.group(1).replace(" ", "").replace("\t", "")
        else:
            other_static = ""

        return (canonical == other_canonical) and (static == other_static)


def parse_arguments(args: list) -> Namespace:
    """Parses the arguments passed on invocation in a dict and return it"""
    parser = ArgumentParser(description="A tool to combine multiple merge tools")

    parser.add_argument('-b', '--base', required=True)
    parser.add_argument('-l', '--local', required=True)
    parser.add_argument('-r', '--remote', required=True)
    parser.add_argument('-m', '--merged', required=True)
    parser.add_argument(
        '-o', '--order', choices=[ORDER_ECLIPSE, ORDER_IJ_IDEA, ORDER_ANDROID], required=False)

    return parser.parse_args(args)


if __name__ == '__main__':
    args = parse_arguments(sys.argv[1:])

    solver = JavaImportSolver(args.order)
    if solver.solve_import_conflicts(args.base, args.local, args.remote, args.merge):
        sys.exit(0)
    else:
        sys.exit(1)
