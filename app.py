from flask import Flask, jsonify, render_template, request

import config
from models.predictor import predict_match, predict_whatif, generate_probability_trend
from models.calibrator import add_result_comparison, compute_calibration
from utils.data_loader import (
    add_odds,
    add_time_status,
    get_all_teams,
    get_beijing_now,
    get_groups_overview,
    get_match_by_id,
    get_odds_map,
    get_schedule,
    get_team,
    get_today_matches,
    get_team_rest_days,
    get_group_matchday,
)


app = Flask(__name__)
app.config.from_object(config)


def enrich_match(match: dict) -> dict:
    home = get_team(match["home"])
    away = get_team(match["away"])
    if not home:
        home = {
            "name": match.get("home_name", match["home"]),
            "code": match.get("home", ""),
            "attack_rating": 0.5,
            "defense_rating": 0.5,
        }
    if not away:
        away = {
            "name": match.get("away_name", match["away"]),
            "code": match.get("away", ""),
            "attack_rating": 0.5,
            "defense_rating": 0.5,
        }

    enriched = dict(match)
    home = {**home, "name": home.get("name") or match.get("home_name", match["home"]), "flag": home.get("flag") or match.get("home_flag", "")}
    away = {**away, "name": away.get("name") or match.get("away_name", match["away"]), "flag": away.get("flag") or match.get("away_flag", "")}
    
    match_date = match.get("date", "")
    home["rest_days"] = get_team_rest_days(match["home"], match_date)
    away["rest_days"] = get_team_rest_days(match["away"], match_date)
    
    home["group_matchday"] = get_group_matchday(match["home"], match_date)
    away["group_matchday"] = get_group_matchday(match["away"], match_date)
    
    enriched["prediction"] = predict_match(home, away, odds=enriched.get("odds"))
    enriched["home_team"] = home
    enriched["away_team"] = away
    # 添加实际结果对比（已完赛的比赛）
    enriched = add_result_comparison(enriched)
    return enriched


@app.route("/")
def index():
    now = get_beijing_now()
    odds_map = get_odds_map()
    matches = [
        enrich_match(add_odds(add_time_status(m, now), odds_map))
        for m in get_schedule()
    ]
    matches.sort(key=lambda x: x.get("date", "") + " " + x.get("time", "00:00"))

    match_groups = []
    for match in matches:
        if not match_groups or match_groups[-1]["date"] != match["date"]:
            match_groups.append({"date": match["date"], "matches": []})
        match_groups[-1]["matches"].append(match)

    # 计算模型校准统计
    calibration = compute_calibration(matches)

    return render_template(
        "index.html",
        matches=matches,
        match_groups=match_groups,
        display_date="完整赛程",
        beijing_now=now.strftime("%Y-%m-%d %H:%M"),
        active_page="index",
        calibration=calibration,
    )


@app.route("/match/<match_id>")
def match_detail(match_id):
    match = get_match_by_id(match_id)
    if not match:
        return render_template("index.html", matches=[], display_date="", active_page="index"), 404
    return render_template("match.html", match=enrich_match(add_odds(match)))


@app.route("/groups")
def groups():
    return render_template("groups.html", groups=get_groups_overview(), active_page="groups")



@app.route("/api/today")
def api_today():
    odds_map = get_odds_map()
    matches = [add_odds(m, odds_map) for m in get_today_matches(include_finished=True)]
    return jsonify([enrich_match(m) for m in matches])


@app.route("/api/schedule")
def api_schedule():
    now = get_beijing_now()
    odds_map = get_odds_map()
    matches = [
        enrich_match(add_odds(add_time_status(m, now), odds_map))
        for m in get_schedule()
    ]
    matches.sort(key=lambda x: x.get("date", "") + " " + x.get("time", "00:00"))
    return jsonify(matches)


@app.route("/api/match/<match_id>")
def api_match(match_id):
    match = get_match_by_id(match_id)
    if not match:
        return jsonify({"error": "Match not found"}), 404
    return jsonify(enrich_match(add_odds(match)))


@app.route("/api/match/<match_id>/simulate", methods=["POST"])
def api_match_simulate(match_id):
    match = get_match_by_id(match_id)
    if not match:
        return jsonify({"error": "Match not found"}), 404
        
    data = request.json or {}
    minute = int(data.get("minute", 0))
    home_score = int(data.get("home_score", 0))
    away_score = int(data.get("away_score", 0))
    home_red = int(data.get("home_red", 0))
    away_red = int(data.get("away_red", 0))
    
    enriched = enrich_match(match)
    home_team = enriched["home_team"]
    away_team = enriched["away_team"]
    
    prediction = predict_whatif(
        home_team, away_team, minute, home_score, away_score, home_red, away_red
    )
    trend = generate_probability_trend(
        home_team, away_team, minute, home_score, away_score, home_red, away_red
    )
    
    return jsonify({
        "prediction": prediction,
        "trend": trend
    })


@app.route("/api/groups")
def api_groups():
    return jsonify(get_groups_overview())

from models.backtester import run_backtest

@app.route("/backtest")
def backtest_page():
    return render_template("backtest.html")

@app.route("/api/v1/backtest")
def api_backtest():
    # You can get query params for initial_bankroll, bet_size, ev_threshold if needed
    result = run_backtest()
    return jsonify(result)

from models.simulator import simulate_tournament

@app.route("/tournament")
def tournament_page():
    return render_template("tournament.html")

@app.route("/api/v1/tournament")
def api_tournament():
    result = simulate_tournament(iterations=1000)
    return jsonify(result)
@app.route("/api/teams")
def api_teams():
    return jsonify(get_all_teams())


if __name__ == "__main__":
    print("[WorldCup] Prediction system starting...")
    print(f"[WorldCup] Visit http://{config.HOST}:{config.PORT}")
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
