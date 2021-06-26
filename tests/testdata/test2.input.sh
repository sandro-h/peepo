cat tests/testdata/users.json
jq '.data[].first_name'
sed -r 's/^\s+|"//g'
tr '\n' ','
wc -c