import math

import config
from models.elo_model import calculate_strength, injury_penalty
from models.poisson_model import (
    expected_goals,
    expected_total_goals,
    score_matrix,
    top_scores,
    win_draw_loss,
)


def suspense_index(prob_home: float, prob_draw: float, prob_away: float):
    probs = [p for p in [prob_home, prob_draw, prob_away] if p > 0.001]
    entropy = -sum(p * math.log2(p) for p in probs)
    normalized = entropy / math.log2(3)
    stars = min(5, max(1, round(normalized * 4) + 1))
    labels = {
        1: "一边倒",
        2: "略有悬念",
        3: "比较焦灼",
        4: "几乎五五开",
        5: "悬念拉满",
    }
    return stars, labels[stars]


def odds_to_probabilities(odds: dict) -> tuple[float, float, float] | None:
    try:
        home = float(odds["home_win"])
        draw = float(odds["draw"])
        away = float(odds["away_win"])
    except (KeyError, TypeError, ValueError):
        return None

    if home <= 1 or draw <= 1 or away <= 1:
        return None

    implied = [1 / home, 1 / draw, 1 / away]
    total = sum(implied)
    return implied[0] / total, implied[1] / total, implied[2] / total


def blend_with_odds(model_probs: tuple[float, float, float], odds: dict | None):
    market_probs = odds_to_probabilities(odds or {})
    weight = max(0.0, min(1.0, config.MODEL_CONFIG.get("odds_weight", 0.0)))
    if not market_probs or weight <= 0:
        return model_probs, None

    blended = tuple(
        model_prob * (1 - weight) + market_prob * weight
        for model_prob, market_prob in zip(model_probs, market_probs)
    )
    return blended, market_probs


def predict_match(home_team: dict, away_team: dict, odds: dict | None = None) -> dict:
    strength_home = calculate_strength(home_team) - injury_penalty(home_team)
    strength_away = calculate_strength(away_team) - injury_penalty(away_team)

    rest_home = home_team.get("rest_days", 7)
    rest_away = away_team.get("rest_days", 7)
    rest_diff = rest_home - rest_away
    
    # +5 Elo per extra day of rest
    strength_home += rest_diff * 5.0
    
    elo_diff = (strength_home - strength_away) / 400.0
    home_boost = 1.0 + elo_diff * 0.15
    away_boost = 1.0 - elo_diff * 0.15
    
    from models.elo_model import get_rating_decay
    home_attack_decay = get_rating_decay(home_team)
    home_defense_decay = get_rating_decay(home_team)
    away_attack_decay = get_rating_decay(away_team)
    away_defense_decay = get_rating_decay(away_team)
    
    # Matchday 3 Motivation
    base_rate = config.MODEL_CONFIG.get("base_goals_per_match", 1.35)
    if home_team.get("group_matchday") == 3 and away_team.get("group_matchday") == 3:
        base_rate *= 0.8
        
    # H2H Mock
    h2h_modifier = (len(home_team.get("name", "")) - len(away_team.get("name", ""))) * 0.02
    home_boost += h2h_modifier
    away_boost -= h2h_modifier

    lambda_home = expected_goals(
        attack=home_team.get("attack_rating", 0.5) * (1.0 - home_attack_decay) * max(0.6, min(1.5, home_boost)),
        defense_opponent=away_team.get("defense_rating", 0.5) * (1.0 - away_defense_decay),
        base_rate=base_rate,
    )
    lambda_away = expected_goals(
        attack=away_team.get("attack_rating", 0.5) * (1.0 - away_attack_decay) * max(0.6, min(1.5, away_boost)),
        defense_opponent=home_team.get("defense_rating", 0.5) * (1.0 - home_defense_decay),
        base_rate=base_rate,
    )

    matrix = score_matrix(lambda_home, lambda_away)
    model_home, model_draw, model_away = win_draw_loss(matrix)
    (p_home, p_draw, p_away), market_probs = blend_with_odds(
        (model_home, model_draw, model_away),
        odds,
    )

    # EV Analysis (Value Bet)
    ev_analysis = {
        "home": {"ev": 0.0, "is_value": False},
        "draw": {"ev": 0.0, "is_value": False},
        "away": {"ev": 0.0, "is_value": False},
    }
    
    if odds and market_probs:
        try:
            home_odds = float(odds.get("home_win", 0))
            draw_odds = float(odds.get("draw", 0))
            away_odds = float(odds.get("away_win", 0))
            
            def calc_kelly(model_p: float, odds_val: float) -> float:
                if odds_val <= 1.0: return 0.0
                b = odds_val - 1.0
                q = 1.0 - model_p
                f_star = (model_p * b - q) / b
                # 1/4 Fractional Kelly
                return max(0.0, f_star * 0.25)

            kelly_home = calc_kelly(model_home, home_odds)
            kelly_draw = calc_kelly(model_draw, draw_odds)
            kelly_away = calc_kelly(model_away, away_odds)
            
            ev_home = (model_home * home_odds) - 1
            ev_draw = (model_draw * draw_odds) - 1
            ev_away = (model_away * away_odds) - 1
            
            ev_analysis["home"] = {"ev": round(ev_home * 100, 1), "is_value": ev_home > 0.05, "kelly_pct": round(kelly_home * 100, 2)}
            ev_analysis["draw"] = {"ev": round(ev_draw * 100, 1), "is_value": ev_draw > 0.05, "kelly_pct": round(kelly_draw * 100, 2)}
            ev_analysis["away"] = {"ev": round(ev_away * 100, 1), "is_value": ev_away > 0.05, "kelly_pct": round(kelly_away * 100, 2)}
        except (ValueError, TypeError):
            pass

    top3 = top_scores(matrix, 3)
    stars, label = suspense_index(p_home, p_draw, p_away)
    goals_pred = expected_total_goals(lambda_home, lambda_away)

    return {
        "home_team": {
            "name": home_team["name"],
            "code": home_team["code"],
            "flag": home_team.get("flag", ""),
            "strength": round(strength_home, 1),
        },
        "away_team": {
            "name": away_team["name"],
            "code": away_team["code"],
            "flag": away_team.get("flag", ""),
            "strength": round(strength_away, 1),
        },
        "probabilities": {
            "home_win": round(p_home * 100),
            "draw": round(p_draw * 100),
            "away_win": round(p_away * 100),
        },
        "model_probabilities": {
            "home_win": round(model_home * 100),
            "draw": round(model_draw * 100),
            "away_win": round(model_away * 100),
        },
        "market": {
            "odds": odds or {},
            "implied_probabilities": {
                "home_win": round(market_probs[0] * 100) if market_probs else None,
                "draw": round(market_probs[1] * 100) if market_probs else None,
                "away_win": round(market_probs[2] * 100) if market_probs else None,
            },
            "weight": config.MODEL_CONFIG.get("odds_weight", 0.0) if market_probs else 0,
        },
        "top_scores": top3,
        "expected_goals": {
            "home": round(lambda_home, 2),
            "away": round(lambda_away, 2),
        },
        "goals_prediction": goals_pred,
        "suspense": {
            "stars": stars,
            "label": label,
        },
        "ev_analysis": ev_analysis,
        "key_info": {
            "home_notes": home_team.get("notes", []),
            "away_notes": away_team.get("notes", []),
            "home_injuries": home_team.get("injuries", []),
            "away_injuries": away_team.get("injuries", []),
            "home_key_players": home_team.get("key_players", []),
            "away_key_players": away_team.get("key_players", []),
            "home_rest_days": rest_home,
            "away_rest_days": rest_away,
        },
    }


def predict_whatif(
    home_team: dict,
    away_team: dict,
    current_minute: int,
    home_score: int,
    away_score: int,
    home_red: int,
    away_red: int,
) -> dict:
    """Predicts the final outcome given the current match state."""
    # Apply red card penalties (e.g. -50 Elo per red card)
    strength_home = calculate_strength(home_team) - injury_penalty(home_team) - (home_red * 50)
    strength_away = calculate_strength(away_team) - injury_penalty(away_team) - (away_red * 50)

    elo_diff = (strength_home - strength_away) / 400.0
    home_boost = 1.0 + elo_diff * 0.15
    away_boost = 1.0 - elo_diff * 0.15

    # Base lambda
    lambda_home_base = expected_goals(
        attack=home_team.get("attack_rating", 0.5) * max(0.6, min(1.5, home_boost)),
        defense_opponent=away_team.get("defense_rating", 0.5),
        base_rate=config.MODEL_CONFIG.get("base_goals_per_match", 1.35),
    )
    lambda_away_base = expected_goals(
        attack=away_team.get("attack_rating", 0.5) * max(0.6, min(1.5, away_boost)),
        defense_opponent=home_team.get("defense_rating", 0.5),
        base_rate=config.MODEL_CONFIG.get("base_goals_per_match", 1.35),
    )

    # Time decay: remaining lambda (Non-linear decay for realism)
    # The second half historically has more goals. Using power 0.85 means
    # at 45 mins, (0.5)^0.85 = ~0.55 (55% expected goals remain).
    linear_ratio = max(0.0, (90.0 - current_minute) / 90.0)
    remaining_ratio = math.pow(linear_ratio, 0.85)
    
    lambda_home_rem = lambda_home_base * remaining_ratio
    lambda_away_rem = lambda_away_base * remaining_ratio

    # Probability matrix for the *remaining* goals
    matrix_rem = score_matrix(lambda_home_rem, lambda_away_rem)
    
    # Calculate final match outcome probabilities by shifting with current score
    p_home_win, p_draw, p_away_win = 0.0, 0.0, 0.0
    for i in range(10):
        for j in range(10):
            prob = matrix_rem[i][j]
            if prob < 0.0001:
                continue
            final_home = home_score + i
            final_away = away_score + j
            if final_home > final_away:
                p_home_win += prob
            elif final_home == final_away:
                p_draw += prob
            else:
                p_away_win += prob

    # Expected goals are current goals + remaining lambda
    exp_home = home_score + lambda_home_rem
    exp_away = away_score + lambda_away_rem
    
    # For goals_prediction (Total Goals > 2.5), we need to shift as well
    goals_pred_rem = expected_total_goals(lambda_home_rem, lambda_away_rem)
    # We must rebuild the most likely total goals based on shifted values.
    # Simple approximation for UI:
    current_total = home_score + away_score
    rem_most_likely = goals_pred_rem["most_likely"]
    
    # Precise calculation for > 2.5
    # If current total >= 3, over 2.5 is 100%
    p_over_2_5 = 0.0
    p_under_2_5 = 0.0
    for i in range(10):
        for j in range(10):
            prob = matrix_rem[i][j]
            if current_total + i + j > 2.5:
                p_over_2_5 += prob
            else:
                p_under_2_5 += prob

    stars, label = suspense_index(p_home_win, p_draw, p_away_win)

    return {
        "probabilities": {
            "home_win": round(p_home_win * 100),
            "draw": round(p_draw * 100),
            "away_win": round(p_away_win * 100),
        },
        "expected_goals": {
            "home": round(exp_home, 2),
            "away": round(exp_away, 2),
        },
        "goals_prediction": {
            "most_likely": current_total + rem_most_likely,
            "over_2_5": p_over_2_5,
            "under_2_5": p_under_2_5
        },
        "suspense": {
            "stars": stars,
            "label": label,
        }
    }


def generate_probability_trend(
    home_team: dict,
    away_team: dict,
    current_minute: int,
    home_score: int,
    away_score: int,
    home_red: int,
    away_red: int,
) -> list:
    """Generates a trend of probabilities from current_minute to 90 mins."""
    trend = []
    # Plot from current minute up to 90, in steps of 5 mins
    start = max(0, min(90, current_minute))
    
    for minute in range(start, 91, 5):
        # We ensure the last point is exactly 90 if it isn't hit by step 5
        if minute == 90 and (start % 5 != 0) and len(trend) > 0 and trend[-1]['minute'] == 90:
            break
            
        pred = predict_whatif(
            home_team, away_team, minute, home_score, away_score, home_red, away_red
        )
        trend.append({
            "minute": minute,
            "home_win": pred["probabilities"]["home_win"],
            "draw": pred["probabilities"]["draw"],
            "away_win": pred["probabilities"]["away_win"],
        })
        
    # Ensure minute 90 is always the last point if it wasn't hit
    if trend and trend[-1]["minute"] != 90:
        pred = predict_whatif(
            home_team, away_team, 90, home_score, away_score, home_red, away_red
        )
        trend.append({
            "minute": 90,
            "home_win": pred["probabilities"]["home_win"],
            "draw": pred["probabilities"]["draw"],
            "away_win": pred["probabilities"]["away_win"],
        })
        
    return trend
