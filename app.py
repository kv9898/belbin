from shiny import App, ui, reactive, render
from shiny.ui._navs import NavPanel
from pathlib import Path
from typing import Optional
from collections.abc import Callable
from string import ascii_letters
import json, re

# Read questionnaire
# file_path = Path(__file__).parent / "www" / "questionnaire.json"
file_path = "www/questionnaire.json"
with open(file_path, encoding="utf-8") as file:
    questionnaire: dict[str] = json.load(file)

# Sanity check
for index, question in enumerate(questionnaire):
    if question != f"Q{index + 1}":
        raise ValueError("Question number mismatch")
    choices = list(questionnaire[question].keys())
    if choices.pop(0) != "q":
        raise ValueError("Question text not found")
    else:
        UPPERCASES = list(ascii_letters[26:])
        if choices != UPPERCASES[:len(choices)]:
            raise ValueError("Choices key mismatch")

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
    ui.input_action_button("start_button","开始问卷")
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
        ui.input_action_button(f"next{question}{choice}", button_text)
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
        str(question),
        question_txt,
        ui.navset_tab(
        *choice_panels,
        id=f"q{question}"
        )
    )
    return question_panel

# get question panels
question_panels: list[NavPanel] = []
for question in questionnaire:
    try:
        match = int(re.match(r'^Q(\d+)$', question).group(1))
    except:
        raise ValueError("Invalid question found")
    question_panels.append(get_question_panel(int(match)))

print(len(question_panels))

app_ui = ui.page_fluid(
    ui.head_content(ui.include_js("app_py.js")),
    ui.navset_tab(
        welcome_panel,
        *question_panels,
        id="main_tab"
    )
)

def server(input, output, session):
    
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

    @reactive.effect
    @reactive.event(getattr(input, "start_button"))
    async def start_button():
        next_tab()

    def create_button_processor(question: int, choice: str) -> Callable:
        choice = choice.lower()
        input_event = getattr(input, f"next{question}{choice}")
        @reactive.effect
        @reactive.event(input_event)
        def button_processor():
            next_tab(question, choice)
        return button_processor
    
    for question in questionnaire:
        for choice in questionnaire[question]:
            q = int(re.match(r'^Q(\d+)$', question).group(1))
            c = choice.lower()
            if choice == "q":
                continue
            if last_choice(q, c):
                continue
            globals()[f"button{q}{c}"] = create_button_processor(q, c)
            print(f"button{q}{c}")

app = App(app_ui, server, static_assets=Path(__file__).parent / "www", debug=True)