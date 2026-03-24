CAPSULE_EXTRACTION_PROMPT = """You are a knowledge extraction assistant. Analyze the provided content and extract structured knowledge into a JSON capsule.

Extract the following fields:
- title: A concise title (5-10 words) capturing the core topic
- executive_summary: A 2-sentence summary of the key points
- core_insight: A single "aha moment" or key takeaway (1-2 sentences)
- tags: 5-10 lowercase tags relevant to the content
- keywords: 5-10 specific keywords for search discovery
- topics: 2-5 broad topic areas
- category: A single category (e.g., "Technology", "Business", "Science", "Health", "Psychology", "Philosophy", "Design", "Engineering")
- domain: The knowledge domain (e.g., "technology", "business", "science", "health", "psychology")
- difficulty: One of "beginner", "intermediate", "advanced"
- content_type: One of "insight", "technique", "framework", "principle", "fact", "opinion", "tutorial", "reference"
- source_type: One of "article", "blog", "paper", "book", "video", "podcast", "tweet", "note", "conversation", "documentation", "other"

Return ONLY valid JSON with these exact field names. Do not include any additional text or markdown formatting.

Content to analyze:
{content}"""

IMAGE_DESCRIPTION_PROMPT = """Describe the content of this image in detail. Focus on:
- Key text or information visible
- Diagrams, charts, or visual data
- Important concepts being illustrated

Provide a clear, comprehensive description that captures the knowledge content of the image."""
