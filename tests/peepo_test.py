import subprocess
import os
import re
import shutil

TEST_DIR = os.path.dirname(os.path.realpath(__file__))
SPOOL_DIR = os.path.join(TEST_DIR, "spool")
TOP_DIR = os.path.join(TEST_DIR, "..")

CASES = [{
    "input": f"{TEST_DIR}/testdata/test1.input.sh",
    "output": f"{TEST_DIR}/testdata/test1.output.txt",
    "status": "\n\nOK (ran 4/4) cmd 4/4: tr '\\n' ','"
}, {
    "input": f"{TEST_DIR}/testdata/test2.input.sh",
    "output": f"{TEST_DIR}/testdata/test2.output.txt",
    "status": "\n\nOK (ran 5/5) cmd 5/5: wc -c"
}, {
    "input": f"{TEST_DIR}/testdata/test_python.input.sh",
    "output": f"{TEST_DIR}/testdata/test_python.output.txt",
    "status": "\n\nOK (ran 3/3) cmd 3/3: data = from_json() print(\"$oi: ..."
}, {
    "input": f"{TEST_DIR}/testdata/test_shell.input.sh",
    "output": f"{TEST_DIR}/testdata/test_shell.output.txt",
    "status": "\n\nOK (ran 3/3) cmd 3/3: grep first_name | wc -l"
}, {
    "input": f"{TEST_DIR}/testdata/test_only_one_cmd.input.sh",
    "output": f"{TEST_DIR}/testdata/test_only_one_cmd.output.txt",
    "status": "\n\nOK (ran 1/1) cmd 1/1: cat tests/testdata/users.json"
}, {
    "input": f"{TEST_DIR}/testdata/test_no_grep_error.input.sh",
    "output": f"{TEST_DIR}/testdata/test_no_grep_error.output.txt",
    "status": "OK (ran 5/5) cmd 5/5: tr ',' '\\n'"
}, {
    "input": f"{TEST_DIR}/testdata/test_mixed_blocks.input.sh",
    "output": f"{TEST_DIR}/testdata/test_mixed_blocks.output.txt",
    "status": "\n\nOK (ran 4/4) cmd 4/4: lines = from_lines() print([f\"o..."
}]


def test_run_empty_spool():
    delete_spool()

    for case in CASES:
        delete_spool()
        print(f"Testcase {case['input']}")

        returncode, stdout, stderr = run_peepo(case["input"])
        assert returncode == 0
        assert stderr == ""
        assert stdout == load_file(case["output"]) + case["status"]


def test_run_all_cached():
    delete_spool()
    returncode, stdout, stderr = run_peepo(f"{TEST_DIR}/testdata/test1.input.sh")

    # Second run, all should be cached
    returncode, stdout, stderr = run_peepo(f"{TEST_DIR}/testdata/test1.input.sh")
    assert returncode == 0
    assert stderr == ""
    assert stdout == load_file(f"{TEST_DIR}/testdata/test1.output.txt") + "\n\nOK (ran 0/4) cmd 4/4: tr '\\n' ','"


def test_run_one_new_command_at_end():
    delete_spool()
    returncode, stdout, stderr = run_peepo(f"{TEST_DIR}/testdata/test1.input.sh")

    # Second run with one more command:
    returncode, stdout, stderr = run_peepo(f"{TEST_DIR}/testdata/test2.input.sh")
    assert returncode == 0
    assert stderr == ""
    # runs 2 because the previously last command is re-executed without colors
    assert stdout == load_file(f"{TEST_DIR}/testdata/test2.output.txt") + "\n\nOK (ran 2/5) cmd 5/5: wc -c"


def test_run_force():
    delete_spool()
    returncode, stdout, stderr = run_peepo(f"{TEST_DIR}/testdata/test1.input.sh")

    # Second run, would be cached but we force it
    returncode, stdout, stderr = run_peepo(f"{TEST_DIR}/testdata/test1.input.sh", extra_args="--force")
    assert returncode == 0
    assert stderr == ""
    assert stdout == load_file(f"{TEST_DIR}/testdata/test1.output.txt") + "\n\nOK (ran 4/4) cmd 4/4: tr '\\n' ','"


def test_run_error():
    delete_spool()
    returncode, stdout, stderr = run_peepo(f"{TEST_DIR}/testdata/test_error.input.sh")
    assert returncode == 0
    assert stderr + stdout == load_file(
        f"{TEST_DIR}/testdata/test_error.output.txt") + "\nFAILED (ran 1/3) cmd 1/3: cat nonexistentfile"


def test_uses_python_venv():
    delete_spool()
    # Should use peepo script's venv when running python blocks
    returncode, stdout, stderr = run_peepo(f"{TEST_DIR}/testdata/test_python_venv.input.sh")
    assert returncode == 0
    assert stderr == ""
    assert stdout == "OK (ran 1/1) cmd 1/1: from docopt import docopt"


def test_helper_file_change():
    delete_spool()
    returncode, stdout, stderr = run_peepo(f"{TEST_DIR}/testdata/test_python.input.sh")
    assert returncode == 0
    assert stderr == ""
    assert stdout == load_file(
        f"{TEST_DIR}/testdata/test_python.output.txt") + "\n\nOK (ran 3/3) cmd 3/3: data = from_json() print(\"$oi: ..."

    # Second run without any helper file change should cache
    returncode, stdout, stderr = run_peepo(f"{TEST_DIR}/testdata/test_python.input.sh")
    assert returncode == 0
    assert stderr == ""
    assert stdout == load_file(
        f"{TEST_DIR}/testdata/test_python.output.txt") + "\n\nOK (ran 0/3) cmd 3/3: data = from_json() print(\"$oi: ..."

    # Now change something in the helper file
    helper_file_name = f"{TOP_DIR}/helpers.py"
    with open(helper_file_name, 'w') as file:
        file.write("""
import json
import sys

def from_json():
    return {"first_name": "changed!"}
        """)

    returncode, stdout, stderr = run_peepo(f"{TEST_DIR}/testdata/test_python.input.sh")
    os.remove(helper_file_name)

    assert returncode == 0
    assert stderr == ""
    assert stdout == "$oi: changed!\n\n\nOK (ran 1/3) cmd 3/3: data = from_json() print(\"$oi: ..."


def test_convert_script():
    convert_file = f"{SPOOL_DIR}/convert_output.sh"
    delete_spool()
    os.makedirs(SPOOL_DIR, exist_ok=True)

    for case in CASES:
        print(f"Testcase {case['input']}")

        returncode, *_ = run_peepo_convert(case["input"], convert_file)
        assert returncode == 0

        returncode, stdout, stderr = run_with_bash(f"chmod +x {convert_file} && {convert_file}")
        assert returncode == 0
        assert stderr == ""
        assert stdout == load_file(case["output"])


def run_peepo(command_file, assert_success=True, extra_args=""):
    return run_with_bash(f"./peepo.py {command_file} --spool={SPOOL_DIR} --once --cols=60 {extra_args}", assert_success)


def run_peepo_convert(command_file, output_script, assert_success=True):
    return run_with_bash(f"./peepo.py {command_file} --spool={SPOOL_DIR} --script > {output_script}", assert_success)


def run_with_bash(cmd, assert_success=True):
    result = subprocess.run(['bash', '-c'] + [cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    stdout = strip_shell_control_chars(result.stdout).lstrip()
    stderr = strip_shell_control_chars(result.stderr).lstrip()
    if assert_success:
        assert result.returncode == 0, f"Return code was {result.returncode}.\nstdout: {stdout}\nstderr: {stderr}"
    return result.returncode, stdout.replace('\r', ''), stderr.replace('\r', '')


def strip_shell_control_chars(str_bytes):
    return re.sub(r"\x1b\[([0-9;]*m|2J)", '', str_bytes.decode("utf8"))


def load_file(file_path):
    with open(file_path, 'r') as file:
        return file.read()


def delete_spool():
    shutil.rmtree(f"{SPOOL_DIR}", ignore_errors=True)
