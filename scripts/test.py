import sys
from sender import *

HOSTS = [
    "10.10.101.50",
    "10.10.101.51",
    "10.10.101.52",
    "10.10.101.53",
    "10.10.101.54",
    "10.10.101.55",
]


if __name__ == "__main__":
    colName = sys.argv[1]

    print("Sending GT request...\n")
    res = send_request('http://localhost:8081/token','GET',**{'headers': {
                'Authorization': 'Bearer fake-token',
                'X-CLIENT-SECRET': 'client-secret'
            } })
    token = res["content"]["group_token"]
    print("Token: ", token)

    print("Creating collection...\n")
    res = send_request('http://10.10.101.55:12345/invoke-function/functionCreateCollections','POST',**{'headers': {
                'X-ERMES-GROUPS': token,
                'X-CLIENT-SECRET': 'client-secret'
            } ,
            'json': {
                'name': colName
            }})
    print(res)


    requests_list = [
        {
            'url': 'http://' + host + ':12345/invoke-function/functionUseCollections',
            'method': 'POST',
            'headers': {
                'Content-Type': 'application/json',
                'X-CLIENT-SECRET': 'client-secret',
                'X-ERMES-GROUPS': token,
                'X-ERMES-QUERY': '{\"query\": {\"name\": \"'+colName+'\"}}'
            },
            'json': {
               'data': 'write number '+ str(i) +" from " + host,
            }
        } for i in range(1000) for host in HOSTS
    ]

    print("Sending parallel requests with different configurations...\n")
    results = send_parallel_requests(requests_list, max_workers=6)
    print_summary(results)