cat tests/testdata/users.json
jq '.data[]'
(sh
    grep first_name |
    tr -d '"'
sh)
(py
    lines = from_lines()
    print([f"oi {l.strip()}" for l in lines])
py)