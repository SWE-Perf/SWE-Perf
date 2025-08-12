import requests
import time

TIMEOUT = 10
def request_(url, headers=None):
    max_try = 10
    try_ = 0
    while try_ < max_try:
        try:
            if headers!=None:
                response = requests.get(url,
                                        allow_redirects=True,
                                        timeout=TIMEOUT,
                                        headers=headers)
            else:
                response = requests.get(url)
            if response.status_code == 403:
                raise TypeError(f"{url} get 403 error")
            elif response.status_code == 404:
                return response
        except Exception as e:
            try_ += 1
            time.sleep(try_*10)
            print("Try {} times for {}".format(try_, url))
        else:
            break
    return response