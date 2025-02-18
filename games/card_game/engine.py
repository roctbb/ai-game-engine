import ge_sdk as sdk
import random

def getCards(deck, amount):
    hand = []
    for i in range(amount):
        rnd = random.randint(0, len(deck)-1)
        hand.append(deck[rnd])
        deck.pop(rnd)
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

# def isPair()

def countScore(crds):
    if len(crds) == 1:
        return cardCost(crds[0]) + 5
    if len(crds) == 2:
        return max(cardCost(crds[0]), cardCost(crds[1])) + 5
    if len(crds) == 3:
        return max(cardCost(crds[0]), cardCost(crds[1]), cardCost(crds[2])) + 5
    if len(crds) == 4:
        return max(cardCost(crds[0]), cardCost(crds[1]), cardCost(crds[2]), cardCost(crds[3])) + 5
    if len(crds) == 5:
        return max(cardCost(crds[0]), cardCost(crds[1]), cardCost(crds[2]), cardCost(crds[3]), cardCost(crds[4])) + 5

def dataReset(data):
    for key in list(data.keys()):
        data[key]["points"] = 0
        data[key]["hands"] = 4
        data[key]["discards"] = 3
        data[key]["deck"] = [f"{_+2}-{suit+1}" for _ in range(13) for suit in range(4)]
        data[key]["handCards"] = []
    return data
        

def game():
    engine = sdk.GameEngineClient()

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
            "handCards": []
        }, 
        "bottom": {
            "points": 0,
            "wins": 0, 
            "hands": 4,
            "discards": 3, 
            "deck": baseCards, 
            "handCards": []
        }
    }

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
            print(topAnswer)
        else:
            topAnswer = {"action": "wait", "cards": []}
        # print(topAnswer["action"])
        print(data["top"])
        if topAnswer["action"] == "play":
            data["top"]["hands"] -= 1
            data["top"]["points"] += countScore(topAnswer["cards"])
        elif topAnswer["action"] == "discard":
            data["top"]["discards"] -= 1

        moves = []
        if data["bottom"]["hands"]>0:
            moves.append("play")
            if data["bottom"]["discards"]>0:
                moves.append("discard")
        
        if moves:
            bottomAnswer = sdk.timeout_run(4, players[0].script, "make_choice", (data["bottom"]["handCards"], data["bottom"]["deck"], data["bottom"]["discards"], data["bottom"]["hands"], moves), bypass_errors=False)
            print(bottomAnswer)
        else:
            bottomAnswer = {"action": "wait", "cards": []}

        print(data["bottom"])
        if bottomAnswer["action"] == "play":
            data["bottom"]["hands"] -= 1
            data["bottom"]["points"] += countScore(bottomAnswer["cards"])
        elif bottomAnswer["action"] == "discard":
            data["bottom"]["discards"] -= 1


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
        for i in data["top"]["handCards"]:
            if not (i in topAnswer["cards"]):
                newHand.append(i)
        data["top"]["handCards"] = newHand
        
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

        if frame.get("winner"):
            break

    # TODO: указать, какая команда победила
    # engine.set_winner(engine.teams[0])

    engine.end()


if __name__ == "__main__":
    game()
