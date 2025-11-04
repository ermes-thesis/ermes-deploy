import sys
from sender import *

HOSTS = [
    "10.10.101.50",
    "10.10.101.51",
    "10.10.101.52",
    "10.10.101.53",
    "10.10.101.54",
    "10.10.101.57",
]


if __name__ == "__main__":
    colName = sys.argv[1]
    seqColName = colName + "_seq"

    print("Sending GT request...")
    res = send_request('http://localhost:8081/token','GET',**{'headers': {
                'Authorization': 'Bearer fake-token',
                'X-CLIENT-SECRET': 'client-secret'
            } })
    token = res["content"]["group_token"]
    print("Token: ", token)

    print("\nCreating eventual collection...")
    result = send_request('http://10.10.101.53:12345/invoke-function/functionCreateCollections','POST',**{'headers': {
                'X-ERMES-GROUPS': token,
                'X-CLIENT-SECRET': 'client-secret'
            } ,
            'json': {
                'name': colName
            }})
    print(f"✓ Contacted node: {result['url'][7:25]} - Status: {result['status_code']} - Time: {result['elapsed_time']:.3f}s, Body: {result['content']}, Execution host: {result["execution_host"]}")
    
    
    print("\nCreating sequential collection...")
    result = send_request('http://10.10.101.50:12345/invoke-function/functionCreateSeqCollections','POST',**{'headers': {
                'X-ERMES-GROUPS': token,
                'X-CLIENT-SECRET': 'client-secret'
            } ,
            'json': {
                'name': seqColName
            }})
    print(f"✓ Contacted node: {result['url'][7:25]} - Status: {result['status_code']} - Time: {result['elapsed_time']:.3f}s, Body: {result['content']}, Execution host: {result["execution_host"]}")
    
    time.sleep(1)
        
    print('\nUsing collection...')
    requests_list = []
    
    for i in range(300):
        for host in HOSTS:
            if host == "10.10.101.57" and i > 100:
                requests_list.append({
                    'url': 'http://' + host + ':12345/invoke-function/functionUseTwoCollections/1.0.1',
                    'method': 'POST',
                    'headers': {
                        'Content-Type': 'application/json',
                        'X-CLIENT-SECRET': 'client-secret',
                        'X-ERMES-GROUPS': token,
                        'X-ERMES-QUERY': '{\"eventual\": {\"name\": \"'+colName+'\"},\"sequential\": {\"name\": \"'+seqColName+'\"}}'
                    },
                    'json': {
                    'data': 'write number '+ str(i) +" from " + host,
                    }
                })
            else:
                requests_list.append({
                    'url': 'http://' + host + ':12345/invoke-function/functionReadTwoCollections/1.0.1',
                    'method': 'POST',
                    'headers': {
                        'Content-Type': 'application/json',
                        'X-CLIENT-SECRET': 'client-secret',
                        'X-ERMES-GROUPS': token,
                        'X-ERMES-QUERY': '{\"eventual\": {\"name\": \"'+colName+'\"},\"sequential\": {\"name\": \"'+seqColName+'\"}}'
                    },
                    'json': {
                    'data': 'write number '+ str(i) +" from " + host,
                    }
                })

    print("Sending parallel requests with different configurations...\n")
    results = send_parallel_requests(requests_list, max_workers=20)
    print_summary(results)
