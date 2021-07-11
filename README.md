# peepo

[![CI](https://github.com/sandro-h/peepo/actions/workflows/ci.yml/badge.svg)](https://github.com/sandro-h/peepo/actions/workflows/ci.yml)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=sandro-h_peepo&metric=alert_status)](https://sonarcloud.io/dashboard?id=sandro-h_peepo)

![](widepeepohappy.png)

## Usage

```shell
./peepo <command file>
```

For more options, see:

```shell
./peepo --help
```

### Command keys

| Key | Function |
|-----|-----|
| `<up arrow key>` | Go to previous command in command file |
| `<down arrow key>` | Go to next command in command file |
| `<home key>` | Go to first command in command file |
| `<end key>` | Go to last command in command file |
| `r` | Rerun all commands without using cached output |

### peepo.bashrc

Executed commands do not use user's bashrc/profile because it can mess
with command execution. Instead, peepo sources `peepo.bashrc`, where you
can add whatever you want.

```shell
cp peepo.bashrc.tmpl peepo.bashrc
```

### Misc

Useful bash function to start peepo inside VSCode's integrated terminal:

```shell
# Create temporary input_file, open it in VSCode, start peepo
function tpeepo() {
    tmp_file=$(mktemp /tmp/peepoXXXXX.sh)
    code "$tmp_file"
    peepo "$tmp_file"
}
```
