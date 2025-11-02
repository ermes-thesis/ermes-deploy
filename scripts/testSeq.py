import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict
import time
import sys

def send_request(url: str, method: str = 'GET', **kwargs) -> Dict:
    """
    Send a single HTTP request and return the response details.

    Args:
        url: The URL to request
        method: HTTP method (GET, POST, etc.)
        **kwargs: Additional arguments for requests (headers, data, json, etc.)

    Returns:
        Dictionary with response details
    """
    start_time = time.time()
    try:
        response = requests.request(method, url, **kwargs)
        elapsed = time.time() - start_time
        
        host = ""
        if "X-ERMES-EXECUTION-HOST" in response.headers:
            host = response.headers["X-ERMES-EXECUTION-HOST"]
        if host in url:
            host += " (local)"
        
        return {
            'url': url,
            'status_code': response.status_code,
            'execution_host': host,
            'elapsed_time': elapsed,
            'success': True,
            'content_length': len(response.content),
            'content': response.json(),
            'error': None
        }
    except Exception as e:
        elapsed = time.time() - start_time
        return {
            'url': url,
            'status_code': None,
            'execution_host': host,
            'elapsed_time': elapsed,
            'success': False,
            'content': response.json(),
            'content_length': 0,
            'error': str(e)
        }

def send_parallel_requests(
    requests_list: List[Dict],
    max_workers: int = 10
) -> List[Dict]:
    """
    Send multiple HTTP requests in parallel with individual configurations.

    Args:
        requests_list: List of request configurations, each containing:
            - url (required): The URL to request
            - method (optional): HTTP method (default: 'GET')
            - headers (optional): Dictionary of headers
            - json (optional): JSON data to send
            - data (optional): Form data or raw body
            - params (optional): URL parameters
            - timeout (optional): Request timeout
            Any other requests library parameters
        max_workers: Maximum number of parallel threads

    Returns:
        List of response dictionaries
    """
    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all requests with their individual configurations
        future_to_config = {}
        for req_config in requests_list:
            url = req_config.pop('url')
            method = req_config.pop('method', 'GET')
            def send_and_sleep(url0, method0, **req_config0):
                res = send_request(url0, method0, **req_config0)
                time.sleep(0.3)
                return res
            future = executor.submit(send_and_sleep, url, method, **req_config)
            future_to_config[future] = url

        # Collect results as they complete
        for future in as_completed(future_to_config):
            try:
                result = future.result()
                results.append(result)
                print(f"✓ {result['url']} - Status: {result['status_code']} - Time: {result['elapsed_time']:.3f}s, Body: {result['content']}, Execution host: {result["execution_host"]}")
            except Exception as e:
                url = future_to_config[future]
                print(f"✗ {url} - Error: {str(e)}")

    return results

def print_summary(results: List[Dict]):
    """Print a summary of all requests."""
    total = len(results)
    successful = sum(1 for r in results if r['success'])
    failed = total - successful
    avg_time = sum(r['elapsed_time'] for r in results) / total if total > 0 else 0

    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Total requests: {total}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Average response time: {avg_time:.4f}s")
    print("="*60)


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