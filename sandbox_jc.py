import requests
import re

url = "https://trade.500.com/jczq/"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
}

try:
    res = requests.get(url, headers=headers, timeout=10)
    res.encoding = 'gb2312'
    html = res.text
    
    matches = re.findall(r'homesxname="([^"]+)"\s+awaysxname="([^"]+)".*?value="([^"]+)"', html)
    print("Found matches via regex:", len(matches))
    for m in matches[:5]:
        print(m)
except Exception as e:
    print("Error:", e)
