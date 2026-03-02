import re
from pathlib import Path

from sieve.compiler.templates import (
    COMPILE_GROUP_PROMPT,
    COMPILE_SINGLE_PROMPT,
    DESCRIPTION_PROMPT,
    SKILL_TEMPLATE,
)
from sieve.llm.client import LLMClient
from sieve.mcp.api_client import SieveAPIClient


def _slugify(text: str) -> str:
    """Convert text to a URL/filename-safe slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


class SkillCompiler:
    def __init__(self, api_url: str, api_key: str) -> None:
        self.api_client = SieveAPIClient(api_url=api_url, api_key=api_key)
        self.llm = LLMClient()

    def group_capsules(self, capsules: list[dict], by: str = "author") -> dict[str, list[dict]]:
        """Group capsules by a given field."""
        groups: dict[str, list[dict]] = {}
        for c in capsules:
            key = c.get(by) or "unknown"
            groups.setdefault(key, []).append(c)
        return groups

    async def _generate_description(self, title: str, summary: str) -> str:
        """Generate a Claude Code skill description starting with 'Use when'."""
        prompt = DESCRIPTION_PROMPT.format(title=title, summary=summary)
        response = await self.llm.client.chat.completions.create(
            model=self.llm.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        desc = (response.choices[0].message.content or "").strip().strip('"')
        if not desc.startswith("Use when"):
            desc = f"Use when working with {title.lower()}"
        return desc[:500]

    async def compile_single(self, capsule: dict) -> str:
        """Compile a single capsule into a skill body."""
        tags = ", ".join(capsule.get("tags", []))
        prompt = COMPILE_SINGLE_PROMPT.format(
            title=capsule.get("title", "Untitled"),
            tags=tags,
            core_insight=capsule.get("core_insight", ""),
            executive_summary=capsule.get("executive_summary", ""),
            full_content=capsule.get("full_content", "")[:4000],
        )
        response = await self.llm.client.chat.completions.create(
            model=self.llm.model,
            messages=[{"role": "user", "content": prompt}],
        )
        return (response.choices[0].message.content or "").strip()

    async def compile_group(self, author: str, capsules: list[dict]) -> str:
        """Compile a group of capsules into a single skill body."""
        capsules_text = ""
        for c in capsules:
            tags = ", ".join(c.get("tags", []))
            capsules_text += f"\n### {c['title']}\nTags: {tags}\n"
            capsules_text += f"Insight: {c.get('core_insight', '')}\n"
            capsules_text += f"Summary: {c.get('executive_summary', '')}\n"

        prompt = COMPILE_GROUP_PROMPT.format(author=author, capsules_text=capsules_text)
        response = await self.llm.client.chat.completions.create(
            model=self.llm.model,
            messages=[{"role": "user", "content": prompt}],
        )
        return (response.choices[0].message.content or "").strip()

    async def compile_to_skills(
        self,
        output_dir: Path,
        by: str = "capsule",
        all_capsules: bool = False,
    ) -> list[Path]:
        """Compile capsules into Claude Code skill files.

        Args:
            output_dir: Directory to write skill files to.
            by: Grouping strategy — 'capsule', 'category', 'author', or 'pack'.
            all_capsules: If True, include all capsules. Otherwise only skill_eligible.
        """
        data = await self.api_client.list_capsules(limit=200)
        capsules = data.get("capsules", [])

        if not all_capsules:
            capsules = [c for c in capsules if c.get("skill_eligible", True)]

        if not capsules:
            return []

        output_dir.mkdir(parents=True, exist_ok=True)
        written: list[Path] = []

        if by == "capsule":
            for c in capsules:
                title = c.get("title", "Untitled")
                slug = _slugify(title)
                name = f"sieve-{slug}"

                body = await self.compile_single(c)
                summary = c.get("executive_summary", title)
                description = await self._generate_description(title, summary)

                skill_content = SKILL_TEMPLATE.format(
                    name=name, description=description, body=body
                )
                path = output_dir / f"{name}.md"
                path.write_text(skill_content)
                written.append(path)
        else:
            groups = self.group_capsules(capsules, by=by)
            for key, group in groups.items():
                if len(group) < 2:
                    continue

                slug = _slugify(key)
                name = f"sieve-{slug}"
                body = await self.compile_group(key, group)

                titles = [c.get("title", "") for c in group[:5]]
                summary = f"Covers: {', '.join(titles)}"
                description = await self._generate_description(
                    f"{key} knowledge ({len(group)} capsules)", summary
                )

                skill_content = SKILL_TEMPLATE.format(
                    name=name, description=description, body=body
                )
                path = output_dir / f"{name}.md"
                path.write_text(skill_content)
                written.append(path)

        return written
