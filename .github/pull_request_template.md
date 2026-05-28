## What changed
<!-- 1–2 lines summarizing the change -->

## Why
<!-- The problem / motivation. Link to a spec section or issue if relevant. -->

## How I verified
<!-- e.g. "pytest passes locally", "ran the agent CLI on iris.csv", "ran 80-task eval and ABQ went from X to Y". -->

## Notes for future me
<!-- Anything weird I want to remember: shortcuts taken, follow-ups, decisions. -->

## Pre-merge checklist
- [ ] All tests pass locally (`pytest -v`)
- [ ] If this changes the eval pipeline, I re-ran a subset and recorded the number
- [ ] If this touches the sandbox or LLM client, the new behavior is covered by a test
- [ ] No secrets or API keys committed
