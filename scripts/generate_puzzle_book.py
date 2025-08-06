import random
from dataclasses import dataclass
from typing import List, Any, Dict
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

# --- Configuration Constants ---
PUZZLE_SIZE = 4
PAGESIZE_WIDTH_INCHES = 8.5
PAGESIZE_HEIGHT_INCHES = 11

# Bright color palette for a cheerful look
COLOR_PALETTE = [
    "#FF6B6B",
    "#F7B801",
    "#6BCB77",
    "#4D96FF",
    "#FFADAD",
    "#9D4EDD",
]

# --- ENHANCEMENT: More flexible and extensive vocabulary for categories ---
CATEGORY_DEFINITIONS = [
    ("Nome", ["Ana", "Bruno", "Carla", "Diego", "Eduardo", "Fernanda", "Gustavo", "Helena"]),
    ("Animal", ["gato", "cachorro", "passarinho", "peixe", "coelho", "tartaruga", "hamster", "periquito"]),
    ("Cor", ["vermelho", "azul", "verde", "amarelo", "roxo", "laranja", "rosa", "marrom"]),
    ("Casa", ["de tijolo", "de madeira", "de pedra", "de vidro", "de metal", "de barro", "de gelo", "de bambu"]),
]

@dataclass
class GeneratedPuzzle:
    """Represents a single generated puzzle of any type."""
    puzzle_type: str
    content: Any
    solution: Any
    display_info: Dict[str, Any]

class SudokuGenerator:
    def __init__(self, difficulty: str):
        self.difficulty = difficulty

    def generate_puzzle(self, index: int) -> GeneratedPuzzle:
        grid = [[f"Grid {self.difficulty[0].upper()}", "", "", "", "", "", "", "", ""],
                ["", "", "", "", "", "", "", "", ""],
                ["", "", "", "", "", "", "", "", ""],
                ["", "", "", "", "", "", "", "", ""],
                ["", "", "", "", "", "", "", "", ""],
                ["", "", "", "", "", "", "", "", ""],
                ["", "", "", "", "", "", "", "", ""],
                ["", "", "", "", "", "", "", "", ""],
                ["", "", "", "", "", "", "", "", f"#{index + 1}"]]
        solution_content = [[f"Solução {self.difficulty[0].upper()}", "", "", "", "", "", "", "", ""],
                            ["", "", "", "", "", "", "", "", f"#{index + 1}"]]
        display_info = {
            "title": f"Sudoku - Nível {self.difficulty.capitalize()} #{index + 1}",
            "instructions": "Preencha a grade para que cada linha, coluna e bloco 3x3 contenha todos os dígitos de 1 a 9, sem repetições.",
        }
        return GeneratedPuzzle(f"sudoku_{self.difficulty}", grid, solution_content, display_info)

class LogicPuzzleGenerator:
    def __init__(self, puzzle_size: int = PUZZLE_SIZE, color_palette: List[str] = COLOR_PALETTE):
        self.puzzle_size = puzzle_size
        self.color_palette = color_palette
        self.categories_map = {name: items for name, items in CATEGORY_DEFINITIONS}
        self.category_names = [name for name, _ in CATEGORY_DEFINITIONS]
        for name, items in self.categories_map.items():
            if len(items) < self.puzzle_size:
                raise ValueError(f"Category '{name}' must have at least {self.puzzle_size} items.")
        if len(self.category_names) < 2:
            raise ValueError("At least two categories are required to generate a logic puzzle.")

    def _generate_solution(self) -> List[List[str]]:
        main_entity_items = random.sample(self.categories_map[self.category_names[0]], self.puzzle_size)
        solution_matrix = [main_entity_items]
        for i in range(1, len(self.category_names)):
            category_name = self.category_names[i]
            available_items = random.sample(self.categories_map[category_name], self.puzzle_size)
            random.shuffle(available_items)
            solution_matrix.append(available_items)
        return solution_matrix

    def _generate_clues(self, solution: List[List[str]]) -> List[str]:
        clues = []
        for _ in range(self.puzzle_size + random.randint(0, self.puzzle_size // 2)):
            cat_indices = random.sample(range(len(self.category_names)), 2)
            item1_cat_idx, item2_cat_idx = cat_indices[0], cat_indices[1]
            assoc_idx = random.randrange(self.puzzle_size)
            item1 = solution[item1_cat_idx][assoc_idx]
            item2 = solution[item2_cat_idx][assoc_idx]
            clues.append(f"{item1} combina com {item2}.")
        for _ in range(self.puzzle_size * 2 + random.randint(0, self.puzzle_size)):
            cat1_idx, cat2_idx = random.sample(range(len(self.category_names)), 2)
            item1 = random.choice(solution[cat1_idx])
            item1_solution_position = solution[cat1_idx].index(item1)
            matching_item_in_cat2 = solution[cat2_idx][item1_solution_position]
            possible_negative_items = list(set(self.categories_map[self.category_names[cat2_idx]]) - {matching_item_in_cat2})
            if possible_negative_items:
                negative_item = random.choice(possible_negative_items)
                clues.append(f"{item1} não combina com {negative_item}.")
        random.shuffle(clues)
        clues = list(dict.fromkeys(clues))
        return clues

    def generate_puzzle(self, index: int) -> GeneratedPuzzle:
        solution = self._generate_solution()
        categories = self.category_names
        items_for_header = solution[0]
        clues = self._generate_clues(solution)
        display_info = {
            "title": f"Quebra-Cabeça de Lógica #{index + 1}",
            "categories": categories,
            "items": items_for_header,
            "instructions": "Use as pistas para preencher a grade e descobrir as associações corretas. Marque 'O' para verdadeiro e 'X' para falso.",
        }
        content = {
            "clues": clues,
            "grid_setup": "Initial grid setup (could be a matrix of empty/marked cells)"
        }
        return GeneratedPuzzle("logic_grid", content, solution, display_info)

    def draw_puzzle(self, ax, generated_puzzle: GeneratedPuzzle, y_origin_norm: float, puzzle_height_norm: float):
        ax.axis("off")
        TITLE_HEIGHT_RATIO = 0.05
        INSTRUCTIONS_HEIGHT_RATIO = 0.05
        TABLE_HEIGHT_RATIO = 0.35
        CLUES_HEIGHT_RATIO = 0.50
        title_y = y_origin_norm + puzzle_height_norm * (1 - TITLE_HEIGHT_RATIO / 2)
        instructions_y = y_origin_norm + puzzle_height_norm * (1 - TITLE_HEIGHT_RATIO - INSTRUCTIONS_HEIGHT_RATIO / 2)
        table_bottom_y = y_origin_norm + puzzle_height_norm * (CLUES_HEIGHT_RATIO)
        title_fontsize = 12
        instructions_fontsize = 9
        table_fontsize = 9
        clue_fontsize = 8.5
        ax.text(0.05, title_y, generated_puzzle.display_info["title"], fontsize=title_fontsize, weight="bold", transform=ax.transAxes, ha='left', va='center')
        ax.text(0.05, instructions_y, generated_puzzle.display_info["instructions"], fontsize=instructions_fontsize, transform=ax.transAxes, ha='left', va='center', wrap=True)
        table_data = [[""] + generated_puzzle.display_info["items"]] + [[cat] + ["[ ]"] * self.puzzle_size for cat in generated_puzzle.display_info["categories"]]
        max_category_len = max(len(cat) for cat in generated_puzzle.display_info["categories"])
        max_item_len = max(len(item) for item in generated_puzzle.display_info["items"])
        first_col_width = max(0.15, 0.008 * max_category_len)
        other_col_width = (1.0 - first_col_width) / (self.puzzle_size)
        col_widths = [first_col_width] + [other_col_width] * self.puzzle_size
        table = ax.table(cellText=table_data, colWidths=col_widths, cellLoc="center", loc="upper left", bbox=[0, table_bottom_y, 1, puzzle_height_norm * TABLE_HEIGHT_RATIO])
        table.auto_set_font_size(False)
        table.set_fontsize(table_fontsize)
        for key, cell in table.get_celld().items():
            cell.set_linewidth(1)
            if key[0] == 0 or key[1] == 0:
                cell.set_text_props(weight="bold", fontsize=table_fontsize)
                cell.set_facecolor("#F0F0F0")
            else:
                cell.set_facecolor(random.choice(self.color_palette))
        clue_start_y = table_bottom_y - (puzzle_height_norm * 0.02)
        clue_line_height = 0.025
        max_chars_per_line = 75
        wrapped_clues = []
        for clue in generated_puzzle.content["clues"]:
            if len(clue) > max_chars_per_line:
                current_line = []
                words = clue.split(' ')
                for word in words:
                    if len(' '.join(current_line + [word])) <= max_chars_per_line:
                        current_line.append(word)
                    else:
                        wrapped_clues.append(' '.join(current_line))
                        current_line = [word]
                if current_line:
                    wrapped_clues.append(' '.join(current_line))
            else:
                wrapped_clues.append(clue)
        for i, clue_line in enumerate(wrapped_clues):
            current_clue_y = clue_start_y - clue_line_height * i
            if current_clue_y < y_origin_norm:
                break
            ax.text(0.05, current_clue_y, f"- {clue_line}", fontsize=clue_fontsize, ha="left", va="top", transform=ax.transAxes, wrap=False)

class PuzzleBookGenerator:
    def __init__(self, logic_puzzle_generator: LogicPuzzleGenerator, sudoku_easy_generator: SudokuGenerator, sudoku_hard_generator: SudokuGenerator):
        self.logic_puzzle_generator = logic_puzzle_generator
        self.sudoku_easy_generator = sudoku_easy_generator
        self.sudoku_hard_generator = sudoku_hard_generator
        self.puzzle_generators = {
            "logic_grid": self.logic_puzzle_generator,
            "sudoku_easy": self.sudoku_easy_generator,
            "sudoku_hard": self.sudoku_hard_generator,
        }

    def generate_book(self, book_title: str, book_subtitle: str, puzzle_specs: List[Dict[str, Any]], puzzles_per_page: int, output_path: str):
        if puzzles_per_page <= 0:
            raise ValueError("'puzzles_per_page' must be a positive integer.")
        all_generated_puzzles: List[GeneratedPuzzle] = []
        for spec in puzzle_specs:
            puzzle_type = spec["type"]
            count = spec["count"]
            generator = self.puzzle_generators.get(puzzle_type)
            if not generator:
                print(f"Aviso: Gerador para '{puzzle_type}' não encontrado. Ignorando este tipo de puzzle.")
                continue
            for i in range(count):
                all_generated_puzzles.append(generator.generate_puzzle(i))
        random.shuffle(all_generated_puzzles)
        num_total_puzzles = len(all_generated_puzzles)
        if num_total_puzzles == 0:
            print("Nenhum puzzle gerado. Verifique as especificações dos puzzles.")
            return
        num_pages = (num_total_puzzles + puzzles_per_page - 1) // puzzles_per_page
        with PdfPages(output_path) as pdf:
            self._draw_title_page(pdf, book_title, book_subtitle)
            for page_idx in range(num_pages):
                fig, ax = plt.subplots(figsize=(PAGESIZE_WIDTH_INCHES, PAGESIZE_HEIGHT_INCHES))
                puzzles_on_this_page = all_generated_puzzles[page_idx * puzzles_per_page : (page_idx + 1) * puzzles_per_page]
                top_margin_norm = 0.05
                bottom_margin_norm = 0.05
                total_usable_height_norm = 1.0 - top_margin_norm - bottom_margin_norm
                puzzle_height_norm = total_usable_height_norm / puzzles_per_page
                for i, generated_puzzle in enumerate(puzzles_on_this_page):
                    y_origin_for_puzzle = 1.0 - top_margin_norm - (i + 1) * puzzle_height_norm
                    if generated_puzzle.puzzle_type == "logic_grid":
                        self.logic_puzzle_generator.draw_puzzle(ax, generated_puzzle, y_origin_for_puzzle, puzzle_height_norm)
                    elif generated_puzzle.puzzle_type.startswith("sudoku"):
                        self._draw_sudoku_puzzle(ax, generated_puzzle, y_origin_for_puzzle, puzzle_height_norm)
                ax.set_aspect('auto')
                fig.tight_layout(rect=[0.05, 0.05, 0.95, 0.95])
                fig.text(0.5, 0.02, f"Página {page_idx + 1} de {num_pages}", ha='center', fontsize=9, color='gray')
                pdf.savefig(fig)
                plt.close(fig)
            self._draw_solution_pages(pdf, all_generated_puzzles, puzzles_per_page)
        print(f"PDF gerado em '{output_path}' com {num_total_puzzles} puzzles em {num_pages} páginas de atividades + páginas de solução.")

    def _draw_title_page(self, pdf, book_title: str, book_subtitle: str):
        fig, ax = plt.subplots(figsize=(PAGESIZE_WIDTH_INCHES, PAGESIZE_HEIGHT_INCHES))
        ax.axis("off")
        title_fontsize = 36
        subtitle_fontsize = 24
        author_fontsize = 18
        ax.text(0.5, 0.7, book_title, fontsize=title_fontsize, weight='bold', ha='center', va='center', wrap=True)
        ax.text(0.5, 0.55, book_subtitle, fontsize=subtitle_fontsize, style='italic', ha='center', va='center', wrap=True)
        ax.text(0.5, 0.2, "Desenvolvido por Adapta", fontsize=author_fontsize, ha='center', va='center', color='gray')
        pdf.savefig(fig)
        plt.close(fig)

    def _draw_sudoku_puzzle(self, ax, generated_puzzle: GeneratedPuzzle, y_origin_norm: float, puzzle_height_norm: float):
        title = generated_puzzle.display_info["title"]
        instructions = generated_puzzle.display_info["instructions"]
        grid_data = generated_puzzle.content
        title_fontsize = 14
        instructions_fontsize = 12
        grid_content_fontsize = 18
        grid_label_fontsize = 10
        ax.text(0.05, y_origin_norm + puzzle_height_norm * 0.95, title, fontsize=title_fontsize, weight="bold", transform=ax.transAxes, ha='left', va='top')
        ax.text(0.05, y_origin_norm + puzzle_height_norm * 0.88, instructions, fontsize=instructions_fontsize, transform=ax.transAxes, ha='left', va='top', wrap=True)
        grid_y_start = y_origin_norm + puzzle_height_norm * 0.3
        grid_height = puzzle_height_norm * 0.55
        ax.add_patch(plt.Rectangle((0.1, grid_y_start), 0.8, grid_height, fill=False, edgecolor='black', lw=1.5, transform=ax.transAxes))
        if grid_data and len(grid_data) > 0:
            ax.text(0.5, grid_y_start + grid_height / 2, f"{grid_data[0][0]} {grid_data[-1][-1]}", fontsize=grid_content_fontsize, ha='center', va='center', transform=ax.transAxes, weight='bold')
        else:
            ax.text(0.5, grid_y_start + grid_height / 2, "Sudoku Grid Placeholder", fontsize=grid_label_fontsize, ha='center', va='center', transform=ax.transAxes)

    def _draw_solution_pages(self, pdf, all_generated_puzzles: List[GeneratedPuzzle], puzzles_per_page: int):
        solutions_per_page = puzzles_per_page
        solutions_by_type = {}
        for p in all_generated_puzzles:
            if p.solution is not None:
                solutions_by_type.setdefault(p.puzzle_type, []).append(p)
        solution_counter = 0
        current_fig, current_ax = None, None
        current_y_offset = 1.0
        for puzzle_type, puzzles_of_type in solutions_by_type.items():
            for p in puzzles_of_type:
                if solution_counter % solutions_per_page == 0:
                    if current_fig:
                        current_fig.text(0.5, 0.02, f"Página Soluções {pdf.get_pagecount()}", ha='center', fontsize=9, color='gray')
                        pdf.savefig(current_fig)
                        plt.close(current_fig)
                    current_fig, current_ax = plt.subplots(figsize=(PAGESIZE_WIDTH_INCHES, PAGESIZE_HEIGHT_INCHES))
                    current_ax.axis("off")
                    current_y_offset = 0.95
                puzzle_height_for_solution = (1.0 - 0.1) / solutions_per_page
                current_ax.text(0.05, current_y_offset, f"Solução: {p.display_info['title']}", fontsize=12, weight='bold', transform=current_ax.transAxes, ha='left', va='top')
                current_y_offset -= 0.02
                if p.puzzle_type.startswith("sudoku"):
                    current_ax.text(0.08, current_y_offset - 0.01, f"Grid Solucionado: {p.solution[0][0]} {p.solution[1][-1]}", fontsize=10, transform=current_ax.transAxes, ha='left', va='top')
                elif p.puzzle_type == "logic_grid":
                    solution_str = "\n".join([", ".join(row) for row in p.solution])
                    current_ax.text(0.08, current_y_offset - 0.01, f"Matriz de Solução:\n{solution_str}", fontsize=10, transform=current_ax.transAxes, ha='left', va='top')
                current_y_offset -= puzzle_height_for_solution / 2
                solution_counter += 1
        if current_fig:
            current_fig.text(0.5, 0.02, f"Página Soluções {pdf.get_pagecount()}", ha='center', fontsize=9, color='gray')
            pdf.savefig(current_fig)
            plt.close(current_fig)

if __name__ == "__main__":
    book_series_configurations = [
        {
            "volume": 1,
            "book_title_template": "Large-Print Sudoku, Logic Puzzles & Brain Teasers – {total_puzzles} Puzzles ({easy_sudoku} Easy Sudoku, {hard_sudoku} Hard Sudoku, {logic_grid} Logic Grid) with Solutions – Volume {volume_number}",
            "book_subtitle_template": "Desafie sua mente com {total_puzzles} atividades variadas de Sudoku e lógica em formato grande, com soluções inclusas. Ideal para adultos e terceira idade.",
            "puzzle_specs": [
                {"type": "sudoku_easy", "count": 50},
                {"type": "sudoku_hard", "count": 50},
                {"type": "logic_grid", "count": 50},
            ],
            "puzzles_per_page": 2,
            "output_filename": "LargePrintPuzzles_Volume1.pdf"
        },
        {
            "volume": 2,
            "book_title_template": "Large-Print Sudoku, Logic Puzzles & Brain Teasers – {total_puzzles} Puzzles ({easy_sudoku} Easy Sudoku, {hard_sudoku} Hard Sudoku, {logic_grid} Logic Grid) with Solutions – Volume {volume_number}",
            "book_subtitle_template": "Continue a desafiar sua mente com {total_puzzles} atividades novas de Sudoku e lógica em formato grande, com soluções inclusas. Perfeito para aprimorar o raciocínio!",
            "puzzle_specs": [
                {"type": "sudoku_easy", "count": 40},
                {"type": "sudoku_hard", "count": 60},
                {"type": "logic_grid", "count": 50},
            ],
            "puzzles_per_page": 2,
            "output_filename": "LargePrintPuzzles_Volume2.pdf"
        },
        {
            "volume": 3,
            "book_title_template": "Large-Print Ultimate Brain Challenge – {total_puzzles} Puzzles ({easy_sudoku} Easy Sudoku, {hard_sudoku} Hard Sudoku, {logic_grid} Logic Grid) with Solutions – Volume {volume_number}",
            "book_subtitle_template": "O desafio definitivo para a mente! {total_puzzles} puzzles em formato extra grande para todas as idades, com soluções completas.",
            "puzzle_specs": [
                {"type": "sudoku_easy", "count": 30},
                {"type": "sudoku_hard", "count": 70},
                {"type": "logic_grid", "count": 50},
            ],
            "puzzles_per_page": 1,
            "output_filename": "LargePrintPuzzles_Volume3.pdf"
        },
    ]
    for book_config in book_series_configurations:
        try:
            total_puzzles = sum(spec["count"] for spec in book_config["puzzle_specs"])
            easy_sudoku_count = next((s["count"] for s in book_config["puzzle_specs"] if s["type"] == "sudoku_easy"), 0)
            hard_sudoku_count = next((s["count"] for s in book_config["puzzle_specs"] if s["type"] == "sudoku_hard"), 0)
            logic_grid_count = next((s["count"] for s in book_config["puzzle_specs"] if s["type"] == "logic_grid"), 0)
            formatted_title = book_config["book_title_template"].format(total_puzzles=total_puzzles, easy_sudoku=easy_sudoku_count, hard_sudoku=hard_sudoku_count, logic_grid=logic_grid_count, volume_number=book_config["volume"])
            formatted_subtitle = book_config["book_subtitle_template"].format(total_puzzles=total_puzzles)
            print(f"\nIniciando a geração do livro: '{formatted_title}'...")
            logic_puzzle_gen = LogicPuzzleGenerator(puzzle_size=PUZZLE_SIZE)
            sudoku_easy_gen = SudokuGenerator("easy")
            sudoku_hard_gen = SudokuGenerator("hard")
            book_gen = PuzzleBookGenerator(logic_puzzle_generator=logic_puzzle_gen, sudoku_easy_generator=sudoku_easy_gen, sudoku_hard_generator=sudoku_hard_gen)
            book_gen.generate_book(book_title=formatted_title, book_subtitle=formatted_subtitle, puzzle_specs=book_config["puzzle_specs"], puzzles_per_page=book_config["puzzles_per_page"], output_path=book_config["output_filename"])
        except ValueError as e:
            print(f"Erro de configuração ou validação para o Volume {book_config['volume']}: {e}")
        except Exception as e:
            print(f"Ocorreu um erro inesperado durante a geração do Volume {book_config['volume']}: {e}")
