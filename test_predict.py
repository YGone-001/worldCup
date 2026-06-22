import json
from models.predictor import predict_match

with open('data/teams.json', 'r', encoding='utf-8') as f:
    teams_data = json.load(f)

teams_dict = {v['name']: v for k, v in teams_data['teams'].items()}

# The matches are:
matches = [
    ("厄瓜多尔", "库拉索"),
    ("德国", "科特迪瓦"),
    ("日本", "突尼斯"),
    ("荷兰", "瑞典")
]

for home_cn, away_cn in matches:
    home = teams_dict.get(home_cn)
    away = teams_dict.get(away_cn)
    
    if home and away:
        pred = predict_match(home, away, None)
        print(f"Match: {home_cn} vs {away_cn}")
        print(f"Win/Draw/Loss probabilities: {pred['probabilities']}")
        print(f"Goal Expectancy: Home {pred['expected_goals']['home']:.2f} - Away {pred['expected_goals']['away']:.2f}")
        print(f"Most Likely Score (Top 3): {pred['top_scores']}")
        print("-" * 40)
    else:
        print(f"Could not find teams: {home_cn} or {away_cn}")
