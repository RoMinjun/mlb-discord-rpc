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

DEFAULT_BASE_ICON_FILLED = "⚪"
DEFAULT_BASE_ICON_EMPTY = "🟦"
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

def format_start_time(game, tz):
    """Return formatted local start time for a game."""
    try:
        dt = datetime.fromisoformat(game.get("gameDate").replace("Z", "+00:00"))
        local_dt = dt.astimezone(tz)
        return local_dt.strftime("%a %H:%M %Z")
    except Exception:
        return None

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
    """Return a string describing the team's next scheduled game."""
    try:
        now_utc = datetime.now(timezone.utc)
        start_date = now_utc.date()
        end_date = (now_utc + timedelta(days=7)).date()
        url = (
            f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&teamId={team_id}"
            f"&startDate={start_date}&endDate={end_date}"
        )
        response = requests.get(url, timeout=10)
        data = response.json()

        next_game = None
        next_game_utc = None

        for date_entry in data.get("dates", []):
            for game in date_entry.get("games", []):
                game_utc = datetime.fromisoformat(game["gameDate"].replace("Z", "+00:00"))
                if game_utc <= now_utc:
                    continue
                if next_game_utc is None or game_utc < next_game_utc:
                    next_game = game
                    next_game_utc = game_utc

        if next_game:
            home_id = next_game["teams"]["home"]["team"]["id"]
            away_id = next_game["teams"]["away"]["team"]["id"]
            home_abbr = abbr_map.get(home_id, "???")
            away_abbr = abbr_map.get(away_id, "???")
            local_dt = next_game_utc.astimezone(local_tz)
            tz_abbr = local_dt.strftime("%Z")
            venue = next_game.get("venue", {}).get("name")
            return (
                f"Next game: {away_abbr} vs {home_abbr} • "
                f"{local_dt.strftime('%a %H:%M')} {tz_abbr}"
                + (f" • {venue}" if venue else "")
            )
    except RequestException as e:
        print("Failed to fetch next game:", e)
    return None

def get_next_game_info(team_id, local_tz, abbr_map):
    """Return info about the next game including each team's record."""
    try:
        now_utc = datetime.now(timezone.utc)
        start_date = now_utc.date()
        end_date = (now_utc + timedelta(days=7)).date()
        url = (
            f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&teamId={team_id}"
            f"&startDate={start_date}&endDate={end_date}"
        )
        response = requests.get(url, timeout=10)
        data = response.json()

        next_game = None
        next_game_utc = None

        for date_entry in data.get("dates", []):
            for game in date_entry.get("games", []):
                game_utc = datetime.fromisoformat(game["gameDate"].replace("Z", "+00:00"))
                if game_utc <= now_utc:
                    continue
                if next_game_utc is None or game_utc < next_game_utc:
                    next_game = game
                    next_game_utc = game_utc

        if next_game:
            home = next_game["teams"]["home"]
            away = next_game["teams"]["away"]
            home_team = home["team"]
            away_team = away["team"]
            home_abbr = abbr_map.get(home_team["id"], "???")
            away_abbr = abbr_map.get(away_team["id"], "???")
            local_dt = next_game_utc.astimezone(local_tz)
            tz_abbr = local_dt.strftime("%Z")
            venue = next_game.get("venue", {}).get("name")
            start_str = f"{local_dt.strftime('%a %H:%M')} {tz_abbr}"
            desc = (
                f"Next game: {away_abbr} vs {home_abbr} • "
                f"{start_str}" + (f" • {venue}" if venue else "")
            )
            opponent = away if home_team["id"] == team_id else home
            opp_team = opponent["team"]
            opp_record = opponent.get("leagueRecord", {})
            main_record = home.get("leagueRecord", {}) if home_team["id"] == team_id else away.get("leagueRecord", {})
            return (
                desc,
                opp_team.get("fileCode", abbr_map.get(opp_team["id"], "").lower()),
                opp_team["id"],
                opp_team.get("name"),
                (main_record.get("wins"), main_record.get("losses")),
                (opp_record.get("wins"), opp_record.get("losses")),
                start_str,
            )
    except RequestException as e:
        print("Failed to fetch next game info:", e)
    return None, None, None, None, (None, None), (None, None), None

def get_previous_game_score(team_id, abbr_map):
    """Return the last game's score and series result if available."""
    try:
        now_utc = datetime.now(timezone.utc)
        start_date = (now_utc - timedelta(days=7)).date()
        end_date = now_utc.date()
        url = (
            f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&teamId={team_id}"
            f"&startDate={start_date}&endDate={end_date}"
        )
        response = requests.get(url, timeout=10)
        data = response.json()

        last_game = None
        last_game_utc = None

        for date_entry in data.get("dates", []):
            for game in date_entry.get("games", []):
                game_utc = datetime.fromisoformat(game["gameDate"].replace("Z", "+00:00"))
                if game_utc >= now_utc:
                    continue
                if last_game_utc is None or game_utc > last_game_utc:
                    last_game = game
                    last_game_utc = game_utc

        if last_game:
            home = last_game["teams"]["home"]
            away = last_game["teams"]["away"]
            home_abbr = abbr_map.get(home["team"]["id"], "???")
            away_abbr = abbr_map.get(away["team"]["id"], "???")
            home_score = home.get("score", 0)
            away_score = away.get("score", 0)
            result = f"Prev: {away_abbr} {away_score} - {home_abbr} {home_score}"
            series_result = get_series_result(team_id, last_game, abbr_map)
            if series_result:
                result += f" • {series_result}"
            return result
    except RequestException as e:
        print("Failed to fetch previous game:", e)
    return None

def get_series_result(team_id, game, abbr_map):
    try:
        series_game_num = int(game.get("seriesGameNumber", 0))
        games_in_series = int(game.get("gamesInSeries", 0))
        if series_game_num == 0 or games_in_series == 0:
            return None

        home = game["teams"]["home"]
        away = game["teams"]["away"]
        opponent = away if home["team"]["id"] == team_id else home
        opp_id = opponent["team"]["id"]
        opp_abbr = abbr_map.get(opp_id, "???")

        game_date = datetime.fromisoformat(game["gameDate"].replace("Z", "+00:00"))
        start_date = (game_date - timedelta(days=series_game_num - 1)).date()
        end_date = game_date.date()

        url = (
            f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&teamId={team_id}"
            f"&startDate={start_date}&endDate={end_date}"
        )
        response = requests.get(url, timeout=10)
        data = response.json()

        wins = 0
        losses = 0
        for date_entry in data.get("dates", []):
            for g in date_entry.get("games", []):
                h = g["teams"]["home"]
                a = g["teams"]["away"]
                if opp_id not in (h["team"]["id"], a["team"]["id"]):
                    continue
                if h["team"]["id"] == team_id:
                    if h.get("isWinner"):
                        wins += 1
                    elif a.get("isWinner"):
                        losses += 1
                elif a["team"]["id"] == team_id:
                    if a.get("isWinner"):
                        wins += 1
                    elif h.get("isWinner"):
                        losses += 1
        if wins == 0 and losses == 0:
            return None

        concluded = (
            series_game_num == games_in_series
            and game["status"].get("detailedState") in ("Final", "Game Over")
        )

        if wins > losses:
            verb = "wins" if concluded else "leads"
            return f"{abbr_map.get(team_id, '???')} {verb} series {wins}-{losses}"
        elif losses > wins:
            verb = "wins" if concluded else "leads"
            return f"{opp_abbr} {verb} series {losses}-{wins}"
        else:
            return f"Series tied {wins}-{losses}"
    except RequestException as e:
        print("Failed to fetch series result:", e)
    except Exception as e:
        print("Error getting series result:", e)
    return None

def get_team_record_from_api(team_id):
    try:
        season = datetime.now(timezone.utc).year
        url = (
            "https://statsapi.mlb.com/api/v1/standings?"
            f"teamId={team_id}&season={season}&standingsTypes=regularSeason"
        )
        response = requests.get(url, timeout=10)
        data = response.json()
        for record in data.get("records", []):
            for team in record.get("teamRecords", []):
                if team.get("team", {}).get("id") == team_id:
                    return team.get("wins"), team.get("losses")
    except RequestException as e:
        print("Failed to fetch team record:", e)
    return None, None


def get_team_record(team_id, game=None):
    """Return (wins, losses) using game data if available, else the API."""
    if game:
        try:
            for side in ("home", "away"):
                team = game["teams"][side]
                if team["team"]["id"] == team_id:
                    rec = team.get("leagueRecord", {})
                    wins = rec.get("wins")
                    losses = rec.get("losses")
                    if wins is not None and losses is not None:
                        return wins, losses
        except KeyError:
            pass
    return get_team_record_from_api(team_id)

def get_pitcher(game, team_id):
    """Return the current pitcher's full name if available."""
    try:
        pitcher_id = game.get("linescore", {}).get("defense", {}).get("pitcher", {}).get("id")
        if not pitcher_id:
            return None
        for side in ["home", "away"]:
            for pdata in game["boxscore"]["teams"][side]["players"].values():
                if pdata.get("person", {}).get("id") == pitcher_id:
                    return pdata.get("person", {}).get("fullName")
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

    main_w, main_l = get_team_record(main["team"]["id"], game)
    opp_w, opp_l = get_team_record(opponent["team"]["id"], game)
    main_record = f"{main_w}-{main_l}" if None not in (main_w, main_l) else "N/A"
    opp_record = f"{opp_w}-{opp_l}" if None not in (opp_w, opp_l) else "N/A"

    opponent_logo_url = LOGO_TEMPLATE.format(opponent["team"].get("fileCode", opp_abbr.lower()))
    team_logo_url = LOGO_TEMPLATE.format(team_info["code"])

    outs = linescore.get("outs", "?")
    offense = linescore.get("offense", {})
    base_status = "".join([
        icons["filled"] if offense.get("first") else icons["empty"],
        icons["filled"] if offense.get("second") else icons["empty"],
        icons["filled"] if offense.get("third") else icons["empty"]
    ])

    inning = linescore.get("currentInning", "?")
    inning_state = linescore.get("inningState", "")
    inning_str = f"{inning_state} {ordinal(inning)}" if inning != "?" else "Inning ?"

    pitcher = get_pitcher(game, team_info["id"])
    batter = get_batter(game)

    if game["status"]["abstractGameState"] == "Live":
        state_str = f"{inning_str} | Bases {base_status} | {outs} Out{'s' if outs > 1 else ''}"
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
        start_time = format_start_time(game, local_tz)
        state_str = status
        if start_time:
            state_str += f" • {start_time}"

    details = f"{main_abbr} {main_score} vs {opp_abbr} {opp_score}"
    if status in ["Final", "Game Over"]:
        series_result = get_series_result(team_info["id"], game, abbr_map)
        if series_result:
            details += f" • {series_result}"

    return {
        "details": details,
        "state": state_str,
        "large_image": team_logo_url,
        "large_text": f"{team_info['name']} • {main_record} | {'Home' if is_home else 'Away'}",
        "small_image": opponent_logo_url,
        "small_text": f"{opponent['team']['name']} • {opp_record} | {'Home' if not is_home else 'Away'}"
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
                            desc, opp_code, opp_id, opp_name, main_rec, opp_rec, start_str = get_next_game_info(team_info["id"], local_tz, abbr_map)
                            if desc:
                                prev = get_previous_game_score(team_info["id"], abbr_map)
                                logo = LOGO_TEMPLATE.format(team_info["code"])
                                opp_logo = LOGO_TEMPLATE.format(opp_code) if opp_code else None
                                mw, ml = main_rec
                                main_record = f"{mw}-{ml}" if None not in (mw, ml) else "N/A"
                                ow, ol = opp_rec
                                opp_record = f"{ow}-{ol}" if None not in (ow, ol) else "N/A"
                                start_time = start_str or format_start_time(game, local_tz)
                                state_field = prev or "No recent game"
                                if start_time:
                                    state_field = f"{state_field} • {start_time}"
                                update_data = {
                                    "details": desc,
                                    "state": state_field,
                                    "large_image": logo,
                                    "large_text": f"{team_info['name']} • {main_record}"
                                }
                                if opp_logo:
                                    update_data["small_image"] = opp_logo
                                if opp_name:
                                    update_data["small_text"] = f"{opp_name} • {opp_record}"
                                rpc.update(**update_data)
                                time.sleep(idle_interval)
                                continue
                        raise
                    rpc.update(**activity)
                    time.sleep(live_interval if abstract_state == "Live" else idle_interval)
                else:
                    if live_only:
                        rpc.clear()
                    else:
                        desc, opp_code, opp_id, opp_name, main_rec, opp_rec, start_str = get_next_game_info(team_info["id"], local_tz, abbr_map)
                        prev = get_previous_game_score(team_info["id"], abbr_map)
                        logo = LOGO_TEMPLATE.format(team_info['code'])
                        opp_logo = LOGO_TEMPLATE.format(opp_code) if opp_code else None
                        mw, ml = main_rec
                        main_record = f"{mw}-{ml}" if None not in (mw, ml) else "N/A"
                        ow, ol = opp_rec
                        opp_record = f"{ow}-{ol}" if None not in (ow, ol) else "N/A"
                        state_field = prev or "No recent game"
                        if start_str:
                            state_field = f"{state_field} • {start_str}"
                        update_data = {
                            "details": desc or "No upcoming game",
                            "state": state_field,
                            "large_image": logo,
                            "large_text": f"{team_info['name']} • {main_record}"
                        }
                        if opp_logo:
                            update_data["small_image"] = opp_logo
                        if opp_name:
                            update_data["small_text"] = f"{opp_name} • {opp_record}"
                        rpc.update(**update_data)
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
