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
    print_result(result)        
    
    print("\nCreating sequential collection...")
    result = send_request('http://10.10.101.50:12345/invoke-function/functionCreateSeqCollections','POST',**{'headers': {
                'X-ERMES-GROUPS': token,
                'X-CLIENT-SECRET': 'client-secret'
            } ,
            'json': {
                'name': seqColName
            }})

    print_result(result)    
    print('\nUsing collection...')
    for i in range(20):
        result = send_request('http://10.10.101.54:12345/invoke-function/functionReadTwoCollections/1.0.1','POST',**{'headers': {
                'Content-Type': 'application/json',
                'X-CLIENT-SECRET': 'client-secret',
                'X-ERMES-GROUPS': token,
                'X-ERMES-QUERY': '{\"eventual\": {\"name\": \"'+colName+'\"},\"sequential\": {\"name\": \"'+seqColName+'\"}}'
            } ,
                'json': {
               'data': 'write number '+ str(i) +" from " + "10.10.101.54",
            }})
        print_result(result)    
        time.sleep(0.5)