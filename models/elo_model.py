"""
改良 Elo Rating 模型
融合球队身价、近期状态、大赛经验进行实力评估
"""
import math


def expected_win_prob(elo_a: float, elo_b: float) -> float:
    """基础Elo预期胜率"""
    return 1.0 / (1.0 + 10 ** ((elo_b - elo_a) / 400.0))


def enhanced_elo(base_elo: float, squad_value_million: float,
                 recent_form: list, tournament_experience: float) -> float:
    """
    增强Elo评分
    - base_elo: 基础Elo评分
    - squad_value_million: 球队身价(百万欧元)
    - recent_form: 近5场结果 [1=胜, 0.5=平, 0=负]
    - tournament_experience: 大赛经验 [0-1]
    """
    # 身价因子：对数化处理，避免极端值
    value_factor = math.log(squad_value_million / 100.0 + 1) * 40

    # 近期状态因子：近5场加权平均，近期权重更高
    if recent_form:
        weights = [0.35, 0.25, 0.20, 0.12, 0.08]
        n = min(len(recent_form), 5)
        weighted_form = sum(recent_form[i] * weights[i] for i in range(n))
        form_factor = (weighted_form - 0.5) * 60  # 中心化
    else:
        form_factor = 0

    # 大赛经验因子
    experience_factor = tournament_experience * 30

    return base_elo + value_factor + form_factor + experience_factor


def calculate_strength(team_data: dict) -> float:
    """从球队数据计算综合实力值"""
    return enhanced_elo(
        base_elo=team_data.get("elo_rating", 1500),
        squad_value_million=team_data.get("squad_value_million", 50),
        recent_form=team_data.get("recent_form", [0.5]),
        tournament_experience=team_data.get("tournament_experience", 0.3)
    )


def injury_penalty(team_data: dict) -> float:
    """伤病减损：根据是否是核心球员以及伤病程度扣除实力值"""
    injuries = team_data.get("injuries", [])
    key_players = team_data.get("key_players", [])
    
    total_penalty = 0.0
    
    for inj in injuries:
        # 提取名字并判断状态
        name = inj
        multiplier = 1.0
        
        if "伤疑" in inj:
            multiplier = 0.5
            name = inj.replace("(伤疑)", "").replace("伤疑", "").strip()
        elif "恢复中" in inj:
            multiplier = 0.7
            name = inj.replace("(恢复中)", "").replace("恢复中", "").strip()
            
        # 基础惩罚
        is_key = any(kp in name or name in kp for kp in key_players)
        base_penalty = 25.0 if is_key else 8.0
        
        total_penalty += base_penalty * multiplier
        
    return total_penalty

def get_rating_decay(team_data: dict) -> float:
    """获取球队攻防评分的衰减比例，最高0.4(即下降40%)"""
    injuries = team_data.get("injuries", [])
    key_players = team_data.get("key_players", [])
    
    decay = 0.0
    for inj in injuries:
        name = inj
        multiplier = 1.0
        
        if "伤疑" in inj:
            multiplier = 0.5
            name = inj.replace("(伤疑)", "").replace("伤疑", "").strip()
        elif "恢复中" in inj:
            multiplier = 0.7
            name = inj.replace("(恢复中)", "").replace("恢复中", "").strip()
            
        # 如果是核心球员，每次受伤导致 15% (0.15) 评分衰减
        is_key = any(kp in name or name in kp for kp in key_players)
        if is_key:
            decay += 0.15 * multiplier
        else:
            decay += 0.05 * multiplier # 普通球员 5%
            
    return min(decay, 0.4) # 最大不超过 40% 衰减
