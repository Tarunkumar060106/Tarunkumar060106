"""Builds dark_mode.svg and light_mode.svg: a neofetch-style profile card.

Run locally (uses `gh auth token`) or in GitHub Actions (uses ACCESS_TOKEN / GITHUB_TOKEN).
Edit PROFILE below to change what the card says.
"""
import datetime as dt
import json
import os
import subprocess
import urllib.request
from xml.sax.saxutils import escape

from PIL import Image

LOGIN = "Tarunkumar060106"
HANDLE = "tarun@github"

PROFILE = [
    ("OS", "Windows 11, Android"),
    ("Uptime", "{uptime}"),
    ("Host", "Chennai, India"),
    ("Kernel", "Full-Stack Developer"),
    ("IDE", "VS Code, Claude Code"),
    None,
    ("Languages.Programming", "TypeScript, Python, JavaScript"),
    ("Languages.Web", "Next.js, React, Convex, Clerk"),
    ("Languages.Systems", "Kotlin, C++, Java, Go"),
    None,
    ("Hobbies.Hardware", "Robotics, Embedded, Sensors"),
    ("Hobbies.Building", "Hackathons, Event Platforms"),
    ("Now.Building", "hpc-ds1, Taskline, MailMind"),
    "Contact",
    ("Website", "tarun.radiantsofficial.com"),
    ("GitHub", LOGIN),
    "GitHub Stats",
    "{stats}",
]

WIDTH = 58          # characters in the info column
ASCII_COLS = 44
ASCII_ROWS = 25
RAMP = " .:-=+*#%@"   # light -> dark

THEMES = {
    "dark": {"bg": "#161b22", "text": "#c9d1d9", "key": "#ffa657",
             "value": "#a5d6ff", "dots": "#616e7f", "accent": "#2dd4bf", "art": "#c9d1d9"},
    "light": {"bg": "#f6f8fa", "text": "#24292f", "key": "#953800",
              "value": "#0a3069", "dots": "#c2cfde", "accent": "#0f766e", "art": "#24292f"},
}


# ---------- ASCII portrait ----------

def ascii_art(path="avatar/avatar.png"):
    cache = "ascii.txt"
    if os.path.exists(cache):
        with open(cache, encoding="utf-8") as f:
            return f.read().split("\n")
    img = Image.open(path).convert("L")
    w, h = img.size
    img = img.crop((int(w * 0.05), 0, int(w * 0.95), h))  # trim side whitespace
    img = img.resize((ASCII_COLS, ASCII_ROWS))
    lines = []
    for y in range(ASCII_ROWS):
        row = ""
        for x in range(ASCII_COLS):
            v = img.getpixel((x, y))
            row += RAMP[min(len(RAMP) - 1, (255 - v) * len(RAMP) // 256)]
        lines.append(row.rstrip())
    with open(cache, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return lines


# ---------- GitHub data ----------

def token():
    t = os.environ.get("ACCESS_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if t:
        return t
    return subprocess.run(["gh", "auth", "token"], capture_output=True, text=True).stdout.strip()


def gql(query, variables, tok):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {tok}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        out = json.load(r)
    if "errors" in out:
        raise RuntimeError(out["errors"])
    return out["data"]


def fetch_stats():
    tok = token()
    base = gql("""query($login:String!){user(login:$login){
        createdAt followers{totalCount}
        repositoriesContributedTo(contributionTypes:[COMMIT,PULL_REQUEST,REPOSITORY]){totalCount}}}""",
               {"login": LOGIN}, tok)["user"]

    repos, stars, cursor = 0, 0, None
    while True:
        page = gql("""query($login:String!,$after:String){user(login:$login){
            repositories(first:100,after:$after,ownerAffiliations:OWNER,privacy:PUBLIC){
            totalCount nodes{stargazerCount} pageInfo{hasNextPage endCursor}}}}""",
                   {"login": LOGIN, "after": cursor}, tok)["user"]["repositories"]
        repos = page["totalCount"]
        stars += sum(n["stargazerCount"] for n in page["nodes"])
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]

    created = dt.datetime.fromisoformat(base["createdAt"].replace("Z", "+00:00"))
    now = dt.datetime.now(dt.timezone.utc)
    commits, start = 0, created
    while start < now:
        end = min(start + dt.timedelta(days=365), now)
        c = gql("""query($login:String!,$from:DateTime!,$to:DateTime!){user(login:$login){
            contributionsCollection(from:$from,to:$to){totalCommitContributions restrictedContributionsCount}}}""",
                {"login": LOGIN, "from": start.isoformat(), "to": end.isoformat()}, tok)
        cc = c["user"]["contributionsCollection"]
        commits += cc["totalCommitContributions"] + cc["restrictedContributionsCount"]
        start = end

    return {
        "created": created,
        "followers": base["followers"]["totalCount"],
        "contributed": base["repositoriesContributedTo"]["totalCount"],
        "repos": repos,
        "stars": stars,
        "commits": commits,
    }


def uptime(created):
    today = dt.date.today()
    c = created.date()
    months = (today.year - c.year) * 12 + today.month - c.month
    days = today.day - c.day
    if days < 0:
        months -= 1
        prev = today.replace(day=1) - dt.timedelta(days=1)
        days += prev.day
    years, months = divmod(months, 12)
    plural = lambda n, w: f"{n} {w}{'' if n == 1 else 's'}"
    return f"{plural(years, 'year')}, {plural(months, 'month')}, {plural(days, 'day')}"


# ---------- SVG ----------

def kv(key, value, width):
    """`key: ..... value` padded with dot leaders to `width` characters."""
    n = max(1, width - len(key) - len(value) - 3)
    return (f'<tspan class="key">{escape(key)}</tspan>:'
            f'<tspan class="dots"> {"." * n} </tspan>'
            f'<tspan class="value">{escape(value)}</tspan>')


def header(title):
    rule = "—" * (WIDTH - len(title) - 3)
    return f'- <tspan class="accent">{escape(title)}</tspan> {rule}'


def info_lines(s):
    lines = [f'<tspan class="accent">{HANDLE}</tspan> ' + "—" * (WIDTH - len(HANDLE) - 1)]
    for item in PROFILE:
        if item is None:
            lines.append("")
        elif item == "{stats}":
            half = (WIDTH - 3) // 2
            lines.append(kv("Repos", f'{s["repos"]} {{Contributed: {s["contributed"]}}}', half + 6)
                         + " | " + kv("Stars", str(s["stars"]), WIDTH - half - 9))
            lines.append(kv("Commits", f'{s["commits"]:,}', half + 6)
                         + " | " + kv("Followers", str(s["followers"]), WIDTH - half - 9))
        elif isinstance(item, str):
            lines.append("")
            lines.append(header(item))
        else:
            key, value = item
            lines.append(kv(key, value.replace("{uptime}", uptime(s["created"])), WIDTH))
    return lines


def render(theme, art, info):
    t = THEMES[theme]
    line_h, top, art_x = 20, 30, 15
    char_w = 9.6  # Consolas at 16px with the 109% size-adjust below
    info_x = round(art_x + ASCII_COLS * char_w + 25)
    width = round(info_x + (WIDTH + 2) * char_w + 15)
    rows = max(len(art), len(info) + 1)
    height = top + rows * line_h + 10
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" font-family="ConsolasFallback,Consolas,\'Courier New\',monospace" '
        f'width="{width}px" height="{height}px" font-size="16px">',
        "<style>",
        "@font-face{src:local('Consolas'),local('Consolas Bold');font-family:'ConsolasFallback';"
        "font-display:swap;-webkit-size-adjust:109%;size-adjust:109%}",
        f".key{{fill:{t['key']}}} .value{{fill:{t['value']}}} .dots{{fill:{t['dots']}}} "
        f".accent{{fill:{t['accent']};font-weight:bold}} text,tspan{{white-space:pre}}",
        "@keyframes fade{from{opacity:0}to{opacity:1}}",
        "@keyframes blink{0%,49%{opacity:1}50%,100%{opacity:0}}",
        ".ln{animation:fade .4s ease backwards}",
        f".cursor{{fill:{t['accent']};animation:blink 1s steps(1) infinite}}",
        "</style>",
        f'<rect width="{width}px" height="{height}px" fill="{t["bg"]}" rx="15"/>',
        f'<text x="{art_x}" y="{top}" fill="{t["art"]}">',
    ]
    for i, row in enumerate(art):
        out.append(f'<tspan class="ln" style="animation-delay:{i * 0.04:.2f}s" x="{art_x}" y="{top + i * line_h}">{escape(row)}</tspan>')
    out.append("</text>")
    out.append(f'<text x="{info_x}" y="{top}" fill="{t["text"]}">')
    for i, row in enumerate(info):
        out.append(f'<tspan class="ln" style="animation-delay:{0.3 + i * 0.06:.2f}s" x="{info_x}" y="{top + i * line_h}">{row}</tspan>')
    last = top + len(info) * line_h
    out.append(f'<tspan class="ln" style="animation-delay:{0.3 + len(info) * 0.06:.2f}s" x="{info_x}" y="{last}">'
               f'<tspan class="accent">{HANDLE}</tspan> $ <tspan class="cursor">█</tspan></tspan>')
    out.append("</text></svg>")
    return "\n".join(out)


def main():
    art = ascii_art()
    stats = fetch_stats()
    info = info_lines(stats)
    for theme in THEMES:
        with open(f"{theme}_mode.svg", "w", encoding="utf-8") as f:
            f.write(render(theme, art, info))
    print("stats:", {k: v for k, v in stats.items() if k != "created"})


if __name__ == "__main__":
    main()
