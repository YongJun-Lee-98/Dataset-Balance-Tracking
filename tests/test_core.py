from __future__ import annotations

import tempfile
import unittest

from models import ProjectState
from storage import load_state_from_file, save_state_to_file
from validators import ValidationError, prepare_bulk_names, validate_simple_json_structure


class ProjectStateTests(unittest.TestCase):
    def test_order_is_preserved_in_simple_json(self) -> None:
        state = ProjectState()
        animals = state.add_category("동물")
        vehicles = state.add_category("차량")

        state.add_subcategory(animals.id, "고양이")
        state.add_subcategory(animals.id, "강아지")
        state.add_subcategory(vehicles.id, "승용차")

        self.assertEqual(
            state.to_simple_json(),
            {
                "동물": {"고양이": 0, "강아지": 0},
                "차량": {"승용차": 0},
            },
        )

    def test_lowest_items_include_ties(self) -> None:
        state = ProjectState()
        category = state.add_category("동물")
        cat = state.add_subcategory(category.id, "고양이")
        dog = state.add_subcategory(category.id, "강아지")
        bird = state.add_subcategory(category.id, "새")

        state.increment_subcategory(category.id, cat.id)
        state.increment_subcategory(category.id, dog.id)

        lowest_ids = state.get_category(category.id).lowest_item_ids()
        self.assertEqual(lowest_ids, {bird.id})

    def test_below_average_items_include_ties(self) -> None:
        state = ProjectState()
        category = state.add_category("동물")
        cat = state.add_subcategory(category.id, "고양이")
        dog = state.add_subcategory(category.id, "강아지")
        bird = state.add_subcategory(category.id, "새")

        state.increment_subcategory(category.id, bird.id)
        state.increment_subcategory(category.id, bird.id)

        below_average_ids = state.get_category(category.id).below_average_item_ids()
        self.assertEqual(below_average_ids, {cat.id, dog.id})

    def test_category_total_count_is_sum_of_subcategories(self) -> None:
        state = ProjectState()
        category = state.add_category("동물")
        cat = state.add_subcategory(category.id, "고양이")
        dog = state.add_subcategory(category.id, "강아지")

        state.increment_subcategory(category.id, cat.id)
        state.increment_subcategory(category.id, dog.id)
        state.increment_subcategory(category.id, dog.id)

        self.assertEqual(state.get_category(category.id).total_count(), 3)

    def test_unbalanced_category_ids_use_most_common_total(self) -> None:
        state = ProjectState()
        animals = state.add_category("동물")
        vehicles = state.add_category("차량")
        plants = state.add_category("식물")

        cat = state.add_subcategory(animals.id, "고양이")
        car = state.add_subcategory(vehicles.id, "승용차")
        tree = state.add_subcategory(plants.id, "나무")

        state.increment_subcategory(animals.id, cat.id)
        state.increment_subcategory(animals.id, cat.id)
        state.increment_subcategory(vehicles.id, car.id)
        state.increment_subcategory(vehicles.id, car.id)
        state.increment_subcategory(plants.id, tree.id)

        self.assertEqual(state.balance_target_total(), 2)
        self.assertEqual(state.unbalanced_category_ids(), {plants.id})

    def test_unbalanced_category_ids_highlight_all_when_no_common_total(self) -> None:
        state = ProjectState()
        animals = state.add_category("동물")
        vehicles = state.add_category("차량")

        cat = state.add_subcategory(animals.id, "고양이")
        car = state.add_subcategory(vehicles.id, "승용차")

        state.increment_subcategory(animals.id, cat.id)
        state.increment_subcategory(animals.id, cat.id)
        state.increment_subcategory(vehicles.id, car.id)

        self.assertIsNone(state.balance_target_total())
        self.assertEqual(state.unbalanced_category_ids(), {animals.id, vehicles.id})

    def test_decrement_never_goes_below_zero(self) -> None:
        state = ProjectState()
        category = state.add_category("차량")
        item = state.add_subcategory(category.id, "트럭")

        self.assertEqual(state.decrement_subcategory(category.id, item.id), 0)
        self.assertEqual(state.get_category(category.id).get_item(item.id).count, 0)

    def test_bulk_name_preparation_deduplicates_and_trims(self) -> None:
        names = prepare_bulk_names("  고양이 \n\n강아지\n고양이\n  새  ")
        self.assertEqual(names, ["고양이", "강아지", "새"])

    def test_invalid_json_rejects_negative_counts(self) -> None:
        with self.assertRaises(ValidationError):
            validate_simple_json_structure({"동물": {"고양이": -1}})

    def test_storage_round_trip(self) -> None:
        state = ProjectState()
        category = state.add_category("사람")
        item = state.add_subcategory(category.id, "어린이")
        state.increment_subcategory(category.id, item.id)
        state.mark_clean()

        with tempfile.NamedTemporaryFile(suffix=".json") as handle:
            save_state_to_file(state, handle.name)
            loaded = load_state_from_file(handle.name)

        self.assertEqual(loaded.to_simple_json(), {"사람": {"어린이": 1}})
        self.assertFalse(loaded.dirty)


if __name__ == "__main__":
    unittest.main()
