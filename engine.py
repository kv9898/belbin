import json
import polars as pl
from string import ascii_letters

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