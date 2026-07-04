import random, os
from deck import Deck
from player import Player
from datetime import datetime

# Press Control + Command + Space to open the emoji panel
#  assure tie breaking logic quality
# ENDGAME: maybe add a solo player mode, with CPUs
# multiplayer
# Trophies
# commentary

def show_trump(trump):
    print(f"\nTrump suit: {trump}" if trump else "\nNO TRUMP")


def play_tricks(players, trump, cards_per_player):
    for _ in range(cards_per_player):
        leading_suit = players[0].play_lead_card(trump)
        for player in players[1:]:
            player.play_card(leading_suit, trump)

        Player.compare_by = "strength"
        winner = max(players)
        print(f"\n--{winner.name} takes the trick--")
        winner.tricks += 1

        new_lead = players.index(winner)
        for _ in range(new_lead):
            players.append(players.pop(0))


def play_round(deck, players, cards_per_player):
    deck.deal(players, cards_per_player)
    for player in players:
        print(f"\n{player.name}'s hand: {player.hand}")

    trump = deck.reveal_trump()
    show_trump(trump)

    for player in players[:-1]:
        player.place_bid()
    players[-1].place_last_bid()

    play_tricks(players, trump, cards_per_player)

    for player in players:
        if player.bid == player.tricks:
            player.score += player.bid + 5
        else:
            player.score -= max(player.bid, player.tricks)
        print(f"{player.name}'s current score is {player.score}")
        player.round_reset()
    deck.refresh()


def play_overtime_round(deck, players, cards_per_player):
    for player in players[:-1]:
        player.place_bid()
    players[-1].place_last_bid()

    for player in players:
        print(f"\n{player.name}'s hand: {player.hand}")

    trump = deck.reveal_trump()
    show_trump(trump)

    play_tricks(players, trump, cards_per_player)

    for player in players:
        if player.tied and player.bid == player.tricks:
            player.score += player.bid + 5
        elif player.tied and player.bid != player.tricks:
            player.score -= max(player.bid, player.tricks)
        print(f"{player.name}'s score: {player.score}")
        player.round_reset()

def play_game(deck, players, max_cards, cards_per_player):
    round = 1
    # consider custom round limits, 5 rounds: 1 -> 2 -> 2 -> 2-> 1
    while cards_per_player != max_cards:
        print(f"\nROUND: {round}")
        play_round(deck, players, cards_per_player)
        cards_per_player += 1
        round += 1
        input("Press Enter to continue...")

    for _ in range(3):
        print(f"\nROUND: {round}")
        play_round(deck, players, cards_per_player)
        round += 1
        input("Press Enter to start the next round...")

    while cards_per_player != 0:
        print(f"\nROUND: {round}")
        play_round(deck, players, cards_per_player)
        cards_per_player -= 1
        round += 1
        input("Press Enter to continue...")

def tie_breaker(deck, players, placement):
    if placement == "winner":
        print("\nLooks like theres a tie for First Place")
        max_cards = (len(deck.cards) - 1) // len(players)
        cards_per_player = min(5, max_cards)
        deck.deal(players, cards_per_player)

        round_num = 1
        while cards_per_player != 0:
            print(f"\nOVERTIME ROUND: {round_num}")
            play_overtime_round(deck, players, cards_per_player)
            cards_per_player -= 1
            round_num += 1

    elif placement == "loser":
        print("\nLooks like theres a tie for Last Place")
        deck.deal(players, 1)

        for player in players:
            player.play_overtime_card()
        Player.compare_by = "strength"

        min_strength = min(player.strength for player in players)
        for player in players:
            if player.strength == min_strength:
                player.score -= 1

def game_results(deck, players):
    Player.compare_by = "score"   
    players.sort(reverse = True)
    
    max_score = max(players)
    min_score = min(players)

    count = 0
    for player in players:
        if player.score == max_score:
            player.tied = True
            count += 1
    if count > 1:
        tie_breaker(deck, players, "winner")
    
    count = 0
    lowest_players = []
    for player in players:
        if player.score == min_score:
            lowest_players.append(player)
            count += 1
    if count > 1:
        tie_breaker(deck, lowest_players, "loser")

    print("🏆 Final Leaderboard 🏆")

    folder = os.path.dirname(__file__)
    filename = datetime.now().strftime("leaderboard_%Y-%m-%d_%H-%M-%S.txt")
    save_folder = os.path.join(folder, "previous games")

    os.makedirs(save_folder, exist_ok=True)
    filepath = os.path.join(save_folder, filename)

    with open(filepath, "w") as file:
        for i in range(len(players)):
            if i == 0:
                print(f"🥇 {players[i].name}: {players[i].score}")
                file.write(f"🥇 {players[i].name}: {players[i].score}\n")
            elif i == 1:
                print(f"🥈 {players[i].name}: {players[i].score}")
                file.write(f"🥈 {players[i].name}: {players[i].score}\n")
            elif i == 2:
                print(f"🥉 {players[i].name}: {players[i].score}")
                file.write(f"🥉 {players[i].name}: {players[i].score}\n")
            else:
                print(f"{i+1}. {players[i].name}: {players[i].score}")
                file.write(f"{i+1}. {players[i].name}: {players[i].score}\n")

def main():
    players = []
    
    while True:
        try:
            num_players = int(input("Please enter the number of players: "))
            if num_players < 2:
                raise ValueError("Too few players. Minimum is 2.")
            if num_players > 51:
                raise ValueError("Too many players. Max is 51.")
            break
        except ValueError as e:
            print(f"Invalid input: {e}")

    for _ in range(num_players):
        players.append(Player(input("Enter Name: ")))
    
    random.shuffle(players)
    print(f"\nHere is the game's order: {players}")

    deck = Deck()
    # max_cards = len(deck.cards) -1 // num_players
    max_cards = 3
    cards_per_player = 1

    play_game(deck, players, max_cards, cards_per_player)
    game_results(deck, players)

    while True:
        try:
            restart = input("\nWould you like to play again? (Y/N): ").upper()
            if restart not in ["Y", "N"]:
                raise ValueError
            break
        except ValueError:
            print("Invalid Input. Please enter Y or N")

    while restart == "Y":
        for player in players:
            player.game_reset()

        play_game(deck, players, max_cards, cards_per_player)
        game_results(deck, players)

        while True:
            try:
                restart = input("\nWould you like to play again? (Y/N): ").upper()
                if restart not in ["Y", "N"]:
                    raise ValueError
                break
            except ValueError:
                print("Invalid Input. Please enter Y or N")

if __name__ == "__main__":
    main()