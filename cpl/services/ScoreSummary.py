import re


def overs_to_float(overs_str: str) -> float:
    """
    Convert cricket overs notation (e.g. '19.5') into decimal overs.
    '19.5' means 19 overs and 5 balls = 19 + 5/6 = 19.8333
    """
    if "." in overs_str:
        parts = overs_str.split(".")
        overs = int(parts[0])
        balls = int(parts[1])
        return overs + balls / 6.0
    else:
        return float(overs_str)


def parse_score_summary(summary: str):
    # Example: "150/7 (19.5 ov) vs 152/5 (20 ov)"
    try:
        parts = summary.split("vs")
        team_a = parts[0].strip()
        team_b = parts[1].strip()

        # Extract runs, wickets, overs
        def extract(s):
            match = re.match(r"(\d+)/(\d+)\s*\(([\d\.]+)\s*ov\)", s)
            if match:
                runs = int(match.group(1))
                wickets = int(match.group(2))
                overs = overs_to_float(match.group(3))
                return runs, wickets, overs
            return None

        runs_a, wkts_a, overs_a = extract(team_a)
        runs_b, wkts_b, overs_b = extract(team_b)

        return runs_a, overs_a, runs_b, overs_b
    except Exception as e:
        print("Error parsing score summary:", e)
        return None
