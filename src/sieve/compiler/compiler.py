from pathlib import Path

from sieve.compiler.templates import COMPILE_PROMPT, SKILL_TEMPLATE
from sieve.llm.client import LLMClient
from sieve.mcp.api_client import SieveAPIClient


class SkillCompiler:
    def __init__(self, api_url: str, api_key: str) -> None:
        self.api_client = SieveAPIClient(api_url=api_url, api_key=api_key)
        self.llm = LLMClient()

    def group_capsules(self, capsules: list[dict], by: str = "author") -> dict[str, list[dict]]:
        groups: dict[str, list[dict]] = {}
        for c in capsules:
            key = c.get(by, "unknown")
            groups.setdefault(key, []).append(c)
        return groups

    async def compile_group(self, author: str, capsules: list[dict]) -> str:
        capsules_text = ""
        for c in capsules:
            tags = ", ".join(c.get("tags", []))
            capsules_text += f"\n### {c['title']}\nTags: {tags}\n"
            capsules_text += f"Insight: {c.get('core_insight', '')}\n"
            capsules_text += f"Summary: {c.get('executive_summary', '')}\n"

        prompt = COMPILE_PROMPT.format(author=author, capsules_text=capsules_text)
        response = await self.llm.client.chat.completions.create(
            model=self.llm.model,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content

    async def compile_to_skills(
        self,
        output_dir: Path,
        pack: str | None = None,
        personal: bool = False,
        all_capsules: bool = False,
    ) -> list[Path]:
        data = await self.api_client.list_capsules(limit=200)
        capsules = data.get("capsules", [])

        if pack:
            capsules = [c for c in capsules if c.get("author") == pack]
        elif personal:
            capsules = [c for c in capsules if c.get("author") == "personal"]

        groups = self.group_capsules(capsules, by="author")
        output_dir.mkdir(parents=True, exist_ok=True)
        written = []

        for author, group in groups.items():
            if len(group) < 2:
                continue
            body = await self.compile_group(author, group)
            slug = author.lower().replace(" ", "-")
            name = f"sieve-{slug}"
            description = f"Knowledge and principles from {author} ({len(group)} capsules)"
            skill_content = SKILL_TEMPLATE.format(name=name, description=description, body=body)
            path = output_dir / f"{name}.md"
            path.write_text(skill_content)
            written.append(path)

        return written
