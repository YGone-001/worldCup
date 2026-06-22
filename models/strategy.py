import itertools
from models.predictor import predict_match

def generate_accumulators(teams_dict, matches_data):
    value_bets = []

    for group in matches_data.get('groups', []):
        for match in group.get('matches', []):
            if not match.get('odds'):
                continue
            
            home_team = teams_dict.get(match['home'])
            away_team = teams_dict.get(match['away'])
            if not home_team or not away_team:
                continue
                
            pred = predict_match(home_team, away_team, match['odds'])
            
            if pred.get('ev_analysis'):
                for outcome, label in [('home', '主胜'), ('draw', '平局'), ('away', '客胜')]:
                    analysis = pred['ev_analysis'][outcome]
                    if analysis['is_value']:
                        if outcome == 'home':
                            odds = float(match['odds']['home_win'])
                            prob = pred['model_probabilities']['home_win'] / 100.0
                        elif outcome == 'draw':
                            odds = float(match['odds']['draw'])
                            prob = pred['model_probabilities']['draw'] / 100.0
                        else:
                            odds = float(match['odds']['away_win'])
                            prob = pred['model_probabilities']['away_win'] / 100.0
                            
                        value_bets.append({
                            'match_id': match['id'],
                            'match_name': f"{home_team['name']} vs {away_team['name']}",
                            'outcome': label,
                            'odds': odds,
                            'prob': prob,
                            'ev': analysis['ev']
                        })

    value_bets.sort(key=lambda x: x['ev'], reverse=True)
    
    best_double = None
    if len(value_bets) >= 2:
        best_ev = -1
        for pair in itertools.combinations(value_bets, 2):
            if pair[0]['match_id'] == pair[1]['match_id']:
                continue
            
            comb_odds = pair[0]['odds'] * pair[1]['odds']
            comb_prob = pair[0]['prob'] * pair[1]['prob']
            comb_ev = (comb_prob * comb_odds) - 1
            
            # Prefer higher probability combos even if EV is slightly lower (stability filter)
            score = comb_ev * (comb_prob ** 0.5) 
            
            if score > best_ev and comb_ev > 0:
                best_ev = score
                
                b = comb_odds - 1
                q = 1.0 - comb_prob
                kelly = (comb_prob * b - q) / b if b > 0 else 0
                kelly_pct = max(0, kelly * 0.25) * 100
                
                best_double = {
                    'type': '二串一 (Double)',
                    'legs': [pair[0], pair[1]],
                    'combined_odds': round(comb_odds, 2),
                    'combined_prob': round(comb_prob * 100, 2),
                    'ev': round(comb_ev * 100, 2),
                    'kelly_pct': round(kelly_pct, 2)
                }

    best_treble = None
    if len(value_bets) >= 3:
        best_ev = -1
        for tri in itertools.combinations(value_bets, 3):
            ids = set([t['match_id'] for t in tri])
            if len(ids) < 3:
                continue
            
            comb_odds = tri[0]['odds'] * tri[1]['odds'] * tri[2]['odds']
            comb_prob = tri[0]['prob'] * tri[1]['prob'] * tri[2]['prob']
            comb_ev = (comb_prob * comb_odds) - 1
            
            score = comb_ev * (comb_prob ** 0.5)
            
            if score > best_ev and comb_ev > 0:
                best_ev = score
                
                b = comb_odds - 1
                q = 1.0 - comb_prob
                kelly = (comb_prob * b - q) / b if b > 0 else 0
                kelly_pct = max(0, kelly * 0.25) * 100
                
                best_treble = {
                    'type': '三串一 (Treble)',
                    'legs': [tri[0], tri[1], tri[2]],
                    'combined_odds': round(comb_odds, 2),
                    'combined_prob': round(comb_prob * 100, 2),
                    'ev': round(comb_ev * 100, 2),
                    'kelly_pct': round(kelly_pct, 2)
                }

    return {
        'value_bets_count': len(value_bets),
        'best_double': best_double,
        'best_treble': best_treble
    }
