SKILL_TEMPLATE = """---
name: {name}
description: {description}
---

{body}
""".lstrip()

COMPILE_SINGLE_PROMPT = """\
You are a Claude Code skill compiler. Transform this knowledge capsule into a Claude Code skill file.

## Capsule
Title: {title}
Tags: {tags}
Core Insight: {core_insight}
Summary: {executive_summary}
Full Content:
{full_content}

## Output Requirements

Output ONLY the skill body content (markdown, no YAML frontmatter).

Follow this structure:
1. **Overview** — What is this? Core principle in 1-2 sentences.
2. **When to Use** — Bullet list of specific symptoms, situations, and triggers. Start each with a concrete scenario.
3. **Quick Reference** — Table or concise bullets for scanning the key points.
4. **Common Mistakes** — What goes wrong + how to fix it.

## Rules
- Be concise. Each principle should be 1-2 sentences max.
- Use keywords throughout for discoverability: error messages, tool names, symptoms.
- Do NOT include YAML frontmatter — only the markdown body.
- Do NOT use emojis.
- Aim for under 500 words total.
"""

COMPILE_GROUP_PROMPT = """\
You are a Claude Code skill compiler. Distill these knowledge capsules from {author} into a single Claude Code skill file.

## Capsules
{capsules_text}

## Output Requirements

Output ONLY the skill body content (markdown, no YAML frontmatter).

Follow this structure:
1. **Overview** — What this collection covers. Core theme in 1-2 sentences.
2. **Core Principles** — Numbered list of actionable rules distilled from the capsules. Each 1-2 sentences.
3. **Quick Reference** — Domain-specific guidance organized by topic. Use tables or concise bullets.
4. **Common Mistakes** — Anti-patterns to avoid, drawn from the capsules.

## Rules
- Be concise. Total output should be under 800 words.
- Organize by topic when there are enough capsules to warrant it.
- Use keywords throughout for discoverability: error messages, tool names, symptoms.
- Do NOT include YAML frontmatter — only the markdown body.
- Do NOT use emojis.
"""

DESCRIPTION_PROMPT = """\
Write a Claude Code skill description for this skill. The description must:
- Start with "Use when"
- Describe ONLY triggering conditions (when someone would need this knowledge)
- Be under 200 characters
- Be written in third person
- NOT summarize the skill's content or workflow

Skill title: {title}
Skill content summary: {summary}

Output ONLY the description text, nothing else."""
