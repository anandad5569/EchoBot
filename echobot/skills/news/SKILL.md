---
name: news
description: "Use this skill when the user asks for the latest news, today's headlines, or news in a specific category (politics, finance, society, world, tech, sports, entertainment). Fetches content from authoritative Chinese news sources using fetch_web_page. Do NOT use for general web searches, historical events, or non-news questions."
---

# News

Fetch headlines and summaries from authoritative news sources using the **fetch_web_page** tool.

## Categories and Sources

| Category          | Source                   | URL                                      |
|-------------------|--------------------------|------------------------------------------|
| **Politics**      | People's Daily · CPC     | https://cpc.people.com.cn/               |
| **Finance**       | China Economic Net       | http://www.ce.cn/                        |
| **Society**       | China News · Society     | https://www.chinanews.com.cn/society/    |
| **World**         | CGTN                     | https://www.cgtn.com/                    |
| **Tech**          | Science and Technology Daily | https://www.stdaily.com/             |
| **Sports**        | CCTV Sports              | https://sports.cctv.com/                 |
| **Entertainment** | Sina Entertainment       | https://ent.sina.com.cn/star/            |

## How to Fetch News

1. **Identify categories**: Determine which category or categories the user wants. If unspecified, pick 1–2 most relevant ones.

2. **Fetch the page**: Call **fetch_web_page** with the URL from the table and a higher `max_chars` to capture more headlines:
   ```json
   {
     "url": "https://www.chinanews.com.cn/society/",
     "max_chars": 8000
   }
   ```

3. **Extract and summarize**: From the returned text content, identify headlines, dates, and key points. The tool strips HTML and returns readable text — look for repeated patterns of headline + brief description.

4. **Reply to the user**: Present a concise list organized by importance or time:
   - Headline (bold)
   - One or two sentence summary
   - Source name

5. **Multiple categories**: Call **fetch_web_page** once per URL — do not reuse content from one page for a different category.

## Notes

- If a site times out or returns an error, say so and suggest the user open the URL directly.
- If the page content looks like JavaScript placeholders (no readable headlines), the site may require a browser — say so and suggest an alternative source.
- Include the source URL in your reply so the user can open it for the full story.
- `max_chars` defaults to 4000; use 6000–10000 for news homepages to capture more headlines.
