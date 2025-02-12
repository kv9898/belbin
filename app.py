from shiny import App, ui, reactive, render
from shiny.ui._navs import NavPanel
from pathlib import Path
from typing import Optional
from collections.abc import Callable
import re

from engine import questionnaire, answers, normalise_answers, role_score_calculate, calculate_final_score, get_results, get_styles, produce_results

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
    prev_text = "上一题" if not (question == 1 and choice == "a") else "返回欢迎页"
    next_text = "下一题" if not last_choice(question, choice) else "完成问卷"
    # find panel
    choice_panel = ui.nav_panel(
        choice.upper(),
        choice_txt,
        ui.input_slider(f"q{question}{choice}", "", 0, 10, 0),
        ui.input_action_button(f"prev{question}{choice}", prev_text),
        ui.input_action_button(f"next{question}{choice}", next_text),
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

    results_df_reac =  reactive.value(get_results()) # for reactive results handling

    def prev_tab(question: int, choice: str):
        choice = choice.lower()
        if question == 1 and choice == "a":
            ui.update_navs(id="main_tab", selected="欢迎")
            return
        if choice!="a":
            ui.update_navs(id=f"q{question}", selected=chr(ord(choice.upper()) - 1))
            return
        else:
            ui.update_navs(id="main_tab", selected=str(question-1)) # go to previous question
            last_choice = list(questionnaire[f"Q{question-1}"].keys())[-1].upper() # get the last choice of previous question
            ui.update_navs(id=f"q{question-1}", selected=last_choice)
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

    def create_prev_processor(question: int, choice: str) -> Callable:
        choice = choice.lower()
        input_event = getattr(input, f"prev{question}{choice}")

        @reactive.effect
        @reactive.event(input_event)
        def prev_processor():
            prev_tab(question, choice)
            collect_answers()

        return prev_processor

    def create_next_processor(question: int, choice: str) -> Callable:
        choice = choice.lower()
        input_event = getattr(input, f"next{question}{choice}")

        @reactive.effect
        @reactive.event(input_event)
        def next_processor():
            next_tab(question, choice)
            collect_answers()

        return next_processor

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
            results_df_reac.set(get_results())
            ui.update_navs(id="results_display", selected="结果")

        return button_processor

    for question in questionnaire:
        for choice in questionnaire[question]:
            q = int(re.match(r"^Q(\d+)$", question).group(1))
            c = choice.lower()
            if choice == "q":
                continue
            if last_choice(q, c):
                globals()[f"prev{q}{c}"] = create_prev_processor(q, c)
                globals()[f"next{q}{c}"] = submit_button_processor(q, c)
                continue
            globals()[f"prev{q}{c}"] = create_prev_processor(q, c)
            globals()[f"next{q}{c}"] = create_next_processor(q, c)

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
            results_df_reac(), styles=get_styles()
        )


app = App(app_ui, server, static_assets=Path(__file__).parent / "www")
