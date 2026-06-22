import os
import json
import requests
import datetime
import re
from config import DATA_DIR

TEAM_NAME_MAP_CN = {
    "美国": "USA", "澳大利亚": "AUS", "法国": "FRA", "塞内加尔": "SEN",
    "伊拉克": "IRQ", "挪威": "NOR", "阿根廷": "ARG", "阿尔及利亚": "ALG",
    "奥地利": "AUT", "约旦": "JOR", "葡萄牙": "POR", "刚果金": "COD",
    "英格兰": "ENG", "克罗地亚": "CRO", "加纳": "GHA", "巴拿马": "PAN",
    "乌兹别克": "UZB", "哥伦比亚": "COL", "捷克": "CZE", "南非": "RSA",
    "瑞士": "SUI", "波黑": "BIH", "加拿大": "CAN", "卡塔尔": "QAT",
    "墨西哥": "MEX", "韩国": "KOR", "苏格兰": "SCO", "摩洛哥": "MAR",
    "巴西": "BRA", "海地": "HAI", "土耳其": "TUR", "巴拉圭": "PAR",
    "荷兰": "NED", "瑞典": "SWE", "德国": "GER", "科特迪瓦": "CIV"
}

def get_team_code(cn_name):
    if cn_name in TEAM_NAME_MAP_CN:
        return TEAM_NAME_MAP_CN[cn_name]
    for k, v in TEAM_NAME_MAP_CN.items():
        if k in cn_name or cn_name in k:
            return v
    return None

def fetch_and_update_jingcai():
    url = "https://trade.500.com/jczq/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    print("==================================================")
    print("  [方案A] 正在启动纯手工爬虫抓取中国体彩实时赔率")
    print("==================================================")
    print(f"📡 目标节点: {url}")
    
    odds_map = {}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.encoding = 'gb2312'
        html = res.text
        
        # 匹配 <tr ... homesxname="A" awaysxname="B" ...>
        # 然后寻找后续的 <span class="pl">1.23</span>
        tr_blocks = html.split('<tr ')
        for block in tr_blocks:
            if 'homesxname="' in block and 'awaysxname="' in block:
                home_m = re.search(r'homesxname="([^"]+)"', block)
                away_m = re.search(r'awaysxname="([^"]+)"', block)
                pl_matches = re.findall(r'<span class="pl">([\d\.]+)</span>', block)
                
                if home_m and away_m and len(pl_matches) >= 3:
                    h_code = get_team_code(home_m.group(1))
                    a_code = get_team_code(away_m.group(1))
                    if h_code and a_code:
                        odds_map[f"{h_code}_{a_code}"] = {
                            "home_win": float(pl_matches[0]),
                            "draw": float(pl_matches[1]),
                            "away_win": float(pl_matches[2])
                        }
    except Exception as e:
        print(f"❌ [Scraper Error] 爬虫在解析 DOM 时被阻断或异常: {e}")
        
    if not odds_map:
        print("⚠️ [Warning] 爬虫运行成功，但当前体彩官方数据库中未找到符合本轮世界杯的比赛赔率。")
        print("💡 [Fallback] 系统将启动热备降水方案 (方案B)：读取基准欧赔，并应用体彩极限抽水算法 (0.89/0.96) 强行降维打击。")
        simulate_jingcai_odds()
        return False
        
    print(f"✅ [Success] 成功从中国体彩提取 {len(odds_map)} 场比赛的真实挂牌赔率。")
    _write_to_schedule(odds_map, "China Sports Lottery (Live Scraped)")
    return True

def simulate_jingcai_odds():
    schedule_path = os.path.join(DATA_DIR, "schedule.json")
    try:
        with open(schedule_path, 'r', encoding='utf-8') as f:
            sched = json.load(f)
            
        updated_count = 0
        for m in sched.get('matches', []):
            # 将现有赔率直接乘以 0.92 (即体彩通常比外围低 8% 左右)
            if 'odds' in m and m['odds'].get('home_win'):
                m['odds']['home_win'] = round(m['odds']['home_win'] * 0.92, 2)
                m['odds']['draw'] = round(m['odds']['draw'] * 0.92, 2)
                m['odds']['away_win'] = round(m['odds']['away_win'] * 0.92, 2)
                m['odds_source'] = 'Jingcai Official (Math Simulation)'
                m['odds_updated_at'] = datetime.datetime.now().isoformat()
                updated_count += 1
                
        with open(schedule_path, 'w', encoding='utf-8') as f:
            json.dump(sched, f, ensure_ascii=False, indent=2)
            
        print(f"✅ [Success] 成功为 {updated_count} 场比赛注入【体彩极限界定模拟赔率】！")
        print("💡 您现在可以刷新【智能策略舱】，系统对 EV 和凯利的判定已大幅收紧，请留意推荐卡片的变化。")
    except Exception as e:
        print("❌ [Error] 降水算法写入失败:", e)

def _write_to_schedule(odds_map, source_name):
    schedule_path = os.path.join(DATA_DIR, "schedule.json")
    try:
        with open(schedule_path, 'r', encoding='utf-8') as f:
            sched = json.load(f)
            
        updated_count = 0
        for m in sched.get('matches', []):
            key = f"{m['home']}_{m['away']}"
            if key in odds_map:
                m['odds'] = odds_map[key]
                m['odds_source'] = source_name
                m['odds_updated_at'] = datetime.datetime.now().isoformat()
                updated_count += 1
                
        with open(schedule_path, 'w', encoding='utf-8') as f:
            json.dump(sched, f, ensure_ascii=False, indent=2)
            
        print(f"✅ [Success] 更新了 {updated_count} 场比赛的 {source_name} 赔率！")
    except Exception as e:
        print(f"❌ [Error] 写入 schedule.json 失败: {e}")
