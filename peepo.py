#!/usr/bin/env python3
import os
from pathlib import Path
import sys
import subprocess
import pty
import hashlib
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
        is_last = k == len(lines) - 1
        if not is_last:
            if Path(get_output_file(line)).is_file():
                ran_previous = False
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
                    output.write(cur_stdin)
                ran_previous = True
                cmds_ran += 1

        else:
            # Always run last command (ignore cached output) to get proper shell coloring
            def read(fd):
                data = os.read(fd, 1024)
                return data

            cmd = line["content"]
            if k > 0:
                cmd = f"cat {get_output_file(lines[k - 1])} | {cmd}"
            pty.spawn(['bash', '-c', cmd], read)
            # TODO: react to fail exit code
            cmds_ran += 1

        k += 1

    print(f"Ran {cmds_ran}/{len(lines)} commands")


def parse_input_file(input_file):
    lines = []
    in_py_block = False
    py_block = ""
    with open(input_file, 'r') as file:
        for line in file:
            line = line.strip()
            if line.startswith("#"):
                continue
            if line == "py":
                if not in_py_block:
                    in_py_block = True
                    py_block = ""
                else:
                    in_py_block = False
                    lines.append({"type": "python", "content": py_block, "hash": "TODO"})
            if in_py_block:
                py_block += line + "\n"
            else:
                lines.append({"type": "shell", "content": line, "hash": "TODO"})

    cur_hash = ""
    for line in lines:
        hash_object = hashlib.sha1((cur_hash + line["content"]).encode("utf8"))
        cur_hash = hash_object.hexdigest()
        line["hash"] = cur_hash

    return lines


def get_output_file(line):
    return f"spool/output{line['hash']}"


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
