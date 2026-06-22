import json
from models.predictor import predict_match

with open('data/teams.json', 'r', encoding='utf-8') as f:
    teams_data = json.load(f)

teams_dict = {t['code']: t for t in teams_data['teams']}

with open('data/matches.json', 'r', encoding='utf-8') as f:
    matches_data = json.load(f)

stars_5 = []
stars_4 = []

for group in matches_data['groups']:
    for match in group['matches']:
        home = teams_dict.get(match['home'])
        away = teams_dict.get(match['away'])
        if home and away:
            pred = predict_match(home, away, match.get('odds'))
            stars = pred['suspense']['stars']
            if stars == 5:
                stars_5.append(f"{home['name']} vs {away['name']}")
            elif stars == 4:
                stars_4.append(f"{home['name']} vs {away['name']}")

with open('suspense_matches.txt', 'w', encoding='utf-8') as f:
    f.write("5-STAR MATCHES: " + ", ".join(stars_5) + "\n")
    f.write("4-STAR MATCHES: " + ", ".join(stars_4[:5]) + "\n")
