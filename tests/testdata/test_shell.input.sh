cat tests/testdata/users.json
jq '.data[]'
(sh
    grep first_name |
    wc -l
sh)