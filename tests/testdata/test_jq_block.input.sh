cat tests/testdata/users.json
(jq
    .data[]
    select(.first_name=="Michael")
jq)
