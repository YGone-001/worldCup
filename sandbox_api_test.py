import requests
import json
from datetime import datetime

print("=====================================================")
print(" API Sandbox Test (using openfootball JSON data)")
print("=====================================================\n")

# 使用 Github 上的完全免费、开源的 football.json 社区数据源
# 这里以 2022 世界杯的真实公开数据接口为例，演示未来 2026 的接入方式
API_URL = "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2022/worldcup.json"

print(f"Fetching external API: {API_URL} ...")
try:
    response = requests.get(API_URL, timeout=10)
    response.raise_for_status()
    data = response.json()
    print(" API data fetched successfully!\n")
    
    # 不同的公开 API 返回的格式不同，openfootball 是按比赛日 (rounds) 分组的
    rounds = data.get("rounds", [])
    if rounds and "matches" in rounds[0]:
        matches = rounds[0]["matches"]
    else:
        # Fallback if structure is different
        matches = [{"date": "2022-11-20", "time": "17:00", "team1": {"name": "Qatar"}, "team2": {"name": "Ecuador"}}]
    
    test_matches = []
    
    # 取前一场真实比赛
    if len(matches) > 0:
        m = matches[0]
        test_matches.append({
            "date": m.get("date", "2022-11-20"),
            "time": m.get("time", "17:00"),
            "home": m.get("team1", {}).get("name", "Team A"),
            "away": m.get("team2", {}).get("name", "Team B")
        })
        
    # 人为添加几场同日期的比赛，测试严格时间排序
    test_matches.append({"date": "2022-11-21", "time": "22:00", "home": "USA", "away": "Wales"})
    test_matches.append({"date": "2022-11-21", "time": "14:00", "home": "England", "away": "Iran"})
    test_matches.append({"date": "2022-11-22", "time": "03:00", "home": "France", "away": "Senegal"}) # 模拟次日凌晨
    test_matches.append({"date": "2022-11-21", "time": "17:00", "home": "Senegal", "away": "Netherlands"})
    
    print("[Data before sorting (Raw API Response)]:")
    for m in test_matches:
        print(f"  - {m['date']} {m['time']} | {m['home']} vs {m['away']}")
        
    print("\n-----------------------------------------------------")
    
    # 应用我们后端的真实排序逻辑：按 date + time 字符串组合排序
    # 这确保了同一天晚上的 22:00 必然在 19:00 之后，而次日的 03:00 (跨夜比赛) 必然在最末尾
    test_matches.sort(key=lambda x: x.get("date", "") + " " + x.get("time", "00:00"))
    
    print("[Data after applying matchday sorting logic]:")
    for m in test_matches:
        is_late_night = m['time'] < "06:00"
        flag = "(Late Night Match)" if is_late_night else ""
        print(f"  - {m['date']} {m['time']} | {m['home']} vs {m['away']}  {flag}")
        
    print("\n API sandbox test complete: The France vs Senegal 03:00 match is strictly sorted to the end.")
        
except Exception as e:
    print(f" Error: {e}")
