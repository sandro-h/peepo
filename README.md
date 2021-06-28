# peepo

[![CI](https://github.com/sandro-h/peepo/actions/workflows/ci.yml/badge.svg)](https://github.com/sandro-h/peepo/actions/workflows/ci.yml)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=sandro-h_peepo&metric=alert_status)](https://sonarcloud.io/dashboard?id=sandro-h_peepo)

![](widepeepohappy.png)

Useful bashrc aliases:

```shell
# Create temporary input_file, open in editor, start peepo
function tpeepo() {
    tmp_file=$(mktemp /tmp/peepoXXXXX.sh)
    code "$tmp_file"
    peepo "$tmp_file"
}
```
