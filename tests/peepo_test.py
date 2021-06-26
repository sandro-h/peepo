import subprocess
import os
import re
import shutil

TEST_DIR = os.path.dirname(os.path.realpath(__file__))


def test_run_empty_spool():
    delete_spool()
    returncode, stdout, stderr = run_peepo(f"{TEST_DIR}/testdata/test1.input.sh")
    assert returncode == 0
    assert stderr == ""
    assert stdout == load_file(f"{TEST_DIR}/testdata/test1.output.txt") + "\nOK (ran 4/4)"


def test_run_all_cached():
    delete_spool()
    returncode, stdout, stderr = run_peepo(f"{TEST_DIR}/testdata/test1.input.sh")

    # Second run, all should be cached
    returncode, stdout, stderr = run_peepo(f"{TEST_DIR}/testdata/test1.input.sh")
    assert returncode == 0
    assert stderr == ""
    assert stdout == load_file(f"{TEST_DIR}/testdata/test1.output.txt") + "\nOK (ran 0/4)"


def test_run_one_new_command_at_end():
    delete_spool()
    returncode, stdout, stderr = run_peepo(f"{TEST_DIR}/testdata/test1.input.sh")

    # Second run with one more command:
    returncode, stdout, stderr = run_peepo(f"{TEST_DIR}/testdata/test2.input.sh")
    assert returncode == 0
    assert stderr == ""
    # runs 2 because the previously last command is re-execueted without colors
    assert stdout == load_file(f"{TEST_DIR}/testdata/test2.output.txt") + "\n\nOK (ran 2/5)"


def test_run_python_block():
    delete_spool()
    returncode, stdout, stderr = run_peepo(f"{TEST_DIR}/testdata/test_python.input.sh")
    assert returncode == 0
    assert stderr == ""
    assert stdout == load_file(f"{TEST_DIR}/testdata/test_python.output.txt") + "\nOK (ran 3/3)"


def test_run_error():
    delete_spool()
    returncode, stdout, stderr = run_peepo(f"{TEST_DIR}/testdata/test_error.input.sh")
    assert returncode == 0
    assert stderr + stdout == load_file(f"{TEST_DIR}/testdata/test_error.output.txt") + "\nFAILED (ran 1/3)"


def run_peepo(input_file, assert_success=True):
    result = subprocess.run(['bash', '-c', f"./peepo.py {input_file} --once --spool={TEST_DIR}/spool"],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            check=False)
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
    shutil.rmtree(f"{TEST_DIR}/spool", ignore_errors=True)
