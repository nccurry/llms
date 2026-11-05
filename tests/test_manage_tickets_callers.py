"""manage-tickets owns the ticket workflow. Each of its five callers names
it in one conditional sentence, plc-checkpoint only reads ticket state, and
no other skill restates the workflow."""

import re
import unittest
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[1] / "skills"
CALLERS = ["plc-planning", "plc-feature-start", "create-mr-description", "plc-mr-review", "plc-wrapup"]
SENTENCE = "When this work has a ticket or the project uses tickets, run"


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
                self.assertTrue(naming[0].startswith(SENTENCE), naming[0])

    def test_checkpoint_only_reads_tickets(self):
        body = text("plc-checkpoint")
        self.assertNotIn("manage-tickets", body)
        ticket_lines = [s for s in sentences("plc-checkpoint") if re.search(r"\btickets?\b", s, re.I)]
        self.assertTrue(ticket_lines, "plc-checkpoint reads ticket state in step 3")
        step3 = body.split("## 3. Gather what changed", 1)[1].split("## 4.", 1)[0]
        self.assertRegex(step3, r"(?i)\btickets?\b")
        writes = re.compile(r"(?i)\b(create|close|transition|move|comment on|update)s?\b[^.]*\btickets?\b")
        for line in ticket_lines:
            if "don't change" in line.lower() or "do not change" in line.lower():
                continue
            self.assertNotRegex(line, writes)

    def test_no_other_skill_names_manage_tickets(self):
        allowed = set(CALLERS) | {"manage-tickets"}
        for skill_md in sorted(SKILLS.glob("*/SKILL.md")):
            skill = skill_md.parent.name
            if skill not in allowed:
                with self.subTest(skill=skill):
                    self.assertNotIn("manage-tickets", skill_md.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
