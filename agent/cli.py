import argparse
import os
import sys
from agent.orchestrator import run
from agent.llm_client import GroqClient


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent")
    sub = parser.add_subparsers(dest="cmd", required=True)

    ask = sub.add_parser("ask", help="ask the agent a question about a CSV")
    ask.add_argument("question", type=str)
    ask.add_argument("--data", required=True, help="path to CSV file")
    ask.add_argument("--model", default="llama-3.3-70b-versatile")
    ask.add_argument("--no-retry", action="store_true",
                     help="disable error retry (for ablation runs)")

    args = parser.parse_args(argv)

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("error: set GROQ_API_KEY", file=sys.stderr)
        return 2

    llm = GroqClient(api_key=api_key, model=args.model)
    result = run(args.question, args.data, llm, retry_on_failure=not args.no_retry)

    if result.success:
        print(result.answer)
        return 0
    print(f"agent failed: {result.failure_reason}", file=sys.stderr)
    return 1
