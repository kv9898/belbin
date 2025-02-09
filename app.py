from shiny import App, ui, reactive, render
from pathlib import Path

question

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
    ui.input_action_button("start","开始问卷")
    )

app_ui = ui.page_fluid(
    ui.head_content(ui.include_js("app_py.js")),
    ui.navset_tab(
        welcome_panel,
        id="tab"
    )
)

def server(input, output, session):
    pass

app = App(app_ui, server, static_assets=Path(__file__).parent / "www")