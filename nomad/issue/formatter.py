"""Format issue content for submission.

Composes structured issue bodies from user input and auto-collected
system information. Handles all three categories (bug, feature,
question) with appropriate templates.
"""

from __future__ import annotations

from typing import Optional

from .collector import SystemInfo


# Components dropdown list (shared across CLI, dashboard, Console)
COMPONENTS = [
    "collectors",
    "alerts",
    "dashboard",
    "tessera",
    "cli",
    "console",
    "dynamics",
    "insights",
    "reference",
    "other",
]

CATEGORIES = ["bug", "feature", "question"]


class IssueFormatter:
    """Compose issue bodies from structured input."""

    def __init__(self, system_info: SystemInfo | None = None):
        self.system_info = system_info

    def format_bug(
        self,
        title: str,
        component: str,
        description: str,
        steps: str,
        expected: str,
        actual: str,
    ) -> str:
        """Format a bug report body."""
        sections = [
            f"**Component:** {component}",
            "",
            "### Description",
            description,
            "",
            "### Steps to Reproduce",
            steps,
            "",
            "### Expected Behavior",
            expected,
            "",
            "### Actual Behavior",
            actual,
        ]

        if self.system_info:
            sections.extend(["", self.system_info.to_markdown()])

        return "\n".join(sections)

    def format_feature(
        self,
        title: str,
        component: str,
        problem: str,
        solution: str = "",
        alternatives: str = "",
    ) -> str:
        """Format a feature request body."""
        sections = [
            f"**Component:** {component}",
            "",
            "### Problem Statement",
            problem,
        ]

        if solution:
            sections.extend(["", "### Proposed Solution", solution])

        if alternatives:
            sections.extend(
                ["", "### Alternatives Considered", alternatives]
            )

        if self.system_info:
            sections.extend(["", self.system_info.to_markdown()])

        return "\n".join(sections)

    def format_question(
        self,
        title: str,
        topic: str,
        question: str,
        tried: str = "",
    ) -> str:
        """Format a question body."""
        sections = [
            f"**Topic:** {topic}",
            "",
            "### Question",
            question,
        ]

        if tried:
            sections.extend(
                ["", "### What I've Already Tried", tried]
            )

        if self.system_info:
            sections.extend(["", self.system_info.to_markdown()])

        return "\n".join(sections)

    def format_from_dict(self, data: dict) -> tuple[str, str]:
        """Format issue from a dictionary (used by dashboard/Console API).

        Returns (title, body) tuple.
        """
        category = data.get("category", "bug")
        title = data.get("title", "")
        component = data.get("component", "other")

        if category == "bug":
            body = self.format_bug(
                title=title,
                component=component,
                description=data.get("description", ""),
                steps=data.get("steps", ""),
                expected=data.get("expected", ""),
                actual=data.get("actual", ""),
            )
        elif category == "feature":
            body = self.format_feature(
                title=title,
                component=component,
                problem=data.get("problem", data.get("description", "")),
                solution=data.get("solution", ""),
                alternatives=data.get("alternatives", ""),
            )
        elif category == "question":
            body = self.format_question(
                title=title,
                topic=component,
                question=data.get("question", data.get("description", "")),
                tried=data.get("tried", ""),
            )
        else:
            body = data.get("description", "")
            if self.system_info:
                body += "\n\n" + self.system_info.to_markdown()

        # Prefix title with category tag
        prefix_map = {
            "bug": "[Bug]",
            "feature": "[Feature]",
            "question": "[Question]",
        }
        prefix = prefix_map.get(category, "")
        if prefix and not title.startswith(prefix):
            title = f"{prefix} {title}"

        return title, body
