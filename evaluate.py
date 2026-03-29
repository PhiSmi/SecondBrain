"""Evaluation framework — measure retrieval quality against ground-truth Q&A pairs."""

import db
import query


def run_evaluation(workspace: str | None = None, hybrid: bool = True,
                   use_rerank: bool = False) -> list[dict]:
    """Run all eval pairs and return scored results.

    For each Q&A pair:
    1. Retrieve chunks using the same pipeline as the Ask tab
    2. Generate an answer
    3. Score the answer against the expected answer using Claude

    Returns a list of dicts with: question, expected, actual, score, reasoning, sources.
    """
    pairs = db.get_eval_pairs(workspace=workspace)
    if not pairs:
        return []

    results = []
    for pair in pairs:
        result = query.ask(
            pair["question"],
            tags=pair.get("tags") or None,
            hybrid=hybrid,
            use_rerank=use_rerank,
            workspace=workspace,
        )

        # Score the answer
        score_result = _score_answer(pair["question"], pair["expected_answer"], result["answer"])
        results.append({
            "question": pair["question"],
            "expected": pair["expected_answer"],
            "actual": result["answer"],
            "score": score_result["score"],
            "reasoning": score_result["reasoning"],
            "sources_used": len(result.get("sources", [])),
        })

    return results


EVAL_PROMPT = """You are an evaluation judge. Compare the actual answer against the expected answer for the given question.

Score from 1-5:
1 = Completely wrong or irrelevant
2 = Partially relevant but misses key points
3 = Covers some key points but incomplete
4 = Good answer, covers most key points
5 = Excellent, covers all key points accurately

Respond in EXACTLY this format (two lines only):
SCORE: <number>
REASONING: <one sentence explanation>"""


def _score_answer(question: str, expected: str, actual: str) -> dict:
    """Use Claude to score an answer against the expected answer."""
    client = query._get_anthropic()
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=150,
        system=EVAL_PROMPT,
        messages=[{
            "role": "user",
            "content": f"Question: {question}\n\nExpected answer: {expected}\n\nActual answer: {actual}",
        }],
    )
    text = response.content[0].text.strip()
    query._track_api_usage(response.usage, "claude-haiku-4-5-20251001", "evaluation")

    # Parse score
    score = 3  # default
    reasoning = text
    for line in text.split("\n"):
        if line.startswith("SCORE:"):
            try:
                score = int(line.split(":")[1].strip())
            except ValueError:
                pass
        elif line.startswith("REASONING:"):
            reasoning = line.split(":", 1)[1].strip()

    return {"score": min(max(score, 1), 5), "reasoning": reasoning}


def compute_summary(results: list[dict]) -> dict:
    """Compute aggregate stats from evaluation results."""
    if not results:
        return {"count": 0, "avg_score": 0, "min_score": 0, "max_score": 0,
                "score_distribution": {}}
    scores = [r["score"] for r in results]
    dist = {}
    for s in range(1, 6):
        dist[s] = sum(1 for x in scores if x == s)
    return {
        "count": len(results),
        "avg_score": round(sum(scores) / len(scores), 2),
        "min_score": min(scores),
        "max_score": max(scores),
        "score_distribution": dist,
    }
