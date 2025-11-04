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

    print("Sending GT request...")
    res = send_request('http://localhost:8081/token','GET',**{'headers': {
                'Authorization': 'Bearer fake-token',
                'X-CLIENT-SECRET': 'client-secret'
            } })
    token = res["content"]["group_token"]
    print("Token: ", token)

    print("\nCreating collection...")
    result = send_request('http://10.10.101.50:12345/invoke-function/functionCreateSeqCollections','POST',**{'headers': {
                'X-ERMES-GROUPS': token,
                'X-CLIENT-SECRET': 'client-secret'
            } ,
            'json': {
                'name': colName
            }})
    print(f"✓ {result['url']} - Status: {result['status_code']} - Time: {result['elapsed_time']:.3f}s, Body: {result['content']}, Execution host: {result["execution_host"]}")    
    
    print('\nUsing collection...')
    for i in range(20):
        result = send_request('http://10.10.101.54:12345/invoke-function/functionUseSeqCollections','POST',**{'headers': {
                'Content-Type': 'application/json',
                'X-CLIENT-SECRET': 'client-secret',
                'X-ERMES-GROUPS': token,
                'X-ERMES-QUERY': '{\"query\": {\"name\": \"'+colName+'\"}}'
            } ,
                'json': {
               'data': 'write number '+ str(i) +" from " + "10.10.101.54",
            }})
        print(f"✓ {result['url']} - Status: {result['status_code']} - Time: {result['elapsed_time']:.3f}s, Body: {result['content']}, Execution host: {result["execution_host"]}")
        time.sleep(0.5)