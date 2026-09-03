"""StateFlow: always has a value, replays it, and drops equal emissions."""

import unittest

from terminalgame.util.flow import StateFlow


class StateFlowTest(unittest.TestCase):

    def test_holds_its_initial_value(self):
        self.assertEqual("first", StateFlow("first").value)

    def test_subscribing_delivers_the_current_value_at_once(self):
        flow = StateFlow(7)
        received = []

        flow.subscribe(received.append)

        self.assertEqual([7], received)

    def test_emitting_a_different_value_updates_and_notifies(self):
        flow = StateFlow(1)
        received = []
        flow.subscribe(received.append)

        changed = flow.emit(2)

        self.assertTrue(changed)
        self.assertEqual(2, flow.value)
        self.assertEqual([1, 2], received)

    def test_emitting_an_equal_value_is_dropped(self):
        """The conflation that keeps an unchanged frame off the terminal."""
        flow = StateFlow((1, 2))
        received = []
        flow.subscribe(received.append)

        changed = flow.emit((1, 2))  # equal, but a different object

        self.assertFalse(changed)
        self.assertEqual([(1, 2)], received, "an equal value reached the subscriber")

    def test_every_subscriber_is_notified_in_subscription_order(self):
        flow = StateFlow(0)
        order = []
        flow.subscribe(lambda value: order.append(("first", value)))
        flow.subscribe(lambda value: order.append(("second", value)))
        order.clear()  # drop the two replays of the initial value

        flow.emit(9)

        self.assertEqual([("first", 9), ("second", 9)], order)

    def test_unsubscribing_stops_delivery(self):
        flow = StateFlow(0)
        received = []
        unsubscribe = flow.subscribe(received.append)

        unsubscribe()
        flow.emit(1)

        self.assertEqual([0], received)
        self.assertEqual(1, flow.value, "the value still moved on")

    def test_unsubscribing_twice_is_harmless(self):
        flow = StateFlow(0)
        unsubscribe = flow.subscribe(lambda _: None)

        unsubscribe()
        unsubscribe()  # would raise if it removed blindly

    def test_a_subscriber_may_unsubscribe_while_being_notified(self):
        """The reason emit iterates over a copy of the subscriber list.

        Removing from the list being walked would skip whoever came next, so
        the second subscriber is the one that proves the copy is there.
        """
        flow = StateFlow(0)
        received = []

        # Held in a list because subscribing calls quitter straight away,
        # before there is any handle for it to let go of.
        handle = []

        def quitter(value):
            received.append(("quitter", value))
            if handle:
                handle.pop()()

        handle.append(flow.subscribe(quitter))
        flow.subscribe(lambda value: received.append(("stayer", value)))
        received.clear()

        flow.emit(1)

        self.assertEqual([("quitter", 1), ("stayer", 1)], received)

    def test_update_emits_the_transformed_value(self):
        flow = StateFlow(10)
        received = []
        flow.subscribe(received.append)

        changed = flow._update(lambda value: value * 3)

        self.assertTrue(changed)
        self.assertEqual(30, flow.value)
        self.assertEqual([10, 30], received)

    def test_update_to_an_equal_value_is_dropped(self):
        flow = StateFlow(10)
        received = []
        flow.subscribe(received.append)

        changed = flow._update(lambda value: value)

        self.assertFalse(changed)
        self.assertEqual([10], received)


if __name__ == "__main__":
    unittest.main()
