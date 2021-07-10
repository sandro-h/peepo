# peepo

[![CI](https://github.com/sandro-h/peepo/actions/workflows/ci.yml/badge.svg)](https://github.com/sandro-h/peepo/actions/workflows/ci.yml)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=sandro-h_peepo&metric=alert_status)](https://sonarcloud.io/dashboard?id=sandro-h_peepo)

![](widepeepohappy.png)

## Usage

Command line options, see

```shell
./peepo --help
```

Command keys:

| Key | Function |
|-----|-----|
| `<up arrow key>` | Go to previous command in input file |
| `<down arrow key>` | Go to next command in input file |
| `r` | Rerun all commands without using cached output |

Useful bash function to start peepo inside VSCode's integrated terminal:

```shell
# Create temporary input_file, open it in VSCode, start peepo
function tpeepo() {
    tmp_file=$(mktemp /tmp/peepoXXXXX.sh)
    code "$tmp_file"
    peepo "$tmp_file"
}
```
