import urllib.request
import urllib.error

req = urllib.request.Request('http://127.0.0.1:8000/api/gpu/summary')
req.add_header('Authorization', 'Bearer MOCK')
try:
    response = urllib.request.urlopen(req)
    print("SUCCESS")
    print(response.read().decode('utf-8'))
except urllib.error.HTTPError as e:
    print('HTTP ERROR', e.code)
    print(e.read().decode('utf-8'))
except Exception as e:
    print('OTHER ERROR', e)
