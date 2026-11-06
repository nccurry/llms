"""manage-tickets owns the ticket workflow. Each of its five callers names
it in one conditional sentence, plc-checkpoint only reads ticket state, and
no other skill restates the workflow."""

import re
import unittest
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[1] / "skills"
CALLERS = [
    "plc-planning",
    "plc-feature-start",
    "create-mr-description",
    "plc-mr-review",
    "plc-wrapup",
]
CONDITION = re.compile(r"(?i)\bhas a ticket or the project uses tickets\b")
RUNS_IT = re.compile(r"\brun (?:\[manage-tickets\]\(|`manage-tickets`)")
# Wording that tells the reader not to change tickets, which is allowed.
NOT_CHANGING = re.compile(
    r"(?i)\b(?:don't|do not|never) (?:change|write to|update) (?:the )?tickets?\b"
)
WRITES = re.compile(
    r"(?i)\b(?:create|close|transition|move|comment on|update|change|write to)s?\b[^.]*\btickets?\b"
)


def text(skill: str) -> str:
    return (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")


def sentences(skill: str) -> list[str]:
    """The skill's sentences: each paragraph, list item or heading split at
    sentence ends, with line breaks joined."""
    blocks = re.split(r"\n\s*\n|\n(?=\s*(?:[-*]|\d+\.|#+)\s)", text(skill))
    found = []
    for block in blocks:
        flat = re.sub(r"\s+", " ", block).strip()
        flat = re.sub(r"^(?:[-*]|\d+\.|#+)\s+", "", flat)
        found += [s for s in re.split(r"(?<=[.!?])\s+(?=[A-Z`\[*])", flat) if s]
    return found


class ManageTicketsCallersTest(unittest.TestCase):
    def test_each_caller_has_one_conditional_sentence(self):
        for skill in CALLERS:
            with self.subTest(skill=skill):
                naming = [s for s in sentences(skill) if "manage-tickets" in s]
                self.assertEqual(len(naming), 1, naming)
                self.assertRegex(naming[0], CONDITION)
                self.assertRegex(naming[0], RUNS_IT)

    def test_checkpoint_only_reads_tickets(self):
        body = text("plc-checkpoint")
        self.assertNotIn("manage-tickets", body)
        ticket_lines = [
            s for s in sentences("plc-checkpoint") if re.search(r"\btickets?\b", s, re.I)
        ]
        self.assertTrue(ticket_lines, "plc-checkpoint reads ticket state in step 3")
        step3 = re.split(r"(?m)^## 3\.", body, maxsplit=1)[1]
        step3 = re.split(r"(?m)^## ", step3, maxsplit=1)[0]
        self.assertRegex(step3, r"(?i)\btickets?\b")
        for line in ticket_lines:
            # A sentence may say not to change tickets, but nothing else in
            # it may tell the reader to write one.
            self.assertNotRegex(NOT_CHANGING.sub("", line), WRITES)

    def test_no_other_skill_names_manage_tickets(self):
        allowed = set(CALLERS) | {"manage-tickets"}
        for skill_md in sorted(SKILLS.glob("*/SKILL.md")):
            skill = skill_md.parent.name
            if skill not in allowed:
                with self.subTest(skill=skill):
                    self.assertNotIn("manage-tickets", skill_md.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
