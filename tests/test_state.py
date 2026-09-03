"""ViewState and Sprite: frozen, compared by value, copied rather than edited.

Value equality is not decoration here -- it is what lets StateFlow drop an
unchanged frame, so it is worth asserting outright.
"""

import unittest

from terminalgame.presentation.state import (
    CELL_COLS,
    CELL_ROWS,
    GRID_COLS,
    GRID_ROWS,
    PLAYFIELD_COLS,
    PLAYFIELD_ROWS,
    Sprite,
    ViewState,
)


def a_state(**overrides):
    """Builds a frame, with any field replaced by a keyword argument."""
    fields = dict(
        walls=("##", "  "),
        pills=("  ", "▪▪"),
        sprites=(Sprite(0, 0, ("X",)),),
        status_line=" score 0",
        tick=0,
    )
    fields.update(overrides)
    return ViewState(**fields)


class GeometryTest(unittest.TestCase):

    def test_the_grid_is_the_playfield_less_the_status_line(self):
        """The last character row is the readings, so it is not playable."""
        self.assertEqual((PLAYFIELD_ROWS - 1) // CELL_ROWS, GRID_ROWS)
        self.assertEqual(PLAYFIELD_COLS // CELL_COLS, GRID_COLS)

    def test_a_cell_is_wider_than_it_is_tall(self):
        """Because a terminal's character is about twice as tall as it is wide."""
        self.assertEqual(1, CELL_ROWS)
        self.assertEqual(2, CELL_COLS)


class SpriteTest(unittest.TestCase):

    def test_sprites_with_the_same_fields_are_equal(self):
        self.assertEqual(Sprite(1, 2, ("▐█▌",), 3), Sprite(1, 2, ("▐█▌",), 3))

    def test_a_sprite_that_moved_is_a_different_sprite(self):
        self.assertNotEqual(Sprite(1, 2, ("▐█▌",), 3), Sprite(1, 3, ("▐█▌",), 3))

    def test_a_sprite_cannot_be_edited_in_place(self):
        sprite = Sprite(1, 2, ("▐█▌",))

        with self.assertRaises(Exception):
            sprite.row = 5


class ViewStateTest(unittest.TestCase):

    def test_frames_with_the_same_contents_are_equal(self):
        """The comparison StateFlow makes to decide a frame is not worth drawing."""
        self.assertEqual(a_state(), a_state())

    def test_a_frame_at_a_different_tick_is_a_different_frame(self):
        """The tick is carried so two otherwise identical frames can be told apart."""
        self.assertNotEqual(a_state(tick=1), a_state(tick=2))

    def test_a_frame_with_a_moved_sprite_is_a_different_frame(self):
        self.assertNotEqual(a_state(), a_state(sprites=(Sprite(0, 1, ("X",)),)))

    def test_a_frame_cannot_be_edited_in_place(self):
        state = a_state()

        with self.assertRaises(Exception):
            state.status_line = "tampered"

    def test_with_sprites_replaces_them_rather_than_adding_to_them(self):
        state = a_state(sprites=(Sprite(0, 0, ("A",)), Sprite(1, 1, ("B",))))

        replaced = state._with_sprites(Sprite(2, 2, ("C",)))

        self.assertEqual((Sprite(2, 2, ("C",)),), replaced.sprites)

    def test_with_sprites_leaves_the_frame_it_was_asked_of_alone(self):
        original = a_state()
        sprites_before = original.sprites

        original._with_sprites(Sprite(9, 9, ("Z",)))

        self.assertEqual(sprites_before, original.sprites)

    def test_with_sprites_carries_the_rest_of_the_frame_across(self):
        state = a_state(status_line=" score 12", tick=7)

        replaced = state._with_sprites(Sprite(2, 2, ("C",)))

        self.assertEqual(state.walls, replaced.walls)
        self.assertEqual(state.pills, replaced.pills)
        self.assertEqual(" score 12", replaced.status_line)
        self.assertEqual(7, replaced.tick)

    def test_with_sprites_and_no_sprites_empties_the_layer(self):
        self.assertEqual((), a_state()._with_sprites().sprites)


if __name__ == "__main__":
    unittest.main()
