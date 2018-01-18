#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
from argparse import ArgumentParser, Namespace
from configparser import RawConfigParser
from typing import Optional

from automergetool.amt_analyser import ConflictedFileAnalyser
from automergetool.amt_launcher import ToolsLauncher
from automergetool.amt_utils import SUCCESS, ERROR_CONFLICTS, ERROR_EXTENSION, ERROR_INVOCATION, ERROR_NO_TOOL, \
    ERROR_UNKNOWN

# CONSTANTS
GLOBAL_CONFIG = os.path.expanduser('~/.gitconfig')
LOCAL_CONFIG_NAME = 'config'

SECT_AMT = 'amt'
OPT_TOOLS = 'tools'
OPT_VERBOSE = 'verbose'
OPT_KEEP_REPORTS = 'keepReport'


def parse_arguments(args: list) -> Namespace:
    """
    Parses the arguments passed on invocation in a dict and return it
    """
    parser = ArgumentParser(description="A tool to combine multiple merge tools")

    parser.add_argument('-b', '--base', required=True)
    parser.add_argument('-l', '--local', required=True)
    parser.add_argument('-r', '--remote', required=True)
    parser.add_argument('-m', '--merged', required=True)

    # convert to absolute path
    parsed_arg = parser.parse_args(args)

    parsed_arg.base = os.path.abspath(parsed_arg.base)
    parsed_arg.local = os.path.abspath(parsed_arg.local)
    parsed_arg.remote = os.path.abspath(parsed_arg.remote)
    parsed_arg.merged = os.path.abspath(parsed_arg.merged)
    return parsed_arg


def find_local_config_path(config_file: str) -> Optional[str]:
    """
    Finds the nearest parent directory where there is a .git folder
    """
    parent = os.path.dirname(config_file)
    if parent == config_file:
        return None

    git = os.path.join(parent, ".git")
    if os.path.exists(git):
        path = os.path.join(git, LOCAL_CONFIG_NAME)
        if os.path.exists(path):
            return path
        else:
            return None
    else:
        return find_local_config_path(parent)


def read_config(config_path: str) -> RawConfigParser:
    """
    Reads the AMT configuration from the given path
    """
    config = RawConfigParser()
    config.optionxform = str
    config.read_file(open(GLOBAL_CONFIG))
    if config_path:
        config.read(config_path)

    return config


# noinspection PyUnresolvedReferences
def expand_arguments(cmd: str, args: Namespace) -> str:
    """
    Expands the named arguments in the command line invocation
    cmd -- the command line invocation
    args -- the arguments with the base, local, remote and merged filenames
    """
    cmd = cmd.replace('$BASE', args.base)
    cmd = cmd.replace('$LOCAL', args.local)
    cmd = cmd.replace('$REMOTE', args.remote)
    cmd = cmd.replace('$MERGED', args.merged)
    return cmd


def merge(config: RawConfigParser,
          args: Namespace,
          launcher: ToolsLauncher,
          analyser: ConflictedFileAnalyser) -> int:
    """
    Handle the merge tools chain for the given argument
    config -- the current amt configuration
    args -- the arguments with the base, local, remote and merged file names
    launcher -- the launcher helper
    """
    if not (config.has_option(SECT_AMT, OPT_TOOLS)):
        raise RuntimeError('Missing the {0}.{1} configuration'.format(SECT_AMT, OPT_TOOLS))

    tools = config.get(SECT_AMT, OPT_TOOLS).split(';')
    merge_result = ERROR_NO_TOOL

    for tool in tools:
        merge_result = merge_with_tool(tool, config, args, launcher, analyser)
        if merge_result == 0:
            return 0

    print(" [AMT] ⚑ Sorry, it seems we can't solve it this time")

    return merge_result


def merge_with_tool(tool: str,
                    config: RawConfigParser,
                    args: Namespace,
                    launcher: ToolsLauncher,
                    analyser: ConflictedFileAnalyser) -> int:
    """
    Run the given merge tool with the config and args
    """
    verbose = False
    if config.has_option(SECT_AMT, OPT_VERBOSE):
        verbose = config.getboolean(SECT_AMT, OPT_VERBOSE)

    # check empty tool
    if (tool is None) or (tool == ""):
        if verbose:
            print(" [AMT] ø Ignoring empty tool")
        return ERROR_NO_TOOL

    # check file extension against tool preset / config
    extensions = launcher.get_tool_extensions(tool)
    ignored_extensions = launcher.get_tool_ignored_extensions(tool)
    if extensions or ignored_extensions:
        # noinspection PyUnresolvedReferences
        file_name, file_ext = os.path.splitext(args.merged)
        file_ext = file_ext[1:]
        if (extensions is not None) and (file_ext not in extensions):
            if verbose:
                print(" [AMT] — Ignoring tool {0} (bad extension : {1})".format(tool, file_ext))
            return ERROR_EXTENSION
        if (ignored_extensions is not None) and (file_ext in ignored_extensions):
            if verbose:
                print(" [AMT] — Ignoring tool {0} (ignoring extension : {1})".format(tool,
                                                                                     file_ext))
            return ERROR_EXTENSION

    # prepare the command line invocation
    if verbose:
        print(" [AMT] → Trying merge with {0}".format(tool))
    cmd = launcher.get_tool_cmd(tool)
    if cmd is None:
        if verbose:
            print(" [AMT] — Ignoring tool {0} (unknown tool)".format(tool))
        return ERROR_UNKNOWN

    # Run command
    cmd = expand_arguments(cmd, args)
    try:
        invocation_result = launcher.invoke(cmd)
    except Exception as err:
        if verbose:
            print(" [AMT] ✗ {0} error running command {1}\n $ {2}".format(tool, err, cmd))
        return ERROR_INVOCATION

    # Check result
    trust_exit_code = launcher.get_tool_trust(tool)
    if trust_exit_code or invocation_result == ERROR_INVOCATION:
        if invocation_result == 0:
            if verbose:
                print(" [AMT] ✓ {0} merged successfully".format(tool))
            return SUCCESS
        else:
            if verbose:
                print(" [AMT] ✗ {0} didn't solve all conflicts".format(tool))
            return ERROR_CONFLICTS
    else:
        if verbose:
            print(" [AMT] ? {0} returned, but this should not be trusted".format(tool))
        # noinspection PyUnresolvedReferences
        has_remaining = analyser.has_remaining_conflicts(args.merged)
        if has_remaining == 0:
            if verbose:
                print(" [AMT] ✓ {0} merged successfully".format(tool))
            return SUCCESS
        else:
            if verbose:
                print(" [AMT] ✗ {0} didn't solve all conflicts".format(tool))
            return ERROR_CONFLICTS


def clean_reports(config: RawConfigParser, merged_path: str):
    """
    Cleans up the reports for the given file
    """
    if config.has_option(SECT_AMT, OPT_KEEP_REPORTS):
        if config.get(SECT_AMT, OPT_KEEP_REPORTS) == "true":
            return
    print(" [AMT] * Cleaning up reports")
    abs_path = os.path.abspath(merged_path)
    dir_path = os.path.dirname(abs_path)
    base_name = os.path.basename(abs_path)
    for file in os.listdir(dir_path):
        if file.startswith(base_name) and file.endswith('-report'):
            os.remove(os.path.join(dir_path, file))


def run_main() -> int:
    cli_args = parse_arguments(sys.argv[1:])

    # noinspection PyUnresolvedReferences
    merged_file_path = cli_args.merged
    local_config_path = find_local_config_path(merged_file_path)
    merged_config = read_config(local_config_path)
    tools_launcher = ToolsLauncher(merged_config)
    conflict_analyser = ConflictedFileAnalyser()
    result = merge(merged_config, cli_args, tools_launcher, conflict_analyser)

    if result == SUCCESS:
        clean_reports(merged_config, merged_file_path)

    return result


if __name__ == '__main__':
    sys.exit(run_main())
