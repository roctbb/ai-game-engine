def decode(runes):
    mapping = {"ᚠ": "forward", "ᚱ": "turn_right", "ᛚ": "turn_left", "ᚲ": "collect", "ᚨ": "attack", "᛫": "wait"}
    result = []
    for rune in runes:
        result.append(mapping[rune])
    return result
