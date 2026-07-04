from card import Card
import random
from typing import Optional

class Deck:
    def __init__(self):
        self.cards = []
        for suit in Card.type:
            for value in Card.weight:
                self.cards.append(Card(suit, value))
        self.shuffle()

    def shuffle(self) -> None:
        random.shuffle(self.cards)
        

    def deal(self, players, cards_per_player) -> None:
        for _ in range(cards_per_player):
            for player in players:
                player.hand.append(self.cards.pop(0))
        

    def reveal_trump(self) -> Optional[str]:
        if self.cards:
            top_card = self.cards.pop(0)
            if top_card.value == 'A':
                return None  # NO TRUMP rule
            return top_card.suit
        return None
    
    def refresh(self) -> None:
        self.cards = []
        for suit in Card.type:
            for value in Card.weight:
                self.cards.append(Card(suit, value))
        self.shuffle()
        