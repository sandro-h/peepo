cat tests/testdata/users.json
jq '.data[0]'
(py
    data = from_json()
    print(data['first_name'])
py)