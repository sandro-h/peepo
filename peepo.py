#!/usr/bin/env python3
import os
from pathlib import Path
import sys
import subprocess
import pty
import hashlib
import re
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
SPOOL_DIR = os.path.join(SCRIPT_DIR, 'spool')
MAX_SPOOL_FILES = 200

PYTHON_HELPER_FUNCS = """
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


def main():

    os.makedirs(SPOOL_DIR, exist_ok=True)
    tidy_spool()

    input_file = sys.argv[1]

    parse_and_run(input_file)

    only_once = len(sys.argv) > 2 and sys.argv[2] == "--once"
    if not only_once:
        event_handler = Handler(lambda f: on_input_file_modified(f, input_file))
        observer = Observer()
        observer.schedule(event_handler, '.', recursive=False)
        observer.start()
        try:
            while True:
                time.sleep(5)
        except:  # pylint: disable=bare-except
            observer.stop()

        observer.join()


def tidy_spool():
    paths = sorted(Path(SPOOL_DIR).iterdir(), key=os.path.getmtime, reverse=True)
    for path in paths[MAX_SPOOL_FILES:]:
        os.remove(path)


def on_input_file_modified(file, input_file):
    if os.path.basename(file) == input_file:
        parse_and_run(input_file)


def parse_and_run(input_file):
    commands = parse_input_file(input_file)
    success, cmds_ran = run(commands)

    if success:
        pre_str = "\n\033[0;32mOK"
    else:
        pre_str = "\n\033[0;31mFAILED"

    post_str = f" (ran {cmds_ran}/{len(commands)})\033[0m"

    print(pre_str + post_str, end='', flush=True)


def run(commands):
    clear_terminal()

    cmds_ran = 0
    k = -1
    for command in commands:
        k += 1
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


def parse_input_file(input_file):
    commands = []
    in_py_block = False
    py_block = ""
    py_block_indent = -1
    in_sh_block = False
    sh_block = ""
    with open(input_file, 'r') as file:
        for line in file:
            line = line.rstrip()
            if line.startswith("#") or line.strip() == "":
                continue

            if line == "(py" and not in_py_block:
                in_py_block = True
                py_block = ""
                py_block_indent = -1
            elif line == "py)" and in_py_block:
                in_py_block = False
                commands.append({"type": "python", "content": py_block})
            elif line == "(sh" and not in_sh_block:
                in_sh_block = True
                sh_block = ""
            elif line == "sh)" and in_sh_block:
                in_sh_block = False
                commands.append({"type": "shellscript", "content": sh_block})
            else:
                if in_py_block:
                    if py_block_indent < 0:
                        trimmed = line.lstrip()
                        py_block_indent = len(line) - len(trimmed)
                    py_block += line[py_block_indent:] + "\n"
                elif in_sh_block:
                    sh_block += line + "\n"
                else:
                    commands.append({"type": "command", "content": line})

    cur_hash = ""
    py_index = 0
    sh_index = 0
    for command in commands:
        cur_hash = sha1(cur_hash + command["content"])
        command["hash"] = cur_hash

        if command["type"] == "python":
            py_file_name = get_tmp_python_file(py_index)
            py_index += 1
            with open(py_file_name, 'w') as py_file:
                py_file.write(PYTHON_HELPER_FUNCS + command["content"])
            command["content"] = f"python {py_file_name}"
        elif command["type"] == "shellscript":
            sh_file_name = get_tmp_shell_file(sh_index)
            sh_index += 1
            with open(sh_file_name, 'w') as sh_file:
                sh_file.write(command["content"])
            command["content"] = f"bash {sh_file_name}"

    return commands


def get_output_file(command):
    return os.path.join(SPOOL_DIR, f"{command['hash']}.out")


def get_col_output_file(command):
    return os.path.join(SPOOL_DIR, f"{command['hash']}.col")


def get_tmp_python_file(index):
    return os.path.join(SPOOL_DIR, f"{index}.py")


def get_tmp_shell_file(index):
    return os.path.join(SPOOL_DIR, f"{index}.sh")


def clear_terminal():
    print(chr(27) + "[2J")


def strip_shell_control_chars(str_bytes):
    return re.sub(r"\x1b\[[0-9;]*m", '', str_bytes.decode("utf8")).encode("utf8")


def sha1(content):
    return hashlib.sha1(content.encode("utf8")).hexdigest()


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
    main()
