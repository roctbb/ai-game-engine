import random

def make_choice(handCards, cardsLeft, discards, hands, moves=["play", "discard"]):
    answer = {
        "action": "play", 
        "cards": [random.choice(handCards)]
    }
    return answer