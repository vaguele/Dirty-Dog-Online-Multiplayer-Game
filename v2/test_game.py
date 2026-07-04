import unittest

from game import Game
from card import Card


class TestGame(unittest.TestCase):
    def setUp(self):
        self.game = Game()
        # use simple string keys as "connections"
        self.p1 = "p1"
        self.p2 = "p2"
        self.p3 = "p3"
        from player import Player
        self.game.players[self.p1] = Player("Alice")
        self.game.players[self.p2] = Player("Bob")
        self.game.players[self.p3] = Player("Cara")

    def test_validate_play_not_in_game(self):
        card, err = self.game.validate_play("nope", "AS")
        self.assertIsNone(card)
        self.assertIsNotNone(err)

    def test_validate_play_missing_card(self):
        card, err = self.game.validate_play(self.p1, "AS")
        self.assertIsNone(card)
        self.assertIn("don't have", err.lower())

    def test_validate_play_follow_suit_enforced(self):
        # give p1 a spade and p2 has both a spade and a heart
        self.game.players[self.p1].hand = [Card('♠', '10')]
        self.game.players[self.p2].hand = [Card('♠', '9'), Card('♥', 'A')]
        # leading suit is spades
        self.game.leading_suit = '♠'

        # p2 must follow suit when attempting to play a heart
        card, err = self.game.validate_play(self.p2, 'A♥')
        self.assertIsNone(card)
        self.assertIsNotNone(err)

    def test_resolve_trick_prefers_trump_then_lead(self):
        # p1 plays high heart (leading), p2 plays trump small, p3 plays heart
        self.game.trump = '♠'
        self.game.leading_suit = '♥'
        c1 = Card('♥', 'K')
        c2 = Card('♠', '2')
        c3 = Card('♥', 'Q')
        self.game.played_cards = {self.p1: c1, self.p2: c2, self.p3: c3}

        winner_conn, winner_card = self.game.resolve_trick()
        self.assertEqual(winner_conn, self.p2)
        self.assertEqual(winner_card, c2)

    def test_score_round_updates_scores(self):
        # set bids/tricks
        self.game.players[self.p1].bid = 2
        self.game.players[self.p1].tricks = 2
        self.game.players[self.p2].bid = 1
        self.game.players[self.p2].tricks = 0

        self.game.score_round()

        self.assertEqual(self.game.players[self.p1].score, 7)  # 5 + bid
        self.assertEqual(self.game.players[self.p2].score, -1)  # -max(bid,tricks)

    def test_hand_complete(self):
        self.game.players[self.p1].hand = []
        self.game.players[self.p2].hand = []
        self.game.players[self.p3].hand = []
        self.assertTrue(self.game.hand_complete())
        self.game.players[self.p3].hand = [Card('♣', '2')]
        self.assertFalse(self.game.hand_complete())

    def test_speaker_order_rotates(self):
        self.game.refresh_speaker_order()
        self.assertEqual(self.game.get_current_speaker_conn(), self.p1)
        self.game.advance_speaker()
        self.assertEqual(self.game.get_current_speaker_conn(), self.p2)
        self.game.advance_speaker()
        self.assertEqual(self.game.get_current_speaker_conn(), self.p3)


if __name__ == '__main__':
    unittest.main()
