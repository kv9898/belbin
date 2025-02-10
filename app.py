from shiny import App, ui, reactive, render
from shiny.ui._navs import NavPanel
from pathlib import Path
from typing import Optional
from collections.abc import Callable
from string import ascii_letters
import json, re
import polars as pl

# Read questionnaire
# file_path = Path(__file__).parent / "www" / "questionnaire.json"
file_path = "www/questionnaire.json"
with open(file_path, encoding="utf-8") as file:
    questionnaire: dict[str] = json.load(file)

# Sanity check and answer dictionary creation
answers: dict[dict[str]] = {}
for index, question in enumerate(questionnaire):
    if question != f"Q{index + 1}":
        raise ValueError("Question number mismatch")
    choices = list(questionnaire[question].keys())
    if choices.pop(0) != "q":
        raise ValueError("Question text not found")
    else:
        UPPERCASES = list(ascii_letters[26:])
        if choices != UPPERCASES[: len(choices)]:
            raise ValueError("Choices key mismatch")
    answers[f"{index + 1}"] = {choice.lower(): 0 for choice in choices}


# normalise answers to sum to 100
def normalise_answers() -> None:
    for question in answers:
        total = sum(answers[question].values())
        if total == 0:
            continue
        for choice in answers[question]:
            answers[question][choice] = answers[question][choice] / total * 10


# Role score initialisation
file_path = "www/roles.json"
with open(file_path, encoding="utf-8") as file:
    role_scores_table: dict[str] = json.load(file)
role_scores: dict[float] = {role: 0 for role in role_scores_table.keys()}


# Role score calculation
def role_score_calculate() -> None:
    for role in role_scores:
        score = 0
        for q in range(1, len(answers) + 1):
            choice = role_scores_table[role][str(q)].lower()
            score += answers[str(q)][choice]
        role_scores[role] = score


# Final score calculation
final_score_table: pl.DataFrame = pl.read_csv("www/final.csv", separator=",")


def final_score_calculator(role: str, raw_score: float) -> int:
    if role not in final_score_table.columns:
        raise ValueError(f"Role {role} not found in final score table")

    role_data = final_score_table[["raw", role]]

    # return if raw score is in the table
    if raw_score in role_data["raw"]:
        processed_score: pl.Series = role_data.filter(
            pl.col("raw") == raw_score
        ).get_column(role)
        if len(processed_score) != 1:
            raise ValueError(
                f"Multiple final scores found for raw score {raw_score} and role {role}"
            )
        processed_score: int = processed_score[0]
        if not isinstance(processed_score, int) or processed_score < 0:
            raise ValueError(
                f"Invalid final score {processed_score} found for raw score {raw_score} and role {role}"
            )
        return processed_score

    # deal with out of range raw score
    if raw_score >= role_data[0, 0]:
        return role_data[0, 1]
    elif raw_score <= role_data[-1, 0]:
        return role_data[-1, 1]

    # find interval for decimal raw score
    for i in range(role_data.height - 1):
        x_high, y_high = role_data[i].rows()[0]
        x_low, y_low = role_data[i + 1].rows()[0]
        if x_high >= raw_score >= x_low:
            break

    # 计算插值
    slope = (y_low - y_high) / (x_low - x_high)
    processed_score = y_high + slope * (raw_score - x_high)
    return int(processed_score)


def calculate_final_score() -> None:
    for role in role_scores:
        raw_score = role_scores[role]
        final_score = final_score_calculator(role, raw_score)
        role_scores[role] = final_score


# Result table production
file_path = "www/role_names.json"
with open(file_path, encoding="utf-8") as file:
    role_names: dict[str] = json.load(file)
if role_names.keys() != role_scores.keys():
    raise ValueError("Role names and scores do not match")

results_df: pl.DataFrame = pl.DataFrame()
styles = []  # for highlighting results


def produce_results() -> None:
    global results_df
    global styles
    results_df = pl.DataFrame(
        {
            "角色": [f"{role_names[role]} ({role})" for role in role_scores.keys()],
            "分数": [role_scores[role] for role in role_scores.keys()],
        }
    )

    def role_level(score: int) -> str:
        if score >= 70:
            return "自然角色"
        elif score >= 30:
            return "次要角色"
        else:
            return "避免角色"

    results_df = results_df.with_columns(
        pl.col("分数").map_elements(role_level, return_dtype=str).alias("角色等级")
    )

    # calculate styles
    styles = []
    natural_roles = [i for i, x in enumerate(results_df["角色等级"] == "自然角色") if x]
    if len(natural_roles) > 0:
        styles.append(
            {
                "rows": natural_roles,
                "style": {"font-weight": "bold", "background-color": "#bfffaf"},
            }
        )
    avoided_roles = [i for i, x in enumerate(results_df["角色等级"] == "避免角色") if x]
    if len(avoided_roles) > 0:
        styles.append(
            {
                "rows": avoided_roles,
                "style": {"background-color": "#ffbaaf"},
            }
        )

produce_results()


# Check for last choice of the last question
def last_choice(question: int, choice: str) -> bool:
    try:
        questions = list(questionnaire.keys())
        if f"Q{question}" != questions[-1]:
            return False
        choices = list(questionnaire[f"Q{question}"].keys())
        if choice.upper() != choices[-1]:
            return False
        return True
    except (ValueError, IndexError):
        return False


# Produce welcome panel
welcome_panel = ui.nav_panel(
    "欢迎",
    ui.strong("贝尔宾团队角色自我认知问卷"),
    ui.br(),
    ui.br(),
    """贝尔宾自评文件是一份以行为为基础导向的测评问卷。请用15-20分钟时间完成该问卷。请注意：这里没有好坏之分，
    尝试以你目前的实际情况回答，而不是你未来想成为的状态来回答问题。请仔细回答，但不要过度分析自己。
    """,
    ui.br(),
    ui.br(),
    ui.input_action_button("start_button", "开始问卷"),
)


# Produce choice panel
def get_choice_panel(question: int, choice: str) -> NavPanel:
    choice = choice.lower()
    # check inputs
    try:
        choice_txt = questionnaire[f"Q{question}"][choice.upper()]
    except:
        if f"Q{question}" not in questionnaire:
            raise ValueError("Question out of bound")
        else:
            raise ValueError("Choice out of bound")
    # determine button text
    button_text = "下一题" if not last_choice(question, choice) else "完成问卷"
    # find panel
    choice_panel = ui.nav_panel(
        choice.upper(),
        choice_txt,
        ui.input_slider(f"q{question}{choice}", "", 0, 10, 0),
        ui.input_action_button(f"next{question}{choice}", button_text),
    )
    return choice_panel


# Produce question panel
def get_question_panel(question: int) -> NavPanel:
    # get question dictionary
    try:
        question_dict = questionnaire[f"Q{question}"]
    except:
        raise ValueError("Question out of bound")
    # get question text
    try:
        question_txt = question_dict["q"]
    except:
        raise ValueError("Question text is not found")
    # get list of choice panels
    choice_panels: list[NavPanel] = []
    for choice in question_dict:
        if choice == "q":
            continue
        choice_panels.append(get_choice_panel(question, choice))
    question_panel = ui.nav_panel(
        str(question), question_txt, ui.navset_tab(*choice_panels, id=f"q{question}")
    )
    return question_panel


# get question panels
question_panels: list[NavPanel] = []
for question in questionnaire:
    try:
        match = int(re.match(r"^Q(\d+)$", question).group(1))
    except:
        raise ValueError("Invalid question found")
    question_panels.append(get_question_panel(int(match)))

# create results panel
results_panel = ui.nav_panel(
    "结果",
    ui.strong("您的贝尔宾团队角色自我认知问卷最终结果："),
    ui.br(),
    ui.br(),
    ui.output_data_frame("results"),
    ui.br(),
    ui.input_action_button("back_to_questions", "返回问卷"),
)

# compile ui
app_ui = ui.page_fluid(
    ui.head_content(ui.include_js("app_py.js")),
    ui.navset_hidden(
        ui.nav_panel(
            "main_tab",
            ui.navset_tab(
                    welcome_panel, 
                    *question_panels, 
                    id="main_tab"
            )
        ),
    results_panel,
    id="results_display"
    )
)


def server(input, output, session):

    results_df_reac =  reactive.value(results_df) # for reactive results handling

    def next_tab(question: Optional[int] = None, choice: Optional[str] = None):
        next_q: int = 1
        next_c: str = "A"
        if last_choice(question, choice):
            return
        if question is None:
            pass
        else:
            choice = choice.lower()
            try:
                # check if the current choice is the last one
                choices = list(questionnaire[f"Q{question}"].keys())
                if choice.upper() == choices[-1]:
                    next_q = question + 1
                    next_c = "A"
                else:
                    next_q = question
                    next_c = chr(ord(choice.upper()) + 1)
            except (ValueError, IndexError):
                next_q: int = 1
                next_c: str = "A"
        ui.update_navs(id="main_tab", selected=str(next_q))
        ui.update_navs(id=f"q{next_q}", selected=next_c)

    # Button processors
    @reactive.effect
    @reactive.event(input.start_button)
    async def start_button():
        next_tab()
        collect_answers()

    @reactive.effect
    @reactive.event(input.back_to_questions)
    async def back_to_questions_button():
        ui.update_navs(id="results_display", selected="main_tab")

    def create_button_processor(question: int, choice: str) -> Callable:
        choice = choice.lower()
        input_event = getattr(input, f"next{question}{choice}")

        @reactive.effect
        @reactive.event(input_event)
        def button_processor():
            next_tab(question, choice)
            collect_answers()

        return button_processor

    def submit_button_processor(question: int, choice: str) -> Callable:
        choice = choice.lower()
        input_event = getattr(input, f"next{question}{choice}")
        @reactive.effect
        @reactive.event(input_event)
        def button_processor():
            collect_answers()
            normalise_answers()
            role_score_calculate()
            calculate_final_score()
            produce_results()
            results_df_reac.set(results_df)
            ui.update_navs(id="results_display", selected="结果")

        return button_processor

    for question in questionnaire:
        for choice in questionnaire[question]:
            q = int(re.match(r"^Q(\d+)$", question).group(1))
            c = choice.lower()
            if choice == "q":
                continue
            if last_choice(q, c):
                globals()[f"button{q}{c}"] = submit_button_processor(q, c)
            globals()[f"button{q}{c}"] = create_button_processor(q, c)

    # collect slider answers
    def collect_answers():
        for question in questionnaire:
            for choice in questionnaire[question]:
                q = int(re.match(r"^Q(\d+)$", question).group(1))
                c = choice.lower()
                if choice == "q":
                    continue
                slider_input = getattr(input, f"q{q}{c}")
                answers[f"{q}"][c] = slider_input()

    # display results
    @render.data_frame
    def results():
        return render.DataGrid(
            results_df_reac(), styles=styles
        )


app = App(app_ui, server, static_assets=Path(__file__).parent / "www", debug=True)
