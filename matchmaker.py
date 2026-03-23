'''matchmaking algorithm for fighthub

produces a single compatabillity score between two fighters by combiing
six weighted factors.

ELO system to compliment traditional  W/L system

all fighters start from 0
ratings are freshly computed from each fighteesr full record and fight history
on every call. '''

from __future__ import annotations

# elo configurations

elo_start = 0
elo_k = 32

method_multiplier ={
    "ko": 1.5,
    "tko": 1.5,
    "submission": 1.3,
    "decision": 1.0,
    "disqualification": 0.5
}

def _method_multiplier(method: str) -> float:
    return method_multiplier.get(method.lower().strip(), 1.0)


#factor weights. must sum to 1.0

weight_W = 0.20
elo_w = 0.20
record_w = 0.15
method_W = 0.10
opp_quality_w = 0.10
experience_w = 0.15
recent_form_w = 0.05
age_w = 0.05

_weight_sum = weight_W + elo_w + record_w + method_W + opp_quality_w + \
    experience_w + recent_form_w + age_w
assert abs(_weight_sum - 1.0) < 1e-9, \
    f"factor weights must sum to 1.0, got {_weight_sum}"

# ELO engine creation

def _expected(rating_a: float, rating_b: float) -> float:
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))

def compute_elo(history: list[dict], all_elos:dict[str, float]| None = None) -> float:
                
    '''computes a fighters elo by replaying their full fight history 
    in chonrological order
                
    as fighters names are stored not ID a shared name keyed ELO table is used so
    two fighters with the same name will have their ELO ratings updated together'''


    if all_elos is None:
        all_elos = {}
                
    rating = float(elo_start)
    result_score = {"W": 1.0, "D": 0.5, "L": 0.0}

    for fight in sorted(history, key = lambda h:h["date"]):
        opp_name = fight["opponent"]
        opp_rating = all_elos.get(opp_name, float (elo_start))
        actual = result_score.get(fight["result"].upper(), 0.5)
        expected = _expected(rating, opp_rating)
        multiplier = _method_multiplier(fight["method"]) if actual == 1.0 else 1.0

        change = elo_k *multiplier * (actual - expected)
        rating += change

        all_elos[opp_name] = opp_rating - change

    return round(rating, 2)



def compute_elo_for_pool(
    fighters: list[dict],
    histories:dict[int,list[dict]]
    ) -> dict[int,float]:

    ''' computes elo for every fighter in a pool simultaneously so that shared 
    fight results influence both fighters ratings'''

    name_to_id = {f["name"]: f["id"] for f in fighters}

    # collects all fights

    all_fights =[]
    for f in fighters:
        for fight in histories.get(f["id"], []):
            all_fights.append({**fight, "_ifghter_id": f["id"], "_fighter_name": f["name"]})
            # sorts all fights globally by date 
        all_fights.sort(key=lambda h:h ["date"])

        ratings : dict[int, float] = {f["id"]: float(elo_start) for f in fighters}
        result_score = {"W": 1.0, "D": 0.5, "L": 0.0}

        for fight in all_fights:
            fid = fight["_fighter_id"]
            opp_name = fight["opponent"]
            opp_id = name_to_id(opp_name)  # none if opponent not in pool
            r_fighter = ratings[fid]
            r_opp = ratings[opp_id] if opp_id else float(elo_start)

            actual = result_score.get(fight["result"].upper(), 0.5)
            expected = _expected (r_fighter, r_opp)
            multiplier = _method_multiplier(fight["method"] if actual == 1.0 else 1.0)

            change = elo_k * multiplier * (actual - expected)
            ratings[fid] += change
            if opp_id:
                ratings[opp_id] -= change  # mirros change to the opponent 
            return {fid: round (r,2) for fid, r in ratings.items()}
        
# victory profle method


method_prestige = {
    "ko": 1.5,
    "tko": 0.9,
    "submission": 0.85,
    "decision": 0.5,
    "disqualification": 0.3
}

def _method_prestige(method:str)-> float:
    return method_prestige.get(method.lower().strip(), 0.5)

# fighter profle usings scoring functions for stats

def _profile (fighter:dict, history:list[dict], elo:float) -> dict:

    '''computes all delvierable statistics for a fighter'''

    wins = fighter["wins"]
    losses = fighter["losses"]
    draws = fighter["draws"]
    total = wins +losses + draws or 1

    win_fights = [h for h in history if h ["result"] == "w"]
    finish_score = sum(_method_prestige(h["method"]) for h in win_fights)/len (win_fights) if win_fights else 0.5
    
    if win_fights:
        finishes = sum(
            1 for h in win_fights if h ["method"].lower() not in ("decision", "disqualification")
        )
        opp_quality_Score = finishes / len(win_fights)
    else:
        opp_quality_Score = 0.0

    # recent for wieghted over last 5 fights
    
    recent = sorted (history, key=lambda h:h ["date"], reverse = True) [:5]
    if recent: 
        result_value = {"w": 1.0, "d": 0.5, "l": 0.0}
        weights = [5,4,3,2,1] [:len(recent)]
        weighted_sum = sum(result_value[h["result"]] * w for h, w in zip (recent,weights))
        recent_form = weighted_sum / sum(weights)
    else:
        recent_form = 0.5

    return {
        "total": total,
        "win_rate": wins/total,
        "elo": elo,
        "finish_score": finish_score,
        "opp_quality_score": opp_quality_Score,
        "recent_form": recent_form,
        "age": fighter["age"],
        "weight_kg": fighter["weight_kg"]
    }


#individual factor scores


def _score_weight(a:dict, b:dict) -> float:
    '''full score at 0kg difference, 0 at 10kg difference'''
    return max (0.0,1.0 - abs(a["weight_kg"] - b ["weight_kg"]) / 10.0)

def _score_elo(a:dict, b:dict) -> float:
    ''' elo proximity score. uses a 400 point window so the factore feels natural. 
    same system uses by elo expected score formula'''

    diff = abs(a["elo"] - b["elo"])
    return max(0.0, 1.0 - diff / 400.0)

def _score_record (a:dict, b:dict) ->float:
    '''win/loss recorded similarly based on raw win rate.
    compliemtns ELO ensures that opponents are matched appropriately'''

    return 1.0 - abs(a["win_rate"] - b["win_rate"])

def _score_method (a:dict, b:dict) ->float:
    ''' beating a similarly scored profile scores higher'''
    return 1.0 - abs(a["finish_score"] - b["finish_score"])

def _score_opp_quality (a:dict, b:dict) ->float:
    '''penalises large gaps in quality to protect fighter scores'''
    return 1.0 - abs(a["opp_quality_score"] - b["opp_quality_score"])

def _score_experience (a:dict, b:dict) ->float:
    '''full score at 0 fight gap, zero at 10+ fights'''
    return max(0.0,1.0 - abs(a["total"] - b ["total"])/10.0)

def _score_recent_form (a:dict, b: dict) ->float:
    """penalises mismatched momentum"""
    return 1.0 - abs(a["recent_form"] - b["recent_form"])


def _score_age (a:dict, b:dict) ->float:
    '''full score at 0 year difference, zero at 10+ years'''
    return max(0.0,1.0 - abs(a["age"] - b["age"])/10.0)


#public API integration 