#!/usr/bin/env python3
"""peepo.

Usage:
  peepo <command_file> [--spool=<spool_dir>] [--once] [--force] [--cols=<cols>] [--script]
  peepo (-h | --help)

Options:
  -h --help                Show this screen.
  -s --spool=<spool_dir>   Spool directory for caching (default: <script dir>/spool)
  -o --once                Run only once instead of watching for file changes.
  -f --force               Don't use cached outputs but rerun all commands instead.
                           Only when peepo runs first time. On file changes or up/down caching will be used.
  -c --cols=<cols>         Overwrite number of columns in terminal (default: read via 'stty size')
  --script                 Convert command file to a standalone shell script and write it to stdout.

"""
import os
from pathlib import Path
import subprocess
import pty
import hashlib
import re
import sys
import shutil
from docopt import docopt
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

COLUMNS = 60
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
SPOOL_DIR = os.path.join(SCRIPT_DIR, 'spool')
BASHRC_FILE_NAME = f"{SCRIPT_DIR}/peepo.bashrc"
LOAD_BASHRC_CMD = f'[ -f "{BASHRC_FILE_NAME}" ] && . {BASHRC_FILE_NAME}'
MAX_SPOOL_FILES = 200
# From https://stackoverflow.com/a/14693789:
ANSI_ESCAPE_PATTERN = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')


def main(args):
    if args["--spool"] is not None:
        global SPOOL_DIR  # pylint: disable=global-statement
        SPOOL_DIR = args["--spool"]

    os.makedirs(SPOOL_DIR, exist_ok=True)

    if args["--script"]:
        convert_peepo_script(args)
    else:
        run_peepo_script(args)


def run_peepo_script(args):

    prepare_helper_files()
    tidy_spool()

    global COLUMNS  # pylint: disable=global-statement
    if args["--cols"] is None:
        _, cols = os.popen('stty size', 'r').read().split()
        COLUMNS = int(cols)
    else:
        COLUMNS = int(args["--cols"])

    command_file = os.path.abspath(args["<command_file>"])

    state = {"up_to_offset": 0, "commands": parse_command_file(command_file)}

    run_commands_and_show_result(state["commands"], force=args["--force"])

    def on_command_file_changed():
        state["commands"] = parse_command_file(command_file)
        state["up_to_offset"] = 0
        run_commands_and_show_result(state["commands"])

    if not args["--once"]:
        stop = watch_file(command_file, on_command_file_changed)
        listen_for_keys(state)
        stop()


def listen_for_keys(state):
    os.system("stty raw -echo")
    try:
        while True:
            ctrl_char = ord(sys.stdin.read(1))
            if ctrl_char == 27:
                rest = sys.stdin.read(2)

                updated_offset = state["up_to_offset"]
                max_cmd_index = len(state["commands"]) - 1
                if rest == "[A":  # up
                    updated_offset = min(max_cmd_index, updated_offset + 1)
                elif rest == "[B":  # down
                    updated_offset = max(0, updated_offset - 1)
                elif rest == "[H":  # home
                    updated_offset = max_cmd_index
                elif rest == "[F":  # end
                    updated_offset = 0

                if updated_offset != state["up_to_offset"]:
                    state["up_to_offset"] = updated_offset
                    run_commands_and_show_result(state["commands"], state["up_to_offset"])

            elif ctrl_char == 114:  # r
                run_commands_and_show_result(state["commands"], state["up_to_offset"], force=True)

            elif ctrl_char in [3, 4, 113]:  # ctrl+c, ctrl+d, q
                break
    finally:
        os.system("stty -raw echo")


def prepare_helper_files():
    copy_from_template_if_exists(BASHRC_FILE_NAME)

    for block_def in BLOCK_DEFS.values():
        if "helper_file" in block_def:
            copy_from_template_if_exists(block_def["helper_file"])


def copy_from_template_if_exists(target_file):
    src_template = f"{target_file}.tmpl"
    if not file_exists(target_file) and file_exists(src_template):
        shutil.copyfile(src_template, target_file)


def tidy_spool():
    paths = sorted(Path(SPOOL_DIR).iterdir(), key=os.path.getmtime, reverse=True)
    for path in paths[MAX_SPOOL_FILES:]:
        os.remove(path)


def parse_command_file(command_file):
    commands = []
    block_content = ""
    block_indent = -1
    active_block = None

    with open(command_file, 'r') as file:
        for line in file:
            line = line.rstrip()
            if line.startswith("#") or line.strip() == "":
                continue

            is_block_marker = False
            for marker in BLOCK_DEFS:
                if line == "(" + marker and not active_block:
                    is_block_marker = True
                    active_block = marker
                    block_content = ""
                    block_indent = -1
                elif line == marker + ")" and active_block:
                    is_block_marker = True
                    active_block = None
                    commands.append({"type": marker, "content": block_content})

            if not is_block_marker:
                if active_block:
                    if block_indent < 0:
                        trimmed = line.lstrip()
                        block_indent = len(line) - len(trimmed)
                    block_content += line[block_indent:] + "\n"
                else:
                    commands.append({"type": "command", "content": line})

    return prepare_commands(commands)


def prepare_commands(commands):

    helpers = {}
    for marker, block_def in BLOCK_DEFS.items():
        if "helper_file" in block_def:
            helper_content = load_helper_content(block_def["helper_file"])
            if helper_content:
                helpers[marker] = helper_content

    cur_hash = ""
    block_index = {}
    for command in commands:
        cur_hash = sha1(cur_hash + command["content"])
        command["hash"] = cur_hash
        command["preview"] = make_preview(command["content"])

        marker = command["type"]
        block_def = BLOCK_DEFS.get(marker)
        if block_def is not None:
            index = block_index.get(marker, 0)
            block_index[marker] = index + 1

            command["script_content"] = command["content"]

            if "mutate_block" in block_def:
                command["script_content"] = block_def["mutate_block"](command["script_content"])
                command["preview"] = make_preview(command["script_content"])

            if marker in helpers:
                command["script_content"] = helpers[marker] + command["script_content"]
                cur_hash = sha1(cur_hash + helpers[marker])
                command["hash"] = cur_hash

            spool_file_name = os.path.join(SPOOL_DIR, f"{index}.{marker}")
            with open(spool_file_name, 'w') as spool_file:
                spool_file.write(command["script_content"])
            command["content"] = block_def["build_command"](spool_file_name)

    return commands


def load_helper_content(file_name):
    if file_exists(file_name):
        with open(file_name, 'r') as file:
            return file.read() + "\n"
    return ""


def make_preview(content):
    return re.sub(r"\s+", " ", content.strip())


def run_commands_and_show_result(commands, up_to_offset=0, force=False):
    if not commands:
        print("Waiting for first command...")
        return

    up_to = max(0, len(commands) - up_to_offset)
    success, cmds_ran, last_cmd_index = run_commands(commands, up_to, force)

    status = "OK" if success else "FAILED"
    status += f" (ran {cmds_ran}/{up_to})\033[0m"
    status += f" cmd {last_cmd_index + 1}/{len(commands)}: {commands[last_cmd_index]['preview']}"
    status = ellipsis(status, COLUMNS)

    # We need to use \r to move cursor to left in terminal raw mode.
    # Cf. https://stackoverflow.com/questions/49124608/how-to-align-the-cursor-to-the-left-side-after-using-printf-c-linux
    if success:
        status = "\r\n\033[0;32m" + status
    else:
        status = "\r\n\033[0;31m" + status

    print(status, end='', flush=True)


def run_commands(commands, up_to, force):
    clear_terminal()

    cmds_ran = 0
    for k, command in enumerate(commands[:up_to]):
        last = k == up_to - 1
        stdin_file_path = get_output_file(commands[k - 1]) if k > 0 else None
        out_file_path = get_output_file(command)
        col_file_path = get_col_output_file(command)
        stdout_file_path = col_file_path if last else out_file_path

        if not last and not file_exists(out_file_path) and file_exists(col_file_path):
            convert_col_to_out_file(col_file_path, out_file_path)

        # Command executed previously, use cached output:
        if not force and file_exists(stdout_file_path):
            # Touch cached file so housekeeping knows it was used recently:
            Path(stdout_file_path).touch()
            if last:
                with open(stdout_file_path, 'rb') as file:
                    print(file.read().decode("utf8"))
            continue

        cmds_ran += 1

        with open(stdout_file_path, 'wb') as stdout_file:
            return_code = run_command(command["content"], stdin_file_path, stdout_file, use_color=last)

        acceptable_return_codes = [0]
        if is_grep_command(command["content"]):
            acceptable_return_codes = [0, 1]

        if return_code not in acceptable_return_codes:
            os.remove(stdout_file_path)
            print(f"Command {k+1} failed with return code {return_code}")
            return False, cmds_ran, k

    return True, cmds_ran, up_to - 1


def convert_col_to_out_file(col_file_path, out_file_path):
    with open(out_file_path, 'w') as out_file:
        with open(col_file_path, 'r') as col_file:
            for line in col_file:
                out_file.write(strip_ansi_escape_codes(line))


def is_grep_command(cmd_content):
    return re.search(r"^\s*e?grep", cmd_content)


def run_command(cmd, stdin_file_path, stdout_file, use_color):
    if use_color:

        def read(pty_stdout):
            data = os.read(pty_stdout, 1024)
            stdout_file.write(data)
            return data

        if stdin_file_path:
            cmd = f"cat {stdin_file_path} | {cmd}"

        return pty.spawn(build_bash_cmd(cmd), read)

    stdin_file = open(stdin_file_path, 'rb') if stdin_file_path is not None else None
    result = subprocess.run(build_bash_cmd(cmd), stdout=stdout_file, stdin=stdin_file, check=False)
    if stdin_file is not None:
        stdin_file.close()
    return result.returncode


def build_bash_cmd(cmd):
    # The \n is important for aliases to be loaded. From bash manual:
    #   The rules concerning the definition and use of aliases are somewhat confusing.
    #   Bash always reads at least one complete line of input before executing any of the commands on that line.
    return ['bash', '-O', 'expand_aliases', '-c', f"{LOAD_BASHRC_CMD}\n{cmd}"]


def convert_peepo_script(args):
    prepare_helper_files()

    command_file = os.path.abspath(args["<command_file>"])

    commands = parse_command_file(command_file)

    script = """
#!/usr/bin/env bash
set -euo pipefail
"""
    script += LOAD_BASHRC_CMD + "\n\n"
    for i, command in enumerate(commands):
        script += convert_to_shell_lines(command)
        if i < len(commands) - 1:
            script += " |\n"

    print(script)


def convert_to_shell_lines(command):
    if command["type"] in BLOCK_DEFS:
        return BLOCK_DEFS[command["type"]]["build_script"](command["script_content"])

    if is_grep_command(command["content"]):
        return command["content"] + " || true"

    return command["content"]


def get_output_file(command):
    return os.path.join(SPOOL_DIR, f"{command['hash']}.out")


def get_col_output_file(command):
    return os.path.join(SPOOL_DIR, f"{command['hash']}.col")


def clear_terminal():
    print(chr(27) + "[2J\r")


def strip_ansi_escape_codes(string):
    return ANSI_ESCAPE_PATTERN.sub('', string)


def sha1(content):
    return hashlib.sha1(content.encode("utf8")).hexdigest()


def ellipsis(content, max_len):
    if len(content) <= max_len:
        return content
    return content[:max_len - 3] + "..."


def file_exists(file_name):
    return Path(file_name).is_file()


def watch_file(command_file, on_modified):
    def internal_on_modified(modified_file):
        if modified_file == command_file:
            on_modified()

    event_handler = Handler(internal_on_modified)
    observer = Observer()

    observer.schedule(event_handler, Path(command_file).parent.absolute(), recursive=False)
    observer.start()
    return observer.stop


class Handler(FileSystemEventHandler):
    def __init__(self, on_mod):
        self.on_mod = on_mod

    def on_any_event(self, event):
        if event.is_directory:
            return

        if event.event_type == 'modified':
            self.on_mod(event.src_path)


def py_build_command(spool_file):
    return f"python {spool_file}"


def py_build_script(content):
    indent_script = content.strip().replace("\n", "\n\t").replace("$", "\\$")
    return f"python <(cat <<-EOF\n\t{indent_script}\nEOF\n)"


def sh_build_command(spool_file):
    return f"bash {spool_file}"


def sh_build_script(content):
    indent_script = content.strip().replace("\n", "\n\t")
    return f"(\n\t{indent_script}\n)"


def jq_build_command(spool_file):
    return f"jq -f {spool_file}"


def jq_build_script(content):
    indent_script = content.strip().replace("\n", "\n\t")
    return f"jq -f <(cat <<-EOF\n\t{indent_script}\nEOF\n)"


def jq_mutate_block(block):
    lines = block.split("\n")
    last_had_pipe = False
    for i, line in enumerate(lines):
        if (not last_had_pipe and i > 0 and line.strip() != "" and not line.lstrip().startswith("|")
                and not line.lstrip().startswith("#")):
            lines[i] = "| " + line
        last_had_pipe = line.rstrip().endswith("|")

    return "\n".join(lines)


BLOCK_DEFS = {
    "py": {
        "build_command": py_build_command,
        "helper_file": f"{SCRIPT_DIR}/helpers.py",
        "build_script": py_build_script
    },
    "sh": {
        "build_command": sh_build_command,
        "build_script": sh_build_script
    },
    "jq": {
        "build_command": jq_build_command,
        "build_script": jq_build_script,
        "mutate_block": jq_mutate_block
    }
}

if __name__ == "__main__":
    # execute only if run as a script
    ARGS = docopt(__doc__, version='peepo')
    main(ARGS)
