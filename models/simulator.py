import random
from collections import defaultdict

from utils.data_loader import get_schedule, get_all_teams


def simulate_tournament(iterations: int = 1000) -> dict:
    """
    运行蒙特卡洛锦标赛推演，返回各支球队夺冠和晋级的概率。
    简化版：仅基于目前剩余的小组赛和淘汰赛。
    """
    from app import enrich_match
    schedule = get_schedule()
    teams = get_all_teams()
    
    # 结果统计
    results = defaultdict(lambda: {"group_adv": 0, "qf": 0, "sf": 0, "final": 0, "win": 0})
    
    # 这里为了演示，我们假设随机挑选几支强队作为示例结果，
    # 完整的杯赛模拟需要完整的积分榜逻辑和淘汰赛对阵树构建，代码量较大。
    # 采用一个简化的胜率随机数发生器模拟深层结构。
    
    for _ in range(iterations):
        # 初始化分数
        group_points = defaultdict(int)
        
        # 1. 模拟未进行的小组赛
        for match in schedule:
            if match.get("status") != "finished" and not match.get("is_knockout"):
                home = match.get("home")
                away = match.get("away")
                if not home or not away:
                    continue
                    
                # 简单抽签决定胜负（基于当前模型的一个简化版本，以节省算力）
                # 为了快速响应，我们这里使用 Elo 的简化预期胜率
                elo_h = teams.get(home, {}).get("elo_rating", 1500)
                elo_a = teams.get(away, {}).get("elo_rating", 1500)
                
                diff = (elo_h - elo_a) / 400.0
                p_h = 1 / (1 + 10 ** (-diff))
                p_a = 1 - p_h
                
                # 假定平局概率为固定的 0.25，两边各扣掉 0.125
                p_h = max(0, p_h - 0.125)
                p_a = max(0, p_a - 0.125)
                
                r = random.random()
                if r < p_h:
                    group_points[home] += 3
                elif r < p_h + 0.25:
                    group_points[home] += 1
                    group_points[away] += 1
                else:
                    group_points[away] += 3
                    
        # 2. 淘汰赛抽签（简化版，直接从强队中抽取）
        # 真实环境应该根据小组积分排名，进行 A1 vs B2 等树状推演。
        # 这里仅作功能演示框架。
        alive_teams = list(teams.keys())
        # 按 Elo + 随机扰动排序
        alive_teams.sort(key=lambda t: teams.get(t, {}).get("elo_rating", 1500) + random.gauss(0, 100), reverse=True)
        
        # 记录 16 强 (Group Adv)
        for t in alive_teams[:16]:
            results[t]["group_adv"] += 1
            
        # 记录 8 强 (QF)
        for t in alive_teams[:8]:
            results[t]["qf"] += 1
            
        # 记录 4 强 (SF)
        for t in alive_teams[:4]:
            results[t]["sf"] += 1
            
        # 记录 2 强 (Final)
        for t in alive_teams[:2]:
            results[t]["final"] += 1
            
        # 记录 冠军 (Win)
        results[alive_teams[0]]["win"] += 1
        
    # 计算百分比
    final_leaderboard = []
    for team_code, stats in results.items():
        team_data = teams.get(team_code, {})
        final_leaderboard.append({
            "code": team_code,
            "name": team_data.get("name", team_code),
            "flag": team_data.get("flag", ""),
            "group_adv": round((stats["group_adv"] / iterations) * 100, 1),
            "qf": round((stats["qf"] / iterations) * 100, 1),
            "sf": round((stats["sf"] / iterations) * 100, 1),
            "final": round((stats["final"] / iterations) * 100, 1),
            "win": round((stats["win"] / iterations) * 100, 1),
        })
        
    final_leaderboard.sort(key=lambda x: x["win"], reverse=True)
    return final_leaderboard
