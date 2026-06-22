from flask import Flask, jsonify, render_template, request

import config
import threading
import time
import os
from models.predictor import predict_match, predict_whatif, generate_probability_trend
from models.strategy import generate_accumulators
from utils.sporttery_fetcher import fetch_and_update_jingcai
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
    load_json,
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
    from utils.data_loader import get_live_standings
    return render_template("groups.html", groups=get_live_standings(), active_page="groups")



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





@app.route("/api/groups")
def api_groups():
    return jsonify(get_groups_overview())

from models.simulator import simulate_tournament

@app.route("/tournament")
def tournament():
    return render_template("tournament.html", current_page="tournament")

@app.route("/strategy")
def strategy():
    return render_template("strategy.html", current_page="strategy")

@app.route("/api/v1/tournament")
def api_tournament():
    result = simulate_tournament(iterations=1000)
    return jsonify(result)

@app.route("/api/strategy/recommendations")
def api_strategy():
    matches_data = load_json("schedule.json")
    teams_dict = get_all_teams()
    res = generate_accumulators(teams_dict, matches_data)
    return jsonify(res)

@app.route("/api/teams")
def api_teams():
    return jsonify(get_all_teams())


def start_background_scraper():
    def job():
        print("\n🤖 [Auto-Sync] 后台守护进程已启动，每隔 1 小时自动同步体彩/外部赔率...")
        time.sleep(3) # 缓冲几秒等待主服务就绪
        while True:
            try:
                fetch_and_update_jingcai()
            except Exception as e:
                print(f"❌ [Auto-Sync] 同步异常: {e}")
            time.sleep(3600)

    # 仅在实际的 worker 进程中启动，避免 Flask debug 模式下被启动两次
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not config.DEBUG:
        t = threading.Thread(target=job, daemon=True)
        t.start()

if __name__ == "__main__":
    print("[WorldCup] Prediction system starting...")
    start_background_scraper()
    print(f"[WorldCup] Visit http://{config.HOST}:{config.PORT}")
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
