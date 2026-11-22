"""Setter guide: period / tradition star ratings, composers, the reason for a registration and layering notes.

A guide accompanies a setter file but lives outside the Combinations folder (GrandOrgue would read a second .yaml there as a
setter): <data root>/Guides/<set>/<setter file stem>.guide.yaml. The organ's own character (what a historic organ was built
for) is the "character" section of its organ map and uses the same ratings.

CHANGELOG
2026-11-22  New: PERIODS, TRADITIONS, blank_guide(), clean_guide(), load_guides(), save_guide(), matches() (filter), fit() (how well a setter suits the organ).
"""

import os

PERIODS = ("baroque", "classical", "romantic", "modern")
TRADITIONS = ("catholic", "early_protestant", "modern_church")


def _stars(value):
    try:
        return max(0, min(5, int(value)))
    except (TypeError, ValueError):
        return 0


def blank_guide():
    return {"period": {p: 0 for p in PERIODS}, "tradition": {t: 0 for t in TRADITIONS}, "composers": [], "reason": "", "layering": ""}


def clean_guide(data):
    """A guide with every field present and ratings as 0-5 integers (unknown keys are dropped)."""
    data = data if isinstance(data, dict) else {}
    guide = blank_guide()
    for group, keys in (("period", PERIODS), ("tradition", TRADITIONS)):
        source = data.get(group) if isinstance(data.get(group), dict) else {}
        guide[group] = {k: _stars(source.get(k)) for k in keys}
    composers = data.get("composers", [])
    if isinstance(composers, str):
        composers = [c for c in composers.replace(";", ",").split(",")]
    guide["composers"] = [str(c).strip() for c in composers if str(c).strip()]
    guide["reason"] = str(data.get("reason", "") or "")
    guide["layering"] = str(data.get("layering", "") or "")
    return guide


def guide_path(folder, filename):
    return os.path.join(folder, os.path.splitext(os.path.basename(filename))[0] + ".guide.yaml")


def load_guides(folder):
    """{setter file stem: guide} for every guide file in the folder."""
    import yaml
    found = {}
    if os.path.isdir(folder):
        for name in os.listdir(folder):
            if name.endswith(".guide.yaml"):
                try:
                    with open(os.path.join(folder, name), encoding="utf-8") as handle:
                        found[name[:-len(".guide.yaml")]] = clean_guide(yaml.safe_load(handle))
                except (OSError, yaml.YAMLError):
                    continue
    return found


def save_guide(folder, filename, guide):
    import yaml
    os.makedirs(folder, exist_ok=True)
    with open(guide_path(folder, filename), "w", encoding="utf-8", newline="\n") as handle:
        handle.write("# Setter guide: ratings 0-5 stars per period and tradition, composers, why this registration, how to layer it.\n")
        yaml.safe_dump(clean_guide(guide), handle, sort_keys=False, allow_unicode=True, default_flow_style=False)


def matches(guide, period="", tradition="", composer="", min_stars=1):
    """Filter test: rated at least min_stars for the chosen period / tradition, and the composer text found."""
    guide = clean_guide(guide)
    if period and guide["period"].get(period, 0) < min_stars:
        return False
    if tradition and guide["tradition"].get(tradition, 0) < min_stars:
        return False
    if composer and not any(composer.casefold() in c.casefold() for c in guide["composers"]):
        return False
    return True


def fit(guide, character):
    """0-5: how well a setter's period ratings suit the organ's character (what it was built for); 0 when either is unrated."""
    guide, character = clean_guide(guide), clean_guide(character)
    best = max(character["period"], key=lambda p: character["period"][p])
    if character["period"][best] == 0:
        return 0
    return min(guide["period"][best], character["period"][best])
