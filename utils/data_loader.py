import json
import os
from datetime import datetime, timedelta, timezone

import config
from utils import live_provider


BEIJING_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")
MATCHDAY_CUTOFF_HOUR = 6
MATCH_DURATION_MINUTES = 120


def load_json(filename: str) -> dict:
    filepath = os.path.join(config.DATA_DIR, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def get_all_teams() -> dict:
    data = load_json("teams.json")
    return data.get("teams", {})


def get_team(code: str) -> dict:
    teams = get_all_teams()
    return teams.get(code, {})


def get_schedule() -> list:
    if config.DATA_SOURCE in {"auto", "api"} and config.SCHEDULE_API_URL:
        try:
            return live_provider.fetch_schedule()
        except Exception:
            if config.DATA_SOURCE == "api":
                raise

    data = load_json("schedule.json")
    return data.get("matches", [])


def get_odds_map() -> dict:
    # 优先使用专门的 The Odds API 适配器
    if config.THE_ODDS_API_KEY:
        try:
            from utils.odds_provider import fetch_odds_map
            return fetch_odds_map()
        except Exception as e:
            print(f"Failed to fetch from The Odds API: {e}")

    # Fallback to existing logic
    if config.DATA_SOURCE in {"auto", "api"} and config.ODDS_API_URL:
        try:
            return live_provider.fetch_odds_map()
        except Exception:
            if config.DATA_SOURCE == "api":
                raise
    return {}


def get_beijing_now() -> datetime:
    return datetime.now(BEIJING_TZ)


def get_match_datetime(match: dict) -> datetime:
    match_date = datetime.strptime(match.get("date", ""), "%Y-%m-%d").date()
    match_time = datetime.strptime(match.get("time", "00:00"), "%H:%M").time()
    return datetime.combine(match_date, match_time, tzinfo=BEIJING_TZ)


def get_team_rest_days(team_code: str, current_match_date: str) -> int:
    """计算球队距离上一场比赛的休息天数"""
    if not current_match_date or not team_code:
        return 7
        
    try:
        current_dt = datetime.strptime(current_match_date, "%Y-%m-%d")
    except ValueError:
        return 7

    schedule = get_schedule()
    last_match_dt = None
    
    for match in schedule:
        m_date = match.get("date", "")
        if not m_date:
            continue
        # 只要比赛包含该球队且日期早于当前比赛
        if match.get("home") == team_code or match.get("away") == team_code:
            try:
                m_dt = datetime.strptime(m_date, "%Y-%m-%d")
                if m_dt < current_dt:
                    if last_match_dt is None or m_dt > last_match_dt:
                        last_match_dt = m_dt
            except ValueError:
                continue
                
    if last_match_dt:
        return (current_dt - last_match_dt).days
    return 7  # 默认首场比赛休息充足


def get_group_matchday(team_code: str, current_match_date: str) -> int:
    """计算当前是该球队在小组赛的第几轮 (1, 2, 3)"""
    if not current_match_date or not team_code:
        return 1
        
    try:
        current_dt = datetime.strptime(current_match_date, "%Y-%m-%d")
    except ValueError:
        return 1

    schedule = get_schedule()
    
    # 获取该队所有小组赛
    team_group_matches = []
    for match in schedule:
        if match.get("group") and not match.get("is_knockout"):  # 假设没is_knockout就是小组赛
            if match.get("home") == team_code or match.get("away") == team_code:
                try:
                    m_date = match.get("date", "")
                    if m_date:
                        m_dt = datetime.strptime(m_date, "%Y-%m-%d")
                        team_group_matches.append(m_dt)
                except ValueError:
                    continue
                    
    # 按日期排序
    team_group_matches.sort()
    
    # 找到当前日期排第几个
    for i, m_dt in enumerate(team_group_matches):
        if m_dt.date() == current_dt.date():
            return i + 1
            
    return 1 # 找不到就默认第一轮


def get_logical_matchday(now: datetime | None = None):
    now = now or get_beijing_now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=BEIJING_TZ)
    now = now.astimezone(BEIJING_TZ)
    if now.hour < MATCHDAY_CUTOFF_HOUR:
        return now.date() - timedelta(days=1)
    return now.date()


def add_time_status(match: dict, now: datetime | None = None) -> dict:
    now = (now or get_beijing_now()).astimezone(BEIJING_TZ)
    match_copy = dict(match)
    start_at = get_match_datetime(match_copy)
    end_at = start_at + timedelta(minutes=MATCH_DURATION_MINUTES)

    if now < start_at:
        status = "upcoming"
    elif now <= end_at:
        status = "live"
    else:
        status = "finished"

    match_copy["beijing_datetime"] = start_at.isoformat()
    match_copy["status"] = status
    return match_copy


def add_odds(match: dict, odds_map: dict | None = None) -> dict:
    if match.get("odds"):
        return match
        
    omap = odds_map or get_odds_map()
    
    # Try exact match ID
    odds = omap.get(str(match.get("id", "")))
    
    # Fallback to team combination: HOME_CODE-AWAY_CODE
    if not odds:
        odds = omap.get(f"{match.get('home')}-{match.get('away')}")
        
    if not odds:
        return match
        
    match_copy = dict(match)
    match_copy["odds"] = odds
    return match_copy


def get_today_matches(include_finished: bool = False, now: datetime | None = None) -> list:
    now = (now or get_beijing_now()).astimezone(BEIJING_TZ)
    logical_today = get_logical_matchday(now)
    logical_date_str = logical_today.strftime("%Y-%m-%d")
    tomorrow_str = (logical_today + timedelta(days=1)).strftime("%Y-%m-%d")

    today_matches = []
    for match in get_schedule():
        match_date = match.get("date")
        match_time = match.get("time", "00:00")
        if match_date == logical_date_str:
            today_matches.append(add_time_status(match, now))
        elif match_date == tomorrow_str and match_time < f"{MATCHDAY_CUTOFF_HOUR:02d}:00":
            today_matches.append(add_time_status(match, now))

    if not include_finished:
        today_matches = [m for m in today_matches if m.get("status") != "finished"]

    today_matches.sort(key=lambda x: x.get("date", "") + " " + x.get("time", "00:00"))
    return today_matches


def get_upcoming_matches(limit: int | None = None, now: datetime | None = None) -> list:
    now = (now or get_beijing_now()).astimezone(BEIJING_TZ)
    upcoming = [
        add_time_status(match, now)
        for match in get_schedule()
        if get_match_datetime(match) + timedelta(minutes=MATCH_DURATION_MINUTES) >= now
    ]
    upcoming.sort(key=lambda x: x.get("date", "") + " " + x.get("time", "00:00"))
    return upcoming[:limit] if limit else upcoming


def get_match_by_id(match_id: str) -> dict:
    for match in get_schedule():
        if match.get("id") == match_id:
            return add_time_status(match)
    return {}


def get_group_matches(group: str) -> list:
    return [m for m in get_schedule() if m.get("group") == group]


def get_groups_overview() -> dict:
    schedule = get_schedule()
    groups_map = {}
    
    for match in schedule:
        g = match.get("group", "")
        if "Group " in g:
            g = g.replace("Group ", "")
        elif "组" in g:
            g = g.replace("组", "")
            
        g = g.strip()
        if len(g) != 1 or not g.isalpha():
            continue
            
        if g not in groups_map:
            groups_map[g] = set()
            
        home = match.get("home")
        away = match.get("away")
        if home: groups_map[g].add(home)
        if away: groups_map[g].add(away)
        
    teams = get_all_teams()
    result = {}
    
    if groups_map:
        for g in sorted(groups_map.keys()):
            result[g] = []
            for code in groups_map[g]:
                team = teams.get(code)
                if not team:
                    team = {"code": code, "name": code, "fifa_ranking": "-"}
                result[g].append(team)
            # Sort by FIFA ranking if available
            def sort_key(t):
                rank = t.get("fifa_ranking")
                if isinstance(rank, int):
                    return rank
                try:
                    return int(rank)
                except (ValueError, TypeError):
                    return 999
            result[g].sort(key=sort_key)
    else:
        for _, team in teams.items():
            group_name = team.get("group", "?")
            if group_name and group_name != "?":
                result.setdefault(group_name, []).append(team)
        result = dict(sorted(result.items()))
        
    return result


def get_live_standings() -> dict:
    groups = get_groups_overview()
    schedule = get_schedule()
    
    # Initialize stats
    stats = {}
    for g, teams in groups.items():
        for team in teams:
            code = team["code"]
            stats[code] = {
                "team": team,
                "pld": 0,
                "w": 0,
                "d": 0,
                "l": 0,
                "gf": 0,
                "ga": 0,
                "gd": 0,
                "pts": 0
            }
            
    now = get_beijing_now()
    for raw_match in schedule:
        match = add_time_status(raw_match, now)
        if match.get("status") == "finished" and match.get("score") and match["score"].get("ft"):
            h = match.get("home")
            a = match.get("away")
            try:
                hg, ag = match["score"]["ft"]
            except (ValueError, TypeError):
                continue
                
            if h in stats:
                stats[h]["pld"] += 1
                stats[h]["gf"] += hg
                stats[h]["ga"] += ag
                stats[h]["gd"] += (hg - ag)
                if hg > ag:
                    stats[h]["w"] += 1
                    stats[h]["pts"] += 3
                elif hg == ag:
                    stats[h]["d"] += 1
                    stats[h]["pts"] += 1
                else:
                    stats[h]["l"] += 1
                    
            if a in stats:
                stats[a]["pld"] += 1
                stats[a]["gf"] += ag
                stats[a]["ga"] += hg
                stats[a]["gd"] += (ag - hg)
                if ag > hg:
                    stats[a]["w"] += 1
                    stats[a]["pts"] += 3
                elif ag == hg:
                    stats[a]["d"] += 1
                    stats[a]["pts"] += 1
                else:
                    stats[a]["l"] += 1
                    
    # Rebuild grouped and sorted standings
    standings = {}
    for g, teams in groups.items():
        group_stats = [stats[t["code"]] for t in teams]
        # Sort by PTS (desc), GD (desc), GF (desc), FIFA ranking (asc)
        def sort_key(s):
            rank = s["team"].get("fifa_ranking")
            try:
                rank_val = int(rank)
            except (ValueError, TypeError):
                rank_val = 999
            return (-s["pts"], -s["gd"], -s["gf"], rank_val)
            
        group_stats.sort(key=sort_key)
        standings[g] = group_stats
        
    return standings
