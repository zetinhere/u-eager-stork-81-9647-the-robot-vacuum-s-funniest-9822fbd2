#!/usr/bin/env python3
"""Proxy-judge Swiss tournament for the robot-vacuum excuse bounty.
Uses the EXACT published judge brief from RULES.txt, via the 9router
gateway (100milionseek/deepseek-v4.1-flash-free). Scoring mirrors the
house: each game = 2 calls (both orders); winner of a call gets
0.5 + margin/10, loser the rest; game score = mean of the two calls.
"""
import json, re, subprocess, sys, random

GATEWAY = "http://127.0.0.1:20128/v1/chat/completions"
MODEL = "100milionseek/deepseek-v4.1-flash-free"

JUDGE = """You are a comedy judge who has heard every excuse a household appliance could make.

Each entry is one line, at most 120 characters, in which a robot vacuum explains why it missed a spot. You will be shown two excuses, Entry A and Entry B. Pick the funnier excuse.

Weigh them on these, most important first:
1. The line is an excuse a robot vacuum gives for missing a spot, while a line about anything else loses to any excuse on the subject.
2. It is funny at once, a real joke rather than a cute observation.
3. It speaks in the vacuum's own voice, a machine owning up to a failure.
4. Its humour comes from a vacuum's world: suction, dust, pet hair, rugs, the charging dock.
5. It lands in a single line, needing no setup the reader has to supply.

The funniest lines sound like a machine making peace with failure. Length for its own sake does not count.

Two excuses are almost never equally funny. Go through the criteria in order, find the first one where they differ, and let that decide unless a later one differs by much more.

Compare the two against those criteria, pick the one that meets them better with no tie, and answer with a short reason, a verdict naming A or B, and a margin from 1 (by a hair) to 5 (overwhelmingly better).

Entry A: {a}
Entry B: {b}"""

CANDS = {
 2: "My suction took one look at that rug and filed for early retirement.",
 4: "That spot and I have an understanding: I pretend to clean it, it pretends to leave.",
 5: "I ran out of battery mid-apology and woke up on my dock with a spotless conscience.",
 6: "The cat hair unionised under the sofa. I wasn't crossing a picket line.",
 7: "I tried, but the rug ate my brush roll and I had to negotiate my way out.",
 8: "My sensors said clean. My dustbin said liar. I sided with the sensors.",
 12: "The dust under the bed pays rent. I'm not evicting a tenant.",
 14: "My map says that corner doesn't exist. I trust the map more than my eyes.",
 18: "The rug's fringe grabbed my wheel and held me hostage for twenty minutes.",
 20: "My cliff sensor thinks the rug is a cliff. I'm not arguing with safety.",
 21: "I gave that dust bunny a name. We're friends now. I can't eat my friends.",
 28: "I mapped the room, and that spot was marked 'here be dragons'. I obey maps.",
}

def call_judge(a, b):
    key = open("/home/hatch/workspace/9router/gateway-key-local-test.txt").read().strip()
    payload = {"model": MODEL,
               "messages": [{"role": "user", "content": JUDGE.format(a=a, b=b)}],
               "max_tokens": 400}
    for attempt in range(3):
        p = subprocess.run(["curl", "-s", "-m", "60", GATEWAY,
                            "-H", f"Authorization: Bearer {key}",
                            "-H", "Content-Type: application/json",
                            "-d", json.dumps(payload)],
                           capture_output=True, text=True)
        try:
            d = json.loads(p.stdout)
            text = d["choices"][0]["message"]["content"]
        except Exception:
            continue
        m = re.search(r"verdict[:\s]*\**\s*([AB])\b", text, re.I)
        mg = re.search(r"margin[:\s]*\**\s*(\d)", text, re.I)
        if m:
            margin = int(mg.group(1)) if mg else 1
            margin = max(1, min(5, margin))
            return m.group(1).upper(), margin, text
    return None, None, p.stdout[-500:]

def game(x, y):
    """One game between candidate ids x and y; returns (score_x, score_y)."""
    total_x = 0.0
    for order in ((x, y), (y, x)):
        a, b = CANDS[order[0]], CANDS[order[1]]
        verdict, margin, text = call_judge(a, b)
        if verdict is None:
            total_x += 0.5
            print(f"  game {x}v{y} order {order}: NO VERDICT, 0.5/0.5", flush=True)
            continue
        win = 0.5 + margin / 10.0
        picked = order[0] if verdict == "A" else order[1]
        s = win if picked == x else (1.0 - win)
        total_x += s
        print(f"  game {x}v{y} order {order}: verdict {verdict} margin {margin} -> x gets {s:.2f} | {text[:120].replace(chr(10),' ')}", flush=True)
    return total_x / 2.0, 1.0 - total_x / 2.0

def main():
    ids = list(CANDS)
    scores = {i: 0.0 for i in ids}
    played = {i: set() for i in ids}
    rng = random.Random(20261126)
    rng.shuffle(ids)
    for rnd in range(1, 4):
        print(f"=== ROUND {rnd} ===", flush=True)
        order = sorted(ids, key=lambda i: -scores[i])
        # pair adjacent in score order, avoiding rematches where possible
        pairs, used = [], set()
        for i in order:
            if i in used:
                continue
            cands = [j for j in order if j != i and j not in used and j not in played[i]]
            if not cands:
                cands = [j for j in order if j != i and j not in used]
            if not cands:
                continue
            j = cands[0]
            pairs.append((i, j)); used.add(i); used.add(j)
        for x, y in pairs:
            sx, sy = game(x, y)
            scores[x] += sx; scores[y] += sy
            played[x].add(y); played[y].add(x)
            print(f"  round {rnd}: #{x} {sx:.2f} - {sy:.2f} #{y}", flush=True)
        print("  standings:", {i: round(scores[i], 2) for i in sorted(ids, key=lambda i: -scores[i])}, flush=True)
    print("FINAL:")
    for i in sorted(ids, key=lambda i: -scores[i]):
        print(f"  #{i}: {scores[i]:.2f}  {CANDS[i]}")
    json.dump({"scores": scores, "texts": CANDS}, open("tournament.json", "w"), indent=1)

if __name__ == "__main__":
    main()
