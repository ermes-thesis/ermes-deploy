import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict
import time
GREEN = "\033[92m"
RED = "\033[91m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RESET = "\033[0m"
DIM = "\033[2m"


def get_json_response(response):
    content = None
    if response is not None:
        try:
            content = response.json()
        except Exception:
            content = response.text.strip() or None
    return content

def print_result(res):
    elapsed_ms = res['elapsed_time'] / 1_000_000  # ns → ms
    
    local = res.get('local')
    if local is True:
        node_symbol = "💻"
    elif local is False:
        node_symbol = "🌐"
    else:
        node_symbol = ""
        
    fn_name = res.get('fn', '')
    if len(fn_name) > 30:
        fn_name = fn_name[:30 - 3] + "..."
    fn_name = f"{fn_name:<{30}}"


    if res['success']:
        status = res.get('status_code', 0) or 0

        if status == 200:
            symbol, color = "✓", GREEN
        elif 400 <= status < 500:
            symbol, color = "⚠", YELLOW
        elif 500 <= status < 600:
            symbol, color = "✗", RED
        else:
            symbol, color = "🌀", CYAN

        status = f"{res['status_code']}" if res['status_code'] else "-"
        node = res['execution_host'] or "-"
        body_preview = res.get('content')
        if isinstance(body_preview, (dict, list)):
            body_preview = str(body_preview)
        if isinstance(body_preview, str):
            body_preview = body_preview.strip()
            if len(body_preview) > 80:
                body_preview = body_preview[:77] + "..."
        else:
            body_preview = str(body_preview)

        print(
            f"{color}{symbol}{RESET} [{CYAN}{res['host']}{RESET}] "
            f"{fn_name} "
            f"| Status: {YELLOW}{status}{RESET} "
            f"| Node: {DIM}{node} {node_symbol}{RESET} "
            f"| Time: {elapsed_ms:7.2f} ms "
            f"| Body: {body_preview}"
        )
    else:
        print(
            f"{RED}✗{RESET} [{CYAN}{res['host']}{RESET}] "
            f"{res['fn']:<25} "
            f"| Time: {elapsed_ms:7.2f} ms "
            f"| {RED}Error:{RESET} {res['error']}"
        )

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
    start_time = time.perf_counter_ns()
    try:
        response = requests.request(method, url, **kwargs)
        elapsed = time.perf_counter_ns() - start_time
        
        host = ""
        local = None
        if "X-ERMES-EXECUTION-HOST" in response.headers:
            host = response.headers["X-ERMES-EXECUTION-HOST"]
            if host != "" and host in url:
                local = True
            else:
                local = False
        
        return {
            'host': url[7:25],
            'fn': url[42:],
            'status_code': response.status_code,
            'execution_host': host,
            'local': local,
            'elapsed_time': elapsed,
            'success': True,
            'content_length': len(response.content),
            'content': get_json_response(response),
            'error': None
        }
    except Exception as e:
        elapsed = time.perf_counter_ns() - start_time
        return {
            'host': url[7:25],
            'fn': url[42:],
            'elapsed_time': elapsed,
            'success': False,
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
                print_result(result)
            except Exception as e:
                url = future_to_config[future]
                print(f"{RED}✗{RESET} {url} - Error: {str(e)}")
    return results

def print_summary(results: List[Dict]):
    """Print a summary of all requests."""
    total = len(results)
    total_local = sum(1 for r in results if r['local'] is True)
    total_remote = sum(1 for r in results if r['local'] is False)
    successful = sum(1 for r in results if r['success'] and r['status_code'] == 200)
    failed = total - successful
    avg_time = sum(r['elapsed_time'] for r in results) / 1_000_000 / total if total > 0 else 0
    avg_time_local = sum(r['elapsed_time'] for r in results if r['local'] is True) / 1_000_000 / total_local if total_local > 0 else 0
    avg_time_remote = sum(r['elapsed_time'] for r in results if r['local'] is False) / 1_000_000 / total_remote if total_remote > 0 else 0

    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Total requests: {total}")
    print(f"Total local requests: {total_local}")
    print(f"Total remote requests: {total_remote}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Average response time: {avg_time:} ms")
    print(f"Average local response time: {avg_time_local:} ms")
    print(f"Average remote response time: {avg_time_remote:} ms")
    print("="*60)

