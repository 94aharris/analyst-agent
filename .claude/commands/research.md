---
description: Analyze a research article, paper, or blog post using the research-analyzer agent to extract structured insights
---

Please use the research-analyzer agent to perform research on the URL(s) or file path(s): $ARGUMENTS

I'll analyze the content from the provided URL(s) or file path(s) using the research-analyzer agent to extract structured insights and create a comprehensive research summary.

Identify all the URLs or file paths in $ARGUMENTS. If there is more than one, work each separately with a separate research-analyzer subagent instance for each $LINK_OR_FILE.

For each URL or file path, use the Task tool to launch the research-analyzer subagent with the following prompt:

"Please analyze the content at this URL or file path: $LINK_OR_FILE

If this is a URL, fetch and thoroughly analyze the source. If this is a file path, read the file content and analyze it. When reading files, extract any metadata found between --- markers at the start of the file and include it in your analysis. Extract actionable insights, frameworks, and key concepts. Create a structured research summary following the research template format, and save it to the research/analysis/ folder with appropriate naming (research/analysis/[topic-or-technology]-[author-lastname].md).

Focus on:

- Core thesis and key quotes
- Main frameworks and components with implementation details
- Actionable takeaways and evidence-based insights
- All references and links mentioned
- Relevant keywords for searchability

Ensure the output follows the exact template structure with clear sections for Core Principle/Thesis, Main Framework/Components, Implementation Guidelines, Key Takeaways, and References."
