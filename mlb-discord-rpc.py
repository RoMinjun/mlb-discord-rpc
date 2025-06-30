import os
import time
import sys
import requests
from datetime import datetime, timedelta, timezone
from pypresence import Presence
from pypresence.exceptions import PipeClosed
import tzlocal
from zoneinfo import ZoneInfo
from requests.exceptions import RequestException
from dotenv import load_dotenv

# Load .env variables
load_dotenv()
CLIENT_ID = os.getenv("CLIENT_ID")

if not CLIENT_ID:
    print("CLIENT_ID is not set. Please add it to your .env file.")
    sys.exit(1)

DEFAULT_BASE_ICON_FILLED = "🟦"
DEFAULT_BASE_ICON_EMPTY = "⚪"
DEFAULT_LIVE_INTERVAL = 15
DEFAULT_IDLE_INTERVAL = 90

TEAM_DATA_URL = "https://statsapi.mlb.com/api/v1/teams?sportId=1"
SCHEDULE_URL = "https://statsapi.mlb.com/api/v1/schedule/games/?sportId=1&hydrate=linescore(runners),boxscore,team"
LOGO_TEMPLATE = "https://a.espncdn.com/combiner/i?img=/i/teamlogos/mlb/500/{}.png&h=64&w=64"

try:
    import tomllib
except ModuleNotFoundError:
    import toml as tomllib

def ordinal(n):
    return f"{n}{'th' if 11 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"

def load_config():
    try:
        with open("config.toml", "rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        print("Error loading config.toml:", e)
        return {}

def parse_args(config):
    team_abbr = config.get("team")
    tz_name = config.get("timezone")
    live_only = config.get("live_only", False)

    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--team" and i + 1 < len(args):
            team_abbr = args[i + 1].upper()
        elif arg == "--tz" and i + 1 < len(args):
            tz_name = args[i + 1]
        elif arg == "--live-only":
            live_only = True

    if not team_abbr:
        print("Usage: python script.py --team <TEAM_ABBR> [--tz TIMEZONE] [--live-only]")
        sys.exit(1)

    try:
        local_tz = ZoneInfo(tz_name) if tz_name else ZoneInfo(tzlocal.get_localzone_name())
    except Exception as e:
        print(f"Invalid timezone '{tz_name}':", e)
        sys.exit(1)

    return team_abbr, local_tz, live_only

def get_team_abbr_map():
    try:
        response = requests.get(TEAM_DATA_URL, timeout=10)
        return {team["id"]: team["abbreviation"] for team in response.json().get("teams", [])}
    except RequestException as e:
        print("Failed to fetch team abbreviation map:", e)
        return {}

def fetch_team_info(abbr):
    try:
        response = requests.get(TEAM_DATA_URL, timeout=10)
        for team in response.json().get("teams", []):
            if team["abbreviation"].upper() == abbr.upper():
                return {
                    "id": team["id"],
                    "name": team["name"],
                    "code": team.get("fileCode", abbr.lower()),
                    "abbr": abbr.upper()
                }
    except RequestException as e:
        print("Failed to fetch team info:", e)
    return None

def fetch_live_game(team_id):
    try:
        response = requests.get(SCHEDULE_URL, timeout=10)
        data = response.json()
        games = data.get("dates", [{}])[0].get("games", [])
        for game in games:
            home = game["teams"]["home"]
            away = game["teams"]["away"]
            if team_id in (home["team"]["id"], away["team"]["id"]):
                return game
    except RequestException as e:
        print("Failed to fetch live game:", e)
    return None

def get_next_game_datetime(team_id, local_tz, abbr_map):
    try:
        now_utc = datetime.now(timezone.utc)
        start_date = (now_utc + timedelta(days=1)).date()
        end_date = (now_utc + timedelta(days=7)).date()
        url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&teamId={team_id}&startDate={start_date}&endDate={end_date}"
        response = requests.get(url, timeout=10)
        data = response.json()

        for date_entry in data.get("dates", []):
            for game in date_entry.get("games", []):
                home_id = game["teams"]["home"]["team"]["id"]
                away_id = game["teams"]["away"]["team"]["id"]
                home_abbr = abbr_map.get(home_id, "???")
                away_abbr = abbr_map.get(away_id, "???")
                game_utc = datetime.fromisoformat(game["gameDate"].replace("Z", "+00:00"))
                local_dt = game_utc.astimezone(local_tz)
                tz_abbr = local_dt.strftime('%Z')
                venue = game.get("venue", {}).get("name")
                return f"Next game: {away_abbr} vs {home_abbr} • {local_dt.strftime('%a %H:%M')} {tz_abbr}" + (f" • {venue}" if venue else "")
    except RequestException as e:
        print("Failed to fetch next game:", e)
    return None

def get_pitcher(game, team_id):
    try:
        players = game["boxscore"]["teams"]
        side = "home" if game["teams"]["home"]["team"]["id"] == team_id else "away"
        for pdata in players["away" if side == "home" else "home"]["players"].values():
            if pdata.get("position", {}).get("code") == "P" and pdata.get("stats", {}).get("pitching", {}).get("gamesPitched", 0) > 0:
                return pdata["person"]["fullName"]
    except KeyError:
        pass
    return None

def get_batter(game):
    try:
        batter_id = game["linescore"].get("offense", {}).get("batter", {}).get("id")
        if not batter_id:
            return None
        for side in ["home", "away"]:
            for pdata in game["boxscore"]["teams"][side]["players"].values():
                if pdata["person"]["id"] == batter_id:
                    return pdata["person"]["fullName"]
    except KeyError:
        pass
    return None

def build_presence(game, team_info, local_tz, icons, abbr_map):
    linescore = game.get("linescore", {})
    home = game["teams"]["home"]
    away = game["teams"]["away"]
    status = game["status"]["detailedState"]

    main, opponent = (home, away) if home["team"]["id"] == team_info["id"] else (away, home)
    is_home = home["team"]["id"] == team_info["id"]
    main_abbr = main["team"]["abbreviation"]
    opp_abbr = opponent["team"]["abbreviation"]
    main_score = main["score"]
    opp_score = opponent["score"]

    opponent_logo_url = LOGO_TEMPLATE.format(opponent["team"].get("fileCode", opp_abbr.lower()))
    team_logo_url = LOGO_TEMPLATE.format(team_info["code"])

    outs = linescore.get("outs", "?")
    offense = linescore.get("offense", {})
    base_status = "".join([
        icons["empty"] if offense.get("first") else icons["filled"],
        icons["empty"] if offense.get("second") else icons["filled"],
        icons["empty"] if offense.get("third") else icons["filled"]
    ])

    inning = linescore.get("currentInning", "?")
    inning_state = linescore.get("inningState", "")
    inning_str = f"{inning_state} {ordinal(inning)}" if inning != "?" else "Inning ?"

    pitcher = get_pitcher(game, team_info["id"])
    batter = get_batter(game)

    if game["status"]["abstractGameState"] == "Live":
        state_str = f"{inning_str} | Bases {base_status} | {outs} Out{'s' if outs != 1 else ''}"
        if pitcher:
            state_str += f" | P: {pitcher}"
        if batter:
            state_str += f" | B: {batter}"
    elif status in ["Final", "Game Over"]:
        state_str = "FINAL"
        next_game = get_next_game_datetime(team_info["id"], local_tz, abbr_map)
        if next_game:
            state_str += f" • {next_game}"
    else:
        state_str = status

    return {
        "details": f"{main_abbr} {main_score} vs {opp_abbr} {opp_score}",
        "state": state_str,
        "large_image": team_logo_url,
        "large_text": f"{team_info['name']} | {'Home' if is_home else 'Away'}",
        "small_image": opponent_logo_url,
        "small_text": f"{opponent['team']['name']} | {'Home' if not is_home else 'Away'}"
    }

def connect_rpc():
    while True:
        try:
            rpc = Presence(CLIENT_ID)
            rpc.response_timeout = 5
            rpc.connect()
            print("Connected to Discord RPC.")
            return rpc
        except Exception:
            print("Waiting for Discord... retrying in 5s.")
            time.sleep(5)

def main():
    config = load_config()
    team_abbr, local_tz, live_only = parse_args(config)

    icons = {
        "filled": config.get("display", {}).get("base_icon_filled", DEFAULT_BASE_ICON_FILLED),
        "empty": config.get("display", {}).get("base_icon_empty", DEFAULT_BASE_ICON_EMPTY)
    }

    live_interval = config.get("refresh", {}).get("live_interval", DEFAULT_LIVE_INTERVAL)
    idle_interval = config.get("refresh", {}).get("idle_interval", DEFAULT_IDLE_INTERVAL)

    abbr_map = get_team_abbr_map()
    team_info = fetch_team_info(team_abbr)
    if not team_info:
        print(f"Invalid team abbreviation: {team_abbr}")
        return

    rpc = connect_rpc()

    try:
        while True:
            try:
                game = fetch_live_game(team_info["id"])

                if game:
                    abstract_state = game["status"]["abstractGameState"]
                    if live_only and abstract_state != "Live":
                        rpc.clear()
                        time.sleep(idle_interval)
                        continue
                    try:
                        activity = build_presence(game, team_info, local_tz, icons, abbr_map)
                    except KeyError as e:
                        if str(e) == "'score'":
                            next_game = get_next_game_datetime(team_info["id"], local_tz, abbr_map)
                            if next_game:
                                logo = LOGO_TEMPLATE.format(team_info["code"])
                                rpc.update({
                                    "details": team_info["name"],
                                    "state": next_game,
                                    "large_image": logo,
                                    "large_text": f"{team_info['name']}"
                                })
                                time.sleep(idle_interval)
                                continue
                        raise
                    rpc.update(**activity)
                    time.sleep(live_interval if abstract_state == "Live" else idle_interval)
                else:
                    if live_only:
                        rpc.clear()
                    else:
                        logo = LOGO_TEMPLATE.format(team_info['code'])
                        rpc.update({
                            "details": team_info["name"],
                            "state": "No live game",
                            "large_image": logo,
                            "large_text": f"{team_info['name']}"
                        })
                    time.sleep(idle_interval)

            except PipeClosed:
                print("Lost Discord RPC connection. Reconnecting...")
                rpc = connect_rpc()
            except Exception as e:
                print("Unexpected error:", e)
                time.sleep(5)
    except KeyboardInterrupt:
        print("\nStopped cleanly.")
        try:
            rpc.clear()
        except:
            pass

if __name__ == "__main__":
    main()
