"""
模型校准模块 (Model Calibration)

对比赛预测结果与实际比分进行对比分析，计算预测准确率、Brier 分数等校准指标，
帮助评估和改进预测模型的表现。
"""

from __future__ import annotations

import math
from typing import Any


# ---------------------------------------------------------------------------
# 内部工具函数
# ---------------------------------------------------------------------------

def _determine_outcome(home_goals: int, away_goals: int) -> str:
    """根据比分判定比赛结果：home_win / draw / away_win"""
    if home_goals > away_goals:
        return "home_win"
    elif home_goals == away_goals:
        return "draw"
    else:
        return "away_win"


def _get_predicted_outcome(probabilities: dict[str, int | float]) -> str:
    """
    从概率字典中选出预测结果（概率最高的那项）。
    如果概率相同，优先级：home_win > draw > away_win（主队优先）。
    """
    outcomes = ["home_win", "draw", "away_win"]
    best = max(outcomes, key=lambda o: probabilities.get(o, 0))
    return best


def _safe_log(p: float, eps: float = 1e-15) -> float:
    """安全的对数计算，防止 log(0)"""
    return math.log(max(p, eps))


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------

def add_result_comparison(match: dict) -> dict:
    """
    为已结束的比赛添加「预测 vs 实际」的对比数据。

    输入 match 需要包含：
        - match['score']['ft'] = [home_goals, away_goals]   (已结束比赛)
        - match['prediction']['probabilities'] = {
              'home_win': 52, 'draw': 24, 'away_win': 24
          }                                                   (百分制整数)

    返回原始 match 的浅拷贝，额外增加 match['result'] 字段：
        {
            "actual_score": "2-0",
            "actual_outcome": "home_win",
            "predicted_outcome": "home_win",
            "prediction_correct": True,
            "outcome_probability": 0.52,
            "predicted_score_hit": False,
            "confidence_gap": 28        # 最高概率 - 次高概率
        }

    如果比赛尚未结束或数据不完整，返回原始 match 不作修改。

    Args:
        match: 包含比分和预测数据的比赛字典

    Returns:
        添加了 result 字段的比赛字典（浅拷贝）
    """
    enriched = dict(match)  # 浅拷贝，避免修改原始数据

    # ---- 校验：比分数据是否存在 ----
    score = match.get("score")
    if not score or not isinstance(score, dict):
        return enriched

    ft = score.get("ft")
    if not ft or not isinstance(ft, (list, tuple)) or len(ft) < 2:
        return enriched

    try:
        home_goals = int(ft[0])
        away_goals = int(ft[1])
    except (ValueError, TypeError):
        return enriched

    # ---- 校验：预测数据是否存在 ----
    prediction = match.get("prediction")
    if not prediction or not isinstance(prediction, dict):
        return enriched

    probabilities = prediction.get("probabilities")
    if not probabilities or not isinstance(probabilities, dict):
        return enriched

    # 确保三个概率值都存在
    required_keys = ("home_win", "draw", "away_win")
    if not all(k in probabilities for k in required_keys):
        return enriched

    # ---- 计算对比结果 ----
    actual_outcome = _determine_outcome(home_goals, away_goals)
    predicted_outcome = _get_predicted_outcome(probabilities)

    # 将百分制整数转成 0~1 的概率值
    prob_values = {k: probabilities[k] / 100.0 for k in required_keys}

    # 模型给实际结果分配的概率
    outcome_probability = prob_values[actual_outcome]

    # 置信度差距：最高概率 - 次高概率（百分制）
    sorted_probs = sorted(probabilities[k] for k in required_keys)
    confidence_gap = sorted_probs[2] - sorted_probs[1]

    # 提取队名
    home_team_name = _extract_team_name(match, "home")
    away_team_name = _extract_team_name(match, "away")

    # 检查预测比分是否命中
    actual_score_str = f"{home_goals}-{away_goals}"
    predicted_score_hit = False
    predicted_score_strs = []
    top_scores = prediction.get("top_scores")
    if top_scores and isinstance(top_scores, list):
        predicted_score_strs = [
            s.get("score", "") for s in top_scores if isinstance(s, dict)
        ]
        predicted_score_hit = actual_score_str in predicted_score_strs

    # 赛后对账动态文案生成
    three_tiers = "/".join(predicted_score_strs[:3]) if predicted_score_strs else "暂无"
    
    home_prob = probabilities.get("home_win", 0)
    away_prob = probabilities.get("away_win", 0)
    draw_prob = probabilities.get("draw", 0)
    
    if predicted_outcome == "home_win":
        predicted_prob_text = f"看好{home_team_name}{home_prob}%(高于{away_team_name}{away_prob}%)"
        predicted_target = home_team_name
    elif predicted_outcome == "away_win":
        predicted_prob_text = f"看好{away_team_name}{away_prob}%(高于{home_team_name}{home_prob}%)"
        predicted_target = away_team_name
    else:
        predicted_prob_text = f"看好平局{draw_prob}%"
        predicted_target = "平局"
        
    win_loss_desc = f"看好{predicted_target}赢,结果{actual_score_str},命中" if (predicted_outcome == actual_outcome) else f"看好{predicted_target}赢,结果{actual_score_str},没中"
    if actual_outcome == "draw" and predicted_outcome != "draw":
        win_loss_desc = f"看好{predicted_target}赢,结果{actual_score_str}平,没中"
        
    score_desc = f"{actual_score_str}在三档内,准确命中" if predicted_score_hit else f"{actual_score_str}不在三档(最多三球),没分析准"
    
    review_text = match.get("review_text", "")
    if not review_text:
        if predicted_outcome == actual_outcome:
            review_text = f"本场比赛走向符合预期，{home_team_name} 与 {away_team_name} 按照模型概率给出了合理结果。"
        else:
            review_text = f"发生意外偏离，{home_team_name} {actual_score_str} {away_team_name} 的剧本超出了赛前模型推演的主要范畴。"

    # 中文标签映射
    outcome_labels = {
        "home_win": "主队胜",
        "draw": "平局",
        "away_win": "客队胜",
    }

    enriched["result"] = {
        "actual_score": actual_score_str,
        "actual_outcome": actual_outcome,
        "actual_outcome_label": outcome_labels.get(actual_outcome, actual_outcome),
        "predicted_outcome": predicted_outcome,
        "predicted_outcome_label": outcome_labels.get(predicted_outcome, predicted_outcome),
        "prediction_correct": predicted_outcome == actual_outcome,
        "outcome_probability": round(outcome_probability * 100),
        "predicted_probability": probabilities.get(predicted_outcome, 0),
        "predicted_score_hit": predicted_score_hit,
        "confidence_gap": confidence_gap,
        "three_tiers": three_tiers,
        "predicted_prob_text": predicted_prob_text,
        "win_loss_desc": win_loss_desc,
        "score_desc": score_desc,
        "review_text": review_text
    }

    return enriched


def compute_calibration(matches: list[dict]) -> dict[str, Any]:
    """
    计算整体模型校准指标。

    流程：
        1. 对每场比赛调用 add_result_comparison() 进行结果对比
        2. 汇总所有已结束比赛的预测表现
        3. 计算 Brier 分数、对数损失等指标

    Args:
        matches: 比赛列表，每项须包含 score 和 prediction 字段

    Returns:
        {
            "total_matches":          总比赛数,
            "total_finished":         已结束且有预测的比赛数,
            "correct_predictions":    预测正确数,
            "accuracy_pct":           准确率（百分比）,
            "brier_score":            Brier 分数（越低越好，0 为完美）,
            "log_loss":               对数损失（越低越好）,
            "avg_outcome_probability": 模型对实际结果的平均信心,
            "score_hit_count":        比分命中次数,
            "score_hit_pct":          比分命中率,
            "avg_confidence_gap":     平均置信度差距,
            "results":                逐场对比结果列表
        }
    """
    results: list[dict] = []
    total_finished = 0
    correct = 0
    score_hits = 0

    # Brier 分数 & 对数损失的累加器
    brier_sum = 0.0
    log_loss_sum = 0.0
    outcome_prob_sum = 0.0
    confidence_gap_sum = 0.0

    for match in matches:
        enriched = add_result_comparison(match)
        result = enriched.get("result")

        if result is None:
            # 比赛未结束或数据不完整，跳过
            continue

        total_finished += 1

        # ---- 逐项统计 ----
        if result["prediction_correct"]:
            correct += 1
        if result["predicted_score_hit"]:
            score_hits += 1

        outcome_prob_sum += result["outcome_probability"]
        confidence_gap_sum += result["confidence_gap"]

        # ---- Brier 分数 ----
        # Brier = (1/N) * Σ (forecast_i - outcome_i)²，对三类结果分别计算
        prediction = match.get("prediction", {})
        probs = prediction.get("probabilities", {})
        actual = result["actual_outcome"]

        for outcome in ("home_win", "draw", "away_win"):
            forecast = probs.get(outcome, 0) / 100.0
            actual_flag = 1.0 if outcome == actual else 0.0
            brier_sum += (forecast - actual_flag) ** 2

        # ---- 对数损失 ----
        # LogLoss = -(1/N) * Σ log(p_actual)
        # outcome_probability 已是百分制，需转回 0~1
        log_loss_sum += -_safe_log(result["outcome_probability"] / 100.0)

        # 将对比信息连同比赛的基本标识一起收集
        match_summary = {
            "match_num": match.get("match_number", match.get("num", "?")),
            "home_team": _extract_team_name(match, "home"),
            "away_team": _extract_team_name(match, "away"),
        }
        match_summary.update(result)
        results.append(match_summary)

    # ---- 汇总 ----
    if total_finished > 0:
        accuracy_pct = round(correct / total_finished * 100, 1)
        brier_score = round(brier_sum / total_finished, 4)
        log_loss = round(log_loss_sum / total_finished, 4)
        avg_outcome_prob = round(outcome_prob_sum / total_finished, 1)
        avg_confidence_gap = round(confidence_gap_sum / total_finished, 1)
        score_hit_pct = round(score_hits / total_finished * 100, 1)
    else:
        accuracy_pct = 0.0
        brier_score = 0.0
        log_loss = 0.0
        avg_outcome_prob = 0.0
        avg_confidence_gap = 0.0
        score_hit_pct = 0.0

    return {
        "total_matches": len(matches),
        "total_finished": total_finished,
        "correct_predictions": correct,
        "accuracy_pct": accuracy_pct,
        "brier_score": brier_score,
        "log_loss": log_loss,
        "avg_outcome_probability": avg_outcome_prob,
        "score_hit_count": score_hits,
        "score_hit_pct": score_hit_pct,
        "avg_confidence_gap": avg_confidence_gap,
        "results": results,
    }


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _extract_team_name(match: dict, side: str) -> str:
    """
    从 match 中提取球队名称。

    兼容两种常见结构：
        - match['home_team']['name']       (predictor 输出格式)
        - match['homeTeam']['name']        (API 原始格式)
        - match['home_team_name']          (扁平格式)
    """
    # 格式1: 嵌套字典 with underscore
    key_underscore = f"{side}_team"
    team_obj = match.get(key_underscore)
    if isinstance(team_obj, dict):
        return team_obj.get("name", team_obj.get("code", "?"))

    # 格式2: 嵌套字典 camelCase
    key_camel = f"{side}Team"
    team_obj = match.get(key_camel)
    if isinstance(team_obj, dict):
        return team_obj.get("name", team_obj.get("code", "?"))

    # 格式3: 扁平 key
    return match.get(f"{side}_team_name", "?")
