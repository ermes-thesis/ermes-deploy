import sys
from sender import *


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
    result = send_request('http://10.10.101.50:12345/invoke-function/functionCreateCollections','POST',**{'headers': {
                'X-ERMES-GROUPS': token,
                'X-CLIENT-SECRET': 'client-secret'
            } ,
            'json': {
                'name': colName
            }})
    print(f"✓ {result['url']} - Status: {result['status_code']} - Time: {result['elapsed_time']:.3f}s, Body: {result['content']}, Execution host: {result["execution_host"]}")    
    
    print('\nUsing collection...')
    for i in range(20):
        result = send_request('http://10.10.101.54:12345/invoke-function/functionUseCollections','POST',**{'headers': {
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