import random
from dataclasses import dataclass
from typing import List
import matplotlib.pyplot as plt

# Bright color palette for a cheerful look
COLOR_PALETTE = [
    "#FF6B6B",
    "#F7B801",
    "#6BCB77",
    "#4D96FF",
    "#FFADAD",
    "#9D4EDD",
]

@dataclass
class Puzzle:
    title: str
    categories: List[str]
    items: List[str]
    clues: List[str]

# Basic vocabulary for random generation
NAMES = ["Ana", "Bruno", "Carla", "Diego", "Eduardo", "Fernanda"]
ANIMALS = ["gato", "cachorro", "passarinho", "peixe"]
CORES = ["vermelho", "azul", "verde", "amarelo"]
CASAS = ["de tijolo", "de madeira", "de pedra", "de vidro"]

CATEGORY_SETS = [
    ("Nome", NAMES),
    ("Animal", ANIMALS),
    ("Cor", CORES),
    ("Casa", CASAS),
]


def random_solution() -> List[List[str]]:
    """Generate a random solution table."""
    # Each category set must have at least len(items) items
    base_items = [items[:4] for _, items in CATEGORY_SETS]
    shuffled = [random.sample(lst, 4) for lst in base_items]
    return shuffled


def generate_clues(solution: List[List[str]]) -> List[str]:
    """Generate simple clues from the solution. Not guaranteed to be solvable."""
    clues = []
    categories = [cat for cat, _ in CATEGORY_SETS]
    for i in range(4):
        pair = random.sample(range(4), 2)
        cat1, cat2 = categories[pair[0]], categories[pair[1]]
        item1 = solution[pair[0]][i]
        item2 = solution[pair[1]][i]
        clues.append(f"{item1} combina com {item2}.")
    # Negative clues
    for i in range(2):
        c1, c2 = random.sample(range(4), 2)
        item1 = random.choice(solution[c1])
        item2 = random.choice(list(set(CATEGORY_SETS[c2][1]) - {solution[c2][solution[c1].index(item1)]}))
        clues.append(f"{item1} nao combina com {item2}.")
    return clues


def generate_puzzle(index: int) -> Puzzle:
    solution = random_solution()
    categories = [cat for cat, _ in CATEGORY_SETS]
    items = ["A", "B", "C", "D"]
    title = f"Puzzle {index + 1}"
    clues = generate_clues(solution)
    return Puzzle(title, categories, items, clues)


def draw_logic_4x4_compact_clues(ax, puzzle: Puzzle, y_origin: float):
    ax.axis("off")
    ax.text(0, y_origin + 0.32, puzzle.title, fontsize=12, weight="bold", transform=ax.transAxes)
    table_data = [[""] + puzzle.items] + [[cat] + ["[ ]"] * len(puzzle.items) for cat in puzzle.categories]
    table = ax.table(
        cellText=table_data,
        colWidths=[0.15] * 5,
        cellLoc="center",
        loc="upper left",
        bbox=[0, y_origin, 1, 0.2],
    )
    for key, cell in table.get_celld().items():
        cell.set_linewidth(1)
        if key[0] == 0 or key[1] == 0:
            cell.set_text_props(weight="bold", fontsize=10)
            cell.set_facecolor("#F0F0F0")
        else:
            cell.set_facecolor(random.choice(COLOR_PALETTE))
    for i, clue in enumerate(puzzle.clues):
        ax.text(
            0,
            y_origin - 0.05 - 0.025 * i,
            f"- {clue}",
            fontsize=9,
            ha="left",
            transform=ax.transAxes,
        )


def generate_book(num_puzzles: int, output_path: str):
    puzzles = [generate_puzzle(i) for i in range(num_puzzles)]
    fig, ax = plt.subplots(figsize=(8.5, 11))
    y_positions = [0.65, 0.05]
    for puzzle, y_origin in zip(puzzles, y_positions):
        draw_logic_4x4_compact_clues(ax, puzzle, y_origin)
    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)


if __name__ == "__main__":
    output_file = "Logic_Grid_Puzzles_Random.pdf"
    generate_book(2, output_file)
    print(f"PDF gerado em {output_file}")
