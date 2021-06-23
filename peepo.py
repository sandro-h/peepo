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


def main():

    input_file = sys.argv[1]
    print("peepo")

    parse_and_run(input_file)

    event_handler = Handler(lambda f: on_input_file_modified(f, input_file))
    observer = Observer()
    observer.schedule(event_handler, '.', recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(5)
    except:
        observer.stop()
        print("Observer Stopped")

    observer.join()


def on_input_file_modified(file, input_file):
    if not file.endswith(input_file):
        return
    parse_and_run(input_file)


def parse_and_run(input_file):
    lines = parse_input_file(input_file)
    print(lines)
    run(lines)


def run(lines):
    print(chr(27) + "[2J")
    cur_stdin = ""
    ran_previous = False
    cmds_ran = 0
    k = 0
    for line in lines:
        ran_previous, cur_stdin = exec_command(line, lines, k, ran_previous, cur_stdin)
        if ran_previous:
            cmds_ran += 1
        k += 1

    print(f"Ran {cmds_ran}/{len(lines)} commands")


def parse_input_file(input_file):
    lines = []
    in_py_block = False
    py_block = ""
    with open(input_file, 'r') as file:
        for line in file:
            line = line.rstrip()
            if line.startswith("#") or line.strip() == "":
                continue
            if line == "py":
                if not in_py_block:
                    in_py_block = True
                    py_block = ""
                else:
                    in_py_block = False
                    lines.append({"type": "python", "content": py_block})
            else:
                if in_py_block:
                    # TODO: handle indendation better than cutting off first 4 chars
                    py_block += line[4:] + "\n"
                else:
                    lines.append({"type": "command", "content": line})

    cur_hash = ""
    for line in lines:
        hash_object = hashlib.sha1((cur_hash + line["content"]).encode("utf8"))
        cur_hash = hash_object.hexdigest()
        line["hash"] = cur_hash

        if line["type"] == "python":
            py_file_name = get_tmp_python_file(line)
            with open(py_file_name, 'w') as py_file:
                py_file.write(line["content"])
            line["content"] = f"python {py_file_name}"

    return lines


def exec_command(line, lines, k, ran_previous, cur_stdin):
    is_last = k == len(lines) - 1
    if not is_last:
        if Path(get_output_file(line)).is_file():
            return False, cur_stdin
        else:
            if k > 0 and not ran_previous:
                with open(get_output_file(lines[k - 1]), 'rb') as file:
                    cur_stdin = file.read()

            result = subprocess.run(['bash', '-c', line["content"]],
                                    stdout=subprocess.PIPE,
                                    input=cur_stdin,
                                    stderr=subprocess.DEVNULL)
            if result.returncode != 0:
                raise Exception(result.returncode)
            cur_stdin = result.stdout
            with open(get_output_file(line), "wb") as output:
                output.write(re.sub(r"\x1b\[[0-9;]*m", '', cur_stdin.decode("utf8")).encode("utf8"))
            ran_previous = True
            return True, cur_stdin

    else:
        if Path(get_col_output_file(line)).is_file():
            with open(get_col_output_file(line), 'rb') as file:
                print(file.read().decode("utf8"))
            return False, cur_stdin
        else:
            with open(get_col_output_file(line), "wb") as output:

                def read(fd):
                    data = os.read(fd, 1024)
                    output.write(data)
                    return data

                cmd = line["content"]
                if k > 0:
                    cmd = f"cat {get_output_file(lines[k - 1])} | {cmd}"
                returncode = pty.spawn(['bash', '-c', cmd], read)
                if returncode != 0:
                    os.remove(get_col_output_file(line))
                    raise Exception(returncode)

            return True, cur_stdin


def get_output_file(line):
    return f"spool/{line['hash']}.out"


def get_col_output_file(line):
    return f"spool/{line['hash']}.col.out"


def get_tmp_python_file(line):
    return f"spool/{line['hash']}.py"


class Handler(FileSystemEventHandler):
    def __init__(self, on_mod):
        self.on_mod = on_mod

    def on_any_event(self, event):
        if event.is_directory:
            return None
        elif event.event_type == 'modified':
            self.on_mod(event.src_path)


if __name__ == "__main__":
    # execute only if run as a script
    main()
