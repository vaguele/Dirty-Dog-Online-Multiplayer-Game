from player import Player
from deck import Deck
import random
from typing import Any, Optional, Tuple, Dict

# Change this value to adjust the default maximum hand size used by the
# game. It's intentionally a single top-level constant so you can edit it
# quickly when you want a different default during testing or play.
DEFAULT_MAX_HANDS = 3

class Game:
    def __init__(self):
        self.players = {}  # conn: Player -> hand
        self.ready_players = set()
        self.min_players = 2
        self.deck = Deck()
        self.turn_order = []
        
        self.last_conn = None
        self.current_turn_index = 0
        # start with one card per player; will increment each round in reset()
        self.cards_per_player = 1
        self.max_cards = 0
        
        # lifecycle controls for dealing: when cards_per_player reaches the
        # computed max, play that size for `hold_rounds` additional rounds,
        # then enter decreasing phase where cards_per_player decreases by 1
        # each round until it reaches 0 (match over).
        self.hold_rounds = 3
        self.hold_rounds_remaining = None
        self.decreasing_phase = False
        self.match_over = False

        self.bids = {}
        self.bid_count = 0

        self.played_cards = {}

        self.game_started = False
        self.BID_PHASE = False
        self.PLAY_PHASE = False

        self.leading_suit = None
        self.trump = None
        self.speaker_order = []
        self.current_speaker_index = 0

    def add_player(self, conn: Any, name: str) -> None:
        self.players[conn] = Player(name)
        self.refresh_speaker_order()

    def remove_player(self, conn: Any) -> None:
        if conn in self.players:
            del self.players[conn]
        if conn in self.ready_players:
            self.ready_players.remove(conn)
        if conn in self.turn_order:
            self.turn_order.remove(conn)
        self.refresh_speaker_order()

    def refresh_speaker_order(self) -> None:
        self.speaker_order = list(self.players.keys())
        if self.speaker_order:
            self.current_speaker_index %= len(self.speaker_order)
        else:
            self.current_speaker_index = 0

    def get_current_speaker_conn(self) -> Any:
        if not self.speaker_order:
            self.refresh_speaker_order()
        if not self.speaker_order:
            return None
        return self.speaker_order[self.current_speaker_index]

    def is_current_speaker(self, conn: Any) -> bool:
        return self.get_current_speaker_conn() == conn

    def advance_speaker(self) -> Any:
        if not self.speaker_order:
            self.refresh_speaker_order()
        if not self.speaker_order:
            return None
        self.current_speaker_index = (self.current_speaker_index + 1) % len(self.speaker_order)
        return self.get_current_speaker_conn()

    def mark_ready(self, conn: Any) -> bool:
        self.ready_players.add(conn)
        return (
            len(self.players) >= self.min_players
            and len(self.ready_players) == len(self.players)
        )
    
    def start_game(self) -> None:
        self.game_started = True

        # Compute maximum cards per player so that after dealing each player gets
        # the same number and one card remains to reveal trump.
        num_players = len(self.players)
        deck_size = len(self.deck.cards)
        computed_max = (deck_size - 1) // num_players if num_players > 0 else 0

        # Cap the default computed max to a reasonable play limit. Change
        # DEFAULT_MAX_HANDS at the top of this file to easily adjust the
        # default behavior for future sessions.
        self.max_cards = min(computed_max, DEFAULT_MAX_HANDS)

        self.deck.shuffle()
        self.deck.deal(list(self.players.values()), self.cards_per_player)

        self.turn_order = list(self.players.keys())
        random.shuffle(self.turn_order)
        self.current_turn_index = 0
        self.refresh_speaker_order()
        # Reveal trump from deck if any
        try:
            self.trump = self.deck.reveal_trump()
        except Exception:
            self.trump = None
        

    def place_bid(self, conn: Any, bid: int) -> None:
        self.bids[conn] = bid
        self.bid_count += bid
        

            
    def build_hands(self) -> Dict[Any, str]:
        hands: Dict[Any, str] = {}
        for conn, player in self.players.items():
            hand_str = ', '.join(str(card) for card in player.hand)
            hands[conn] = f"Your hand: {hand_str}"
        return hands

    def has_suit(self, player: Player, suit: str) -> bool:
        return any(card.suit == suit for card in player.hand)

    def validate_play(self, conn: Any, card_text: str) -> Tuple[Optional[Any], Optional[str]]:
        player = self.players.get(conn)
        if not player:
            return None, "You are not part of this game."

        matching_card = next((card for card in player.hand if str(card) == card_text), None)
        if not matching_card:
            return None, "You don't have that card."

        if self.leading_suit and self.has_suit(player, self.leading_suit) and matching_card.suit != self.leading_suit:
            return None, f"You must follow suit: {self.leading_suit}."

        return matching_card, None

    def record_play(self, conn: Any, card: Any) -> None:
        player = self.players[conn]
        self.played_cards[conn] = card
        player.hand.remove(card)

        if len(self.played_cards) == 1:
            self.leading_suit = card.suit
        

    def resolve_trick(self) -> Tuple[Any, Any]:
        best_conn: Any = None
        best_card: Any = None
        best_score = -1

        for pconn, card in self.played_cards.items():
            if self.trump and card.suit == self.trump:
                score = card.weight[card.value] + 100
            elif card.suit == self.leading_suit:
                score = card.weight[card.value] + 50
            else:
                score = 0

            if score > best_score:
                best_score = score
                best_conn = pconn
                best_card = card

        return best_conn, best_card


    def hand_complete(self) -> bool:
        return all(len(player.hand) == 0 for player in self.players.values())

    def score_round(self) -> None:
        for player in self.players.values():
            if player.tricks == player.bid:
                player.score += 5 + player.bid
            else:
                player.score -= max(player.bid, player.tricks)
        

    def get_current_player_conn(self) -> Any:
        if not self.turn_order or not (0 <= self.current_turn_index < len(self.turn_order)):
            return None
        return self.turn_order[self.current_turn_index]
    
    def is_player_turn(self, conn):
        return conn is not None and conn == self.get_current_player_conn()

    def get_last_player_conn(self):
        """Return the connection object for the last player in the turn order.

        Returns None if there is no turn order yet.
        """
        if not self.turn_order:
            return None
        return self.turn_order[-1]

    def advance_turn(self):
        if not self.turn_order:
            self.current_turn_index = 0
            return None
        self.current_turn_index = (self.current_turn_index + 1) % len(self.turn_order)
        return None

    def debug_state(self):
        print("Players:", [p.name for p in self.players.values()])
        print("Hands:", [p.hand for p in self.players.values()])
        print("Ready:", [self.players[c].name for c in self.ready_players])
        print("Turn order:", [self.players[c].name for c in self.turn_order])
        current_conn = self.get_current_player_conn()
        if current_conn is not None:
            print("Current:", self.players[current_conn].name)
        else:
            print("Current: none")
        return None

    def reset(self):
        # Preserve player objects and connections, reset per-hand state
        for player in self.players.values():
            player.round_reset()

        self.ready_players = set()
        self.deck.refresh()
        self.turn_order = []
        self.last_conn = None
        self.current_turn_index = 0


        # Lifecycle transitions:
        if self.max_cards <= 0:
            # No cards can be dealt while leaving a trump card; match over
            self.cards_per_player = 0
            self.match_over = True
        elif not self.decreasing_phase:
            # Ramp up toward max_cards
            if self.cards_per_player < self.max_cards:
                self.cards_per_player += 1
            else:
                # We've reached or exceeded max; initialize hold counter if needed
                if self.hold_rounds_remaining is None:
                    self.hold_rounds_remaining = self.hold_rounds

                if self.hold_rounds_remaining > 0:
                    # Consume one of the hold rounds and remain at max
                    self.hold_rounds_remaining -= 1
                    self.cards_per_player = self.max_cards
                else:
                    # Finished holding at max -> begin decreasing next round
                    self.decreasing_phase = True
                    self.cards_per_player = self.max_cards - 1
        else:
            # Decreasing phase: reduce cards by one each round
            self.cards_per_player = self.cards_per_player - 1

        # If we've dropped to zero, the match is over
        if self.cards_per_player <= 0:
            self.match_over = True

        self.bids = {}
        self.bid_count = 0
        self.played_cards = {}

        self.game_started = False
        self.refresh_speaker_order()
        self.BID_PHASE = False
        self.PLAY_PHASE = False

        self.leading_suit = None
        self.trump = None
        return None