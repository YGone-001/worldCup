"""
========================================================================
  世界杯预测模型沙盒自测 (Sandbox Self-Test)
  基于全部已完赛比赛，验证模型的精准度和校准表现
========================================================================
"""
import sys, json, math
sys.stdout.reconfigure(encoding='utf-8')
sys.path.append('c:\\Users\\pc\\Desktop\\worldCup')

from utils.data_loader import get_schedule, get_team
from models.predictor import predict_match
from models.poisson_model import expected_goals

schedule = get_schedule()
finished = [m for m in schedule if m.get('score') and m['score'].get('ft')]

print("=" * 90)
print("  2026 世界杯 · 预测模型沙盒自测报告")
print(f"  已完赛比赛数: {len(finished)}")
print("=" * 90)

# ---- 逐场校验 ----
correct_outcome = 0
correct_top3_score = 0
total_brier = 0.0
total_log_loss = 0.0
total_goals_error = 0.0
upset_count = 0

results = []

for m in finished:
    home_code = m['home']
    away_code = m['away']
    home = get_team(home_code) or {
        'name': m.get('home_name', home_code), 'code': home_code,
        'attack_rating': 0.5, 'defense_rating': 0.5
    }
    away = get_team(away_code) or {
        'name': m.get('away_name', away_code), 'code': away_code,
        'attack_rating': 0.5, 'defense_rating': 0.5
    }
    home = {**home, 'name': home.get('name') or home_code, 'code': home.get('code', home_code)}
    away = {**away, 'name': away.get('name') or away_code, 'code': away.get('code', away_code)}

    pred = predict_match(home, away)
    probs = pred['probabilities']
    ft = m['score']['ft']
    actual_score = f"{ft[0]}-{ft[1]}"

    # 实际结果
    if ft[0] > ft[1]:
        actual = 'home_win'
    elif ft[0] == ft[1]:
        actual = 'draw'
    else:
        actual = 'away_win'

    # 预测结果 (概率最高的)
    predicted = max(probs, key=probs.get)

    # 胜平负命中
    hit = (predicted == actual)
    if hit:
        correct_outcome += 1

    # Top3 比分命中
    top3 = pred.get('top_scores', [])
    top3_scores = [s['score'] for s in top3]
    score_hit = actual_score in top3_scores
    if score_hit:
        correct_top3_score += 1

    # Brier Score
    for outcome in ['home_win', 'draw', 'away_win']:
        forecast = probs[outcome] / 100.0
        actual_flag = 1.0 if outcome == actual else 0.0
        total_brier += (forecast - actual_flag) ** 2

    # Log Loss
    actual_prob = probs[actual] / 100.0
    total_log_loss += -math.log(max(actual_prob, 1e-15))

    # 预期进球误差
    exp_home = pred['expected_goals']['home']
    exp_away = pred['expected_goals']['away']
    goals_error = abs(exp_home - ft[0]) + abs(exp_away - ft[1])
    total_goals_error += goals_error

    # 冷门检测 (模型给实际结果的概率 < 25%)
    is_upset = actual_prob < 0.25
    if is_upset:
        upset_count += 1

    home_name = m.get('home_name', home_code)
    away_name = m.get('away_name', away_code)
    
    results.append({
        'match': f"{home_name} vs {away_name}",
        'score': actual_score,
        'predicted': predicted,
        'actual': actual,
        'hit': hit,
        'score_hit': score_hit,
        'probs': probs,
        'actual_prob': actual_prob,
        'exp_goals': f"{exp_home:.1f}-{exp_away:.1f}",
        'goals_error': goals_error,
        'is_upset': is_upset,
        'suspense': pred['suspense'],
    })

# ---- 输出逐场结果 ----
print(f"\n{'比赛':^30} {'比分':^6} {'预测':^10} {'实际':^10} {'命中':^4} {'实际概率':^8} {'预期比分':^10} {'误差':^5} {'冷门':^4}")
print("-" * 90)
for r in results:
    labels = {'home_win': '主胜', 'draw': '平局', 'away_win': '客胜'}
    flag = 'O' if r['hit'] else 'X'
    upset_flag = '!!!' if r['is_upset'] else ''
    print(f"{r['match']:>30} {r['score']:^6} {labels[r['predicted']]:^10} {labels[r['actual']]:^10} {flag:^4} {r['actual_prob']*100:>5.1f}%  {r['exp_goals']:^10} {r['goals_error']:>4.1f} {upset_flag:>4}")

# ---- 汇总统计 ----
n = len(finished)
accuracy = correct_outcome / n * 100
brier = total_brier / n
log_loss = total_log_loss / n
avg_goals_error = total_goals_error / n
score_hit_rate = correct_top3_score / n * 100

print("\n" + "=" * 90)
print("  模型校准汇总")
print("=" * 90)
print(f"  胜平负命中率:           {correct_outcome}/{n} = {accuracy:.1f}%")
print(f"  Top3比分命中率:          {correct_top3_score}/{n} = {score_hit_rate:.1f}%")
print(f"  Brier Score:             {brier:.4f}  (越低越好, 0=完美, 0.25=随机)")
print(f"  Log Loss:                {log_loss:.4f}  (越低越好)")
print(f"  平均进球数误差:          {avg_goals_error:.2f} 球/场")
print(f"  冷门比赛数:              {upset_count}/{n} ({upset_count/n*100:.1f}%)")

# ---- 悬念指数准确性分析 ----
print("\n" + "=" * 90)
print("  悬念指数 vs 实际净胜球分析")
print("=" * 90)

from collections import defaultdict
star_stats = defaultdict(lambda: {'count': 0, 'avg_goal_diff': 0, 'total_goal_diff': 0, 'draws': 0})

for r, m in zip(results, finished):
    ft = m['score']['ft']
    goal_diff = abs(ft[0] - ft[1])
    stars = r['suspense']['stars']
    star_stats[stars]['count'] += 1
    star_stats[stars]['total_goal_diff'] += goal_diff
    if goal_diff == 0:
        star_stats[stars]['draws'] += 1

labels_map = {1: '一边倒', 2: '略有悬念', 3: '比较焦灼', 4: '几乎五五开', 5: '悬念拉满'}
print(f"  {'星级':>8} {'标签':>10} {'场数':>4} {'平均净胜球':>10} {'平局率':>8}")
for stars in sorted(star_stats.keys()):
    s = star_stats[stars]
    avg_diff = s['total_goal_diff'] / s['count']
    draw_rate = s['draws'] / s['count'] * 100
    print(f"  {stars}星     {labels_map[stars]:>10} {s['count']:>4} {avg_diff:>10.1f} {draw_rate:>7.1f}%")

# ---- 基准线对比 ----
print("\n" + "=" * 90)
print("  模型表现基准线对比")
print("=" * 90)
print(f"  指标           本模型     | 行业基准(世界杯)")
print(f"  ──────────────────────────────────────────────")
print(f"  胜平负命中率   {accuracy:>5.1f}%    | ~45-55% (顶级模型)")
print(f"  Brier Score    {brier:>6.4f}   | ~0.20 (良好) / 0.18 (优秀)")
print(f"  Log Loss       {log_loss:>6.4f}   | ~1.00 (良好) / 0.90 (优秀)")
print(f"  比分命中率     {score_hit_rate:>5.1f}%    | ~15-25% (Top3)")
print("=" * 90)
