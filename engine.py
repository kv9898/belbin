import json
from string import ascii_letters

# Read questionnaire
# file_path = Path(__file__).parent / "www" / "questionnaire.json"
file_path = "www/questionnaire.json"
with open(file_path, encoding="utf-8") as file:
    questionnaire: dict[str] = json.load(file)

# Sanity check and answer dictionary creation
answers: dict[dict[str]] = {}
for index, question in enumerate(questionnaire):
    print("test")
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