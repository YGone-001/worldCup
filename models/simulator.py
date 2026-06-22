import math
import random
from collections import defaultdict
from utils.data_loader import get_all_teams

def random_poisson(lam: float) -> int:
    L = math.exp(-lam)
    k = 0
    p = 1.0
    while p > L:
        k += 1
        p *= random.random()
    return k - 1

def simulate_tournament(iterations: int = 1000) -> dict:
    """
    运行蒙特卡洛锦标赛推演，模拟 2026 年 48 队世界杯完整赛制。
    返回各队晋级概率以及最热的决赛对阵组合。
    """
    teams = get_all_teams()
    results = defaultdict(lambda: {"group_adv": 0, "ro16": 0, "qf": 0, "sf": 0, "final": 0, "win": 0})
    
    # 建立小组 (根据 teams.json 中的 group 字段)
    groups = defaultdict(list)
    for code, t in teams.items():
        groups[t.get("group", "A")].append(code)
        
    final_matchups = defaultdict(int)

    for _ in range(iterations):
        # 1. 小组赛阶段
        group_standings = {}
        # 记录所有球队的小组赛积分和净胜球，以便选取最好的小组第三
        global_pts = defaultdict(int)
        global_gd = defaultdict(int)
        global_gf = defaultdict(int)

        for g, members in groups.items():
            pts = defaultdict(int)
            gd = defaultdict(int)
            gf = defaultdict(int)
            for i in range(len(members)):
                for j in range(i+1, len(members)):
                    t1, t2 = members[i], members[j]
                    elo1 = teams[t1].get("elo_rating", 1500)
                    elo2 = teams[t2].get("elo_rating", 1500)
                    diff = (elo1 - elo2) / 400.0
                    lam1 = 1.35 * (1.0 + diff * 0.35)
                    lam2 = 1.35 * (1.0 - diff * 0.35)
                    lam1 = max(0.35, min(lam1, 4.0))
                    lam2 = max(0.35, min(lam2, 4.0))
                    
                    g1 = random_poisson(lam1)
                    g2 = random_poisson(lam2)
                    
                    gd[t1] += g1 - g2
                    gd[t2] += g2 - g1
                    gf[t1] += g1
                    gf[t2] += g2
                    
                    if g1 > g2:
                        pts[t1] += 3
                    elif g1 < g2:
                        pts[t2] += 3
                    else:
                        pts[t1] += 1
                        pts[t2] += 1
            
            # 更新到全局以备挑选第三名
            for t in members:
                global_pts[t] = pts[t]
                global_gd[t] = gd[t]
                global_gf[t] = gf[t]

            # 组内排序：积分 > 净胜球 > 进球数 > 随机
            ranked = sorted(members, key=lambda x: (pts[x], gd[x], gf[x], random.random()), reverse=True)
            group_standings[g] = ranked

        # 2. 选出 32 强: 各组前2名 (24队) + 成绩最好的8个第三名
        ro32_teams = []
        thirds = []
        for g, ranked in group_standings.items():
            if len(ranked) >= 2:
                ro32_teams.extend(ranked[:2])
            if len(ranked) >= 3:
                thirds.append(ranked[2])
                
        # 第三名排行
        thirds.sort(key=lambda x: (global_pts[x], global_gd[x], global_gf[x], random.random()), reverse=True)
        ro32_teams.extend(thirds[:8])
        
        for t in ro32_teams:
            results[t]["group_adv"] += 1

        # 淘汰赛单场胜负函数（无平局，点球大战也算胜负）
        def simulate_knockout(teams_list):
            winners = []
            random.shuffle(teams_list) # 这里为了效率和简便，用随机抽签代替复杂的 FIFA 淘汰赛对阵表
            for i in range(0, len(teams_list), 2):
                t1, t2 = teams_list[i], teams_list[i+1]
                elo1 = teams[t1].get("elo_rating", 1500)
                elo2 = teams[t2].get("elo_rating", 1500)
                # 淘汰赛胜率直接通过 Elo 差值计算
                p1 = 1 / (1 + 10 ** ((elo2 - elo1) / 400.0))
                if random.random() < p1:
                    winners.append(t1)
                else:
                    winners.append(t2)
            return winners

        # 3. 32进16
        ro16_teams = simulate_knockout(ro32_teams)
        for t in ro16_teams: results[t]["ro16"] += 1
        
        # 4. 16进8
        qf_teams = simulate_knockout(ro16_teams)
        for t in qf_teams: results[t]["qf"] += 1
        
        # 5. 8进4
        sf_teams = simulate_knockout(qf_teams)
        for t in sf_teams: results[t]["sf"] += 1
        
        # 6. 半决赛
        finalists = simulate_knockout(sf_teams)
        for t in finalists: results[t]["final"] += 1
        
        # 记录决赛对阵组合 (按字母排序避免不同轮次的重名组合分流)
        matchup = " vs ".join(sorted([teams[finalists[0]].get("name", finalists[0]), teams[finalists[1]].get("name", finalists[1])]))
        final_matchups[matchup] += 1
        
        # 7. 决赛
        champion = simulate_knockout(finalists)[0]
        results[champion]["win"] += 1

    # 统计排行榜
    final_leaderboard = []
    for team_code, stats in results.items():
        team_data = teams.get(team_code, {})
        final_leaderboard.append({
            "code": team_code,
            "name": team_data.get("name", team_code),
            "flag": team_data.get("flag", ""),
            "group_adv": round((stats["group_adv"] / iterations) * 100, 1),
            "ro16": round((stats["ro16"] / iterations) * 100, 1),
            "qf": round((stats["qf"] / iterations) * 100, 1),
            "sf": round((stats["sf"] / iterations) * 100, 1),
            "final": round((stats["final"] / iterations) * 100, 1),
            "win": round((stats["win"] / iterations) * 100, 1),
        })
        
    final_leaderboard.sort(key=lambda x: x["win"], reverse=True)
    
    # 提取最热决赛对决
    top_matchup = max(final_matchups.items(), key=lambda x: x[1]) if final_matchups else ("", 0)
    
    return {
        "leaderboard": final_leaderboard,
        "top_matchup": {
            "teams": top_matchup[0],
            "probability": round((top_matchup[1] / iterations) * 100, 1)
        }
    }
