import ge_sdk as sdk
import random
import time

def getCards(deck, amount):
    hand = []
    for i in range(amount):
        hand.append(deck[0])
        deck.pop(0)
    return hand, deck

def cardCost(card):
    num = int(card.split("-")[0])
    if num == 14:
        return 11
    elif num > 10:
        return 10
    else:
        return num

def cardNum(card):
    return int(card.split("-")[0])

def cardSuit(card):
    return int(card.split("-")[1])

def isPair(cards):
    nums = [cardNum(card) for card in cards]
    for num in set(nums):
        if nums.count(num) == 2:
            return [card for card in cards if cardNum(card) == num]
    return []

def isTwoPair(cards):
    nums = [cardNum(card) for card in cards]
    pairs = []
    for num in set(nums):
        if nums.count(num) == 2:
            pairs.append(num)
    if len(pairs) >= 2:
        return [card for card in cards if cardNum(card) in pairs]
    return []

def isThreeOfAKind(cards):
    nums = [cardNum(card) for card in cards]
    for num in set(nums):
        if nums.count(num) == 3:
            return [card for card in cards if cardNum(card) == num]
    return []

def isStraight(cards):
    nums = sorted([cardNum(card) for card in cards])
    if len(cards) >= 5:
        if all(nums[i] + 1 == nums[i+1] for i in range(len(nums)-1)):
            return cards
    return []

def isFlush(cards):
    suits = [cardSuit(card) for card in cards]
    if len(cards) >= 5:
        if all(s == suits[0] for s in suits):
            return cards
    return []

def isFullHouse(cards):
    nums = [cardNum(card) for card in cards]
    three = None
    two = None
    for num in set(nums):
        if nums.count(num) == 3:
            three = num
        elif nums.count(num) == 2:
            two = num
    if three and two:
        return [card for card in cards if cardNum(card) == three or cardNum(card) == two]
    return []

def isFourOfAKind(cards):
    nums = [cardNum(card) for card in cards]
    for num in set(nums):
        if nums.count(num) == 4:
            return [card for card in cards if cardNum(card) == num]
    return []

def isStraightFlush(cards):
    if len(cards) >= 5:
        if isStraight(cards) and isFlush(cards):
            return cards
    return []

def isRoyalFlush(cards):
    nums = sorted([cardNum(card) for card in cards])
    if nums == [10, 11, 12, 13, 14] and isFlush(cards):
        return cards
    return []

def summCards(crds):
    summ = 0
    for i in crds:
        summ += cardCost(i)
    return summ

def countScore(crds):
    if isRoyalFlush(crds):
        print(1)
        return (100 + summCards(isRoyalFlush(crds))) * 8
    elif isStraightFlush(crds):
        print(isStraightFlush(crds))
        return (100 + summCards(isStraightFlush(crds))) * 8
    elif isFourOfAKind(crds):
        print(3)
        return (60 + summCards(isFourOfAKind(crds))) * 7
    elif isFullHouse(crds):
        print(4)
        return (40 + summCards(isFullHouse(crds))) * 4
    elif isFlush(crds):
        print(5)
        return (35 + summCards(isFlush(crds))) * 4
    elif isStraight(crds):
        print(6)
        return (30 + summCards(isStraight(crds))) * 4
    elif isThreeOfAKind(crds):
        print(7)
        return (30 + summCards(isThreeOfAKind(crds))) * 3
    elif isTwoPair(crds):
        print(8)
        return (20 + summCards(isTwoPair(crds))) * 2
    elif isPair(crds):
        print(9)
        return (10 + summCards(isPair(crds))) * 2
    else:
        highest_card = max(crds, key=lambda card: cardCost(card))
        # print(cardCost(highest_card) + 5)
        return cardCost(highest_card) + 5

def dataReset(data):
    cards = [f"{_+2}-{suit+1}" for _ in range(13) for suit in range(4)]
    random.shuffle(cards)
    for key in list(data.keys()):
        data[key]["points"] = 0
        data[key]["hands"] = 4
        data[key]["discards"] = 3
        data[key]["deck"] = cards.copy()
        data[key]["handCards"] = []
    return data
        

def game():
    engine = sdk.GameEngineClient()
    stats = sdk.GameEngineStats(engine.teams, ["Рук сыграно", "Рук скинуто", "Карт сыграно", "Самая дорогая рука"])

    
    engine.start()

    
    
    # engine.teams - команды

    # team = engine.teams[0]
    # team.id - id команды 0
    # team.name - имя команды 0
    # team.players - игроки команды 0

    # player = team.players[0]
    # player.id - id игрока
    # player.name - имя игрока
    # player.script - скрипт игрока

    # Запуск скрипта игрока и получение значения:
    # result = sdk.timeout_run(0.4, player.script, "function_name", (arg1, arg2, arg3...))
    # 0.4 - таймаут выполнения, при превышении вернет None
    # "function_name" - имя функции из скрипта игрока, которую хотите запустить
    # (arg1, arg2, arg3...) - список аргументов, которые нужно передать в функцию игрока

    baseHandSize = 8
    baseCards = [f"{_+2}-{suit+1}" for _ in range(13) for suit in range(4)]
    rplayed = 0

    data = {
        "top": {
            "points": 0,
            "wins": 0, 
            "hands": 4,
            "discards": 3, 
            "deck": baseCards, 
            "handCards": [], 
            "handsPlayed": 0, 
            "handsDiscarded": 0, 
            "cardsPlayed": 0,
            "richiestHand": 0
        }, 
        "bottom": {
            "points": 0,
            "wins": 0, 
            "hands": 4,
            "discards": 3, 
            "deck": baseCards, 
            "handCards": [], 
            "handsPlayed": 0, 
            "handsDiscarded": 0, 
            "cardsPlayed": 0,
            "richiestHand": 0
        }
    }

    data = dataReset(data)
    while True:
        players = [engine.teams[0].players[0], engine.teams[1].players[0]]

        hc, data["top"]["deck"] = getCards(data["top"]["deck"], baseHandSize - len(data["top"]["handCards"]))
        data["top"]["handCards"] += hc
        hc, data["bottom"]["deck"] = getCards(data["bottom"]["deck"], baseHandSize - len(data["bottom"]["handCards"]))
        data["bottom"]["handCards"] += hc


        moves = []
        if data["top"]["hands"]>0:
            moves.append("play")
            if data["top"]["discards"]>0:
                moves.append("discard")
        
        if moves:
            topAnswer = sdk.timeout_run(4, players[0].script, "make_choice", (data["top"]["handCards"], data["top"]["deck"], data["top"]["discards"], data["top"]["hands"], moves), bypass_errors=False)
        else:
            topAnswer = {"action": "wait", "cards": []}
        if topAnswer["action"] == "play":
            data["top"]["hands"] -= 1
            data["top"]["handsPlayed"] += 1
            sc = countScore(topAnswer["cards"])
            if sc > data["top"]["richiestHand"]:
                data["top"]["richiestHand"] = sc
            data["top"]["points"] += sc
        elif topAnswer["action"] == "discard":
            data["top"]["handsDiscarded"] += 1
            data["top"]["discards"] -= 1
        data["top"]["cardsPlayed"] += len(topAnswer["cards"])
            

        moves = []
        if data["bottom"]["hands"]>0:
            moves.append("play")
            if data["bottom"]["discards"]>0:
                moves.append("discard")
        
        if moves:
            bottomAnswer = sdk.timeout_run(4, players[0].script, "make_choice", (data["bottom"]["handCards"], data["bottom"]["deck"], data["bottom"]["discards"], data["bottom"]["hands"], moves), bypass_errors=False)
        else:
            bottomAnswer = {"action": "wait", "cards": []}

        if bottomAnswer["action"] == "play":
            data["bottom"]["hands"] -= 1
            data["bottom"]["handsPlayed"] += 1
            sc = countScore(bottomAnswer["cards"])
            if sc > data["bottom"]["richiestHand"]:
                data["bottom"]["richiestHand"] = sc
            data["bottom"]["points"] += sc
        elif bottomAnswer["action"] == "discard":
            data["bottom"]["handsDiscarded"] += 1
            data["bottom"]["discards"] -= 1
        data["bottom"]["cardsPlayed"] += len(bottomAnswer["cards"])

        data["top"]["handCards"] = sorted(data["top"]["handCards"], key=lambda card: (cardNum(card), cardSuit(card)))
        data["bottom"]["handCards"] = sorted(data["bottom"]["handCards"], key=lambda card: (cardNum(card), cardSuit(card)))

        frame = {
            "players": {
                "top": players[0].name,
                "bottom": players[1].name
            },
            "wins": {
                "top": data["top"]["wins"],
                "bottom": data["bottom"]["wins"],
            },
            "cardsLeft": {
                "top": len(data["top"]["deck"]), 
                "bottom": len(data["bottom"]["deck"])
            }, 
            "points": {
                "top": data["top"]["points"], 
                "bottom": data["bottom"]["points"]
            }, 
            "cardsInHand": {
                "top": data["top"]["handCards"], 
                "bottom": data["bottom"]["handCards"]
            }, 
            "cardsChosen": {
                "top": topAnswer["cards"],
                "bottom": bottomAnswer["cards"]
            },
            "cardsScores": {
                "top": [cardCost(_) for _ in data["top"]["handCards"]],
                "bottom": [cardCost(_) for _ in data["bottom"]["handCards"]]
            }, 
            "handsLeft": {
                "top": data["top"]["hands"],
                "bottom": data["bottom"]["hands"]
            }, 
            "discardsLeft": {
                "top": data["top"]["discards"],
                "bottom": data["bottom"]["discards"]
            }, 
            "action":{ # discard/play/wait
                "top": topAnswer["action"],
                "bottom": bottomAnswer["action"]
            },
            "round": rplayed
        }



        newHand = []
        for i in data["top"]["handCards"]:
            if not (i in topAnswer["cards"]):
                newHand.append(i)
        data["top"]["handCards"] = newHand

        newHand = []
        for i in data["bottom"]["handCards"]:
            if not (i in bottomAnswer["cards"]):
                newHand.append(i)
        data["bottom"]["handCards"] = newHand
        
        if data["top"]["hands"] == 0 and data["bottom"]["hands"] == 0:
            if data["top"]["points"]>data["bottom"]["points"]:
                data["top"]["wins"] += 1
            else:
                data["bottom"]["wins"] += 1
            data = dataReset(data)
            rplayed += 1
            

        if (data["top"]["wins"] >= 5):
            engine.set_winner(engine.teams[0])
            frame["winner"] = "top"
        if (data["bottom"]["wins"] >= 5):
            engine.set_winner(engine.teams[1])
            frame["winner"] = "bottom"

        engine.send_frame(frame)
        time.sleep(2)
        if frame.get("winner"):
            stats.add_value(players[1], "Рук сыграно", data["bottom"]["handsPlayed"])
            stats.add_value(players[1], "Рук скинуто", data["bottom"]["handsDiscarded"])
            stats.add_value(players[1], "Карт сыграно", data["bottom"]["cardsPlayed"])
            stats.add_value(players[1], "Самая дорогая рука", data["bottom"]["richiestHand"])
            stats.add_value(players[0], "Рук сыграно", data["top"]["handsPlayed"])
            stats.add_value(players[0], "Рук скинуто", data["top"]["handsDiscarded"])
            stats.add_value(players[0], "Карт сыграно", data["top"]["cardsPlayed"])
            stats.add_value(players[0], "Самая дорогая рука", data["top"]["richiestHand"])
            engine.send_stats(stats)
            break
    # TODO: указать, какая команда победила
    # engine.set_winner(engine.teams[0])

    engine.end()


if __name__ == "__main__":
    game()
