#!/usr/bin/env python3
"""peepo.

Usage:
  peepo <file> [--once] [--spool=<spool_dir>]
  peepo (-h | --help)

Options:
  -h --help             Show this screen.
  --once                Run only once instead of watching for file changes.
  --spool=<spool_dir>   Spool directory for caching (default: <script dir>/spool)

"""
import os
from pathlib import Path
import subprocess
import pty
import hashlib
import re
import time
from docopt import docopt
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
SPOOL_DIR = os.path.join(SCRIPT_DIR, 'spool')
MAX_SPOOL_FILES = 200
BLOCK_DEFS = {
    "py": {
        "make_command": lambda spool_file: f"python {spool_file}",
        "helper_functions": """
import json
import sys

def from_json():
    return json.load(sys.stdin)

def from_string():
    return sys.stdin.read()

def from_lines():
    for line in sys.stdin:
        yield line.rstrip()

"""
    },
    "sh": {
        "make_command": lambda spool_file: f"bash {spool_file}",
        "helper_functions": ""
    }
}


def main(args):

    if args["--spool"] is not None:
        global SPOOL_DIR  # pylint: disable=global-statement
        SPOOL_DIR = args["--spool"]

    os.makedirs(SPOOL_DIR, exist_ok=True)
    tidy_spool()

    input_file = args["<file>"]

    parse_and_run(input_file)

    if not args["--once"]:
        watch_file(input_file, parse_and_run)


def tidy_spool():
    paths = sorted(Path(SPOOL_DIR).iterdir(), key=os.path.getmtime, reverse=True)
    for path in paths[MAX_SPOOL_FILES:]:
        os.remove(path)


def parse_and_run(input_file):
    commands = parse_input_file(input_file)
    success, cmds_ran = run(commands)

    if success:
        pre_str = "\n\033[0;32mOK"
    else:
        pre_str = "\n\033[0;31mFAILED"

    post_str = f" (ran {cmds_ran}/{len(commands)})\033[0m"

    print(pre_str + post_str, end='', flush=True)


def parse_input_file(input_file):
    commands = []
    block_content = ""
    block_indent = -1
    in_block = False

    with open(input_file, 'r') as file:
        for line in file:
            line = line.rstrip()
            if line.startswith("#") or line.strip() == "":
                continue

            is_block_marker = False
            for marker in BLOCK_DEFS:
                if line == "(" + marker and not in_block:
                    is_block_marker = True
                    in_block = True
                    block_content = ""
                    block_indent = -1
                elif line == marker + ")" and in_block:
                    is_block_marker = True
                    in_block = False
                    commands.append({"type": marker, "content": block_content})

            if not is_block_marker:
                if in_block:
                    if block_indent < 0:
                        trimmed = line.lstrip()
                        block_indent = len(line) - len(trimmed)
                    block_content += line[block_indent:] + "\n"
                else:
                    commands.append({"type": "command", "content": line})

    return process_commands(commands)


def process_commands(commands):
    cur_hash = ""
    block_index = {}
    for command in commands:
        cur_hash = sha1(cur_hash + command["content"])
        command["hash"] = cur_hash

        marker = command["type"]
        block_def = BLOCK_DEFS.get(marker)
        if block_def is not None:
            index = block_index.get(marker, 0)
            block_index[marker] = index + 1
            spool_file_name = os.path.join(SPOOL_DIR, f"{index}.{marker}")
            with open(spool_file_name, 'w') as spool_file:
                spool_file.write(block_def["helper_functions"] + command["content"])
            command["content"] = block_def["make_command"](spool_file_name)

    return commands


def run(commands):
    clear_terminal()

    cmds_ran = 0
    for k, command in enumerate(commands):
        last = k == len(commands) - 1
        stdin_file_path = get_output_file(commands[k - 1]) if k > 0 else None
        stdout_file_path = get_col_output_file(command) if last else get_output_file(command)

        # Command executed previously, use cached output:
        if Path(stdout_file_path).is_file():
            Path(stdout_file_path).touch()
            if last:
                with open(stdout_file_path, 'rb') as file:
                    print(file.read().decode("utf8"))
            continue

        cmds_ran += 1

        with open(stdout_file_path, 'wb') as stdout_file:
            return_code = exec_command_in_shell(command["content"], stdin_file_path, stdout_file, use_color=last)

        if return_code != 0:
            os.remove(stdout_file_path)
            print(f"Command {k+1} failed with return code {return_code}")
            return False, cmds_ran

    return True, cmds_ran


def exec_command_in_shell(cmd, stdin_file_path, stdout_file, use_color):
    if use_color:

        def read(pty_stdout):
            data = os.read(pty_stdout, 1024)
            stdout_file.write(data)
            return data

        if stdin_file_path:
            cmd = f"cat {stdin_file_path} | {cmd}"

        return pty.spawn(['bash', '-c', cmd], read)

    stdin_file = open(stdin_file_path, 'rb') if stdin_file_path is not None else None
    result = subprocess.run(['bash', '-c', cmd], stdout=stdout_file, stdin=stdin_file, check=False)
    if stdin_file is not None:
        stdin_file.close()
    return result.returncode


def get_output_file(command):
    return os.path.join(SPOOL_DIR, f"{command['hash']}.out")


def get_col_output_file(command):
    return os.path.join(SPOOL_DIR, f"{command['hash']}.col")


def clear_terminal():
    print(chr(27) + "[2J")


def strip_shell_control_chars(str_bytes):
    return re.sub(r"\x1b\[[0-9;]*m", '', str_bytes.decode("utf8")).encode("utf8")


def sha1(content):
    return hashlib.sha1(content.encode("utf8")).hexdigest()


def watch_file(input_file, on_modified):
    def internal_on_modified(modified_file):
        if os.path.basename(modified_file) == input_file:
            on_modified(input_file)

    event_handler = Handler(internal_on_modified)
    observer = Observer()
    observer.schedule(event_handler, '.', recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(5)
    except:  # pylint: disable=bare-except
        observer.stop()

    observer.join()


class Handler(FileSystemEventHandler):
    def __init__(self, on_mod):
        self.on_mod = on_mod

    def on_any_event(self, event):
        if event.is_directory:
            return

        if event.event_type == 'modified':
            self.on_mod(event.src_path)


if __name__ == "__main__":
    # execute only if run as a script
    arguments = docopt(__doc__, version='peepo')
    main(arguments)
