cat tests/testdata/users.json
(jq
    .data[] |
    select(.first_name=="Michael")
    | select(.first_name=="Michael")
jq)
