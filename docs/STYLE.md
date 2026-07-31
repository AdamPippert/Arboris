# Documentation style

Arboris documentation follows
[AdamPippert/AgentStyleGuide](https://github.com/AdamPippert/AgentStyleGuide).
The standard derives from ASD-STE100 Simplified Technical English. It governs
human and AI authors equally.

## Governed documents

The standard governs: `README.md`, everything under `docs/` (including
`docs/adr/` and `docs/rfc/`), and the guides under `.claude/skills/`. It does
not govern code, commit messages, or conversational replies.

## Check a document before you commit

1. Get the linter:

   ```sh
   curl -sSLo /tmp/asg-lint.py \
     https://raw.githubusercontent.com/AdamPippert/AgentStyleGuide/main/tools/lint.py
   ```

2. Run it on the changed documents:

   ```sh
   python3 /tmp/asg-lint.py README.md docs/**/*.md
   ```

3. IF the linter reports findings,
   THEN fix them before you commit.
   A clean run covers only the countable rules.

4. Review the judgment rules in the standard's `CHECKLIST.md`. Key items:
   verified facts only, marked inference, named actors, front-loaded
   conclusions, one term per concept.

## Rules that most often need attention here

- Sentences: maximum 20 words (procedural) or 25 words (descriptive).
  Identifiers, paths, and URLs count as one word each.
- Paragraphs: maximum 6 sentences, one topic.
- Do not open a sentence with a bare demonstrative. Name the referent.
- Use active voice. Use passive voice only when the actor is unknown or
  irrelevant.
- State conditions before actions. State the negative branch.
