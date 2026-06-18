from utils.data_loader import get_schedule


def run_backtest(initial_bankroll: float = 1000.0, bet_size: float = 100.0, ev_threshold: float = 5.0, strategy: str = "kelly") -> dict:
    """
    运行历史回测模拟。
    策略：寻找 EV > threshold 的盘口，使用固定仓位 bet_size 虚拟下注。
    """
    from app import enrich_match
    schedule = get_schedule()
    
    bankroll = initial_bankroll
    bankroll_history = [initial_bankroll]
    matches_processed = 0
    bets_placed = 0
    wins = 0
    losses = 0
    
    for match in schedule:
        # 只测试已完赛的比赛，且有比分和赔率
        if match.get("status") == "finished" and "home_score" in match and "away_score" in match and match.get("odds"):
            enriched = enrich_match(match)
            prediction = enriched.get("prediction", {})
            ev_analysis = prediction.get("ev_analysis", {})
            
            home_score = match.get("home_score", 0)
            away_score = match.get("away_score", 0)
            
            actual_outcome = ""
            if home_score > away_score:
                actual_outcome = "home"
            elif home_score == away_score:
                actual_outcome = "draw"
            else:
                actual_outcome = "away"
            
            bet_placed = False
            
            # 检查是否有价值投注
            for outcome in ["home", "draw", "away"]:
                analysis = ev_analysis.get(outcome, {})
                if analysis.get("is_value") and analysis.get("ev", 0) > ev_threshold:
                    bets_placed += 1
                    bet_placed = True
                    
                    # 确定下注额
                    current_bet = bet_size
                    if strategy == "kelly":
                        # 使用 Kelly Percentage，上限 5% 仓位
                        kelly_pct = analysis.get("kelly_pct", 0) / 100.0
                        capped_kelly = min(kelly_pct, 0.05)
                        current_bet = bankroll * capped_kelly
                        # 如果没有剩余资金，直接跳过
                        if current_bet < 0.1:
                            current_bet = 0.0
                    
                    if current_bet > 0:
                        # 确定对应赔率的 key
                        odds_key = outcome + "_win" if outcome != "draw" else "draw"
                        odds = float(match.get("odds", {}).get(odds_key, 0))
                        
                        if outcome == actual_outcome:
                            # 赢了，赚回利润
                            profit = (current_bet * odds) - current_bet
                            bankroll += profit
                            wins += 1
                        else:
                            # 输了，损失本金
                            bankroll -= current_bet
                            losses += 1
                        
            # 如果这场比赛下注了，记录资金曲线
            if bet_placed:
                bankroll_history.append(bankroll)
                matches_processed += 1
                
    net_profit = bankroll - initial_bankroll
    total_invested = bets_placed * bet_size
    roi = (net_profit / total_invested) * 100 if total_invested > 0 else 0
    win_rate = (wins / bets_placed) * 100 if bets_placed > 0 else 0
    
    return {
        "initial_bankroll": initial_bankroll,
        "final_bankroll": round(bankroll, 2),
        "net_profit": round(net_profit, 2),
        "roi": round(roi, 2),
        "win_rate": round(win_rate, 2),
        "bets_placed": bets_placed,
        "matches_processed": matches_processed,
        "wins": wins,
        "losses": losses,
        "bankroll_history": [round(b, 2) for b in bankroll_history],
    }
