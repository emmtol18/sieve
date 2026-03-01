SKILL_TEMPLATE = """---
name: {name}
description: {description}
---

{body}
"""

COMPILE_PROMPT = """You are a skill compiler. Given a collection of knowledge capsules from {author}, distill them into a concise Claude Code skill file.

The skill should contain:
1. Core principles (numbered list of actionable rules)
2. Domain-specific guidance organized by topic
3. Anti-patterns to avoid

Be concise. Each principle should be 1-2 sentences. Organize by topic when there are enough capsules.
Output only the skill body content (markdown), no frontmatter.

Capsules:
{capsules_text}"""
