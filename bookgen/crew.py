"""CrewAI authoring pipeline. Imports are lazy so --dry-run works offline."""
import os
import json
from .catalog import relevant_refs


def generate(chapter, evidence_bundle=None):
    from crewai import Agent, Task, Crew, Process, LLM

    llm = LLM(
        model=os.getenv("BOOK_LLM_MODEL", "openai/gpt-4o-mini"),
        temperature=float(os.getenv("BOOK_TEMPERATURE", "0.2")),
    )
    researcher = Agent(
        role="Technical Research Librarian",
        goal="Create an accurate chapter evidence map with only supplied reference identifiers",
        backstory="You carefully distinguish established claims from uncertain or version-dependent claims.",
        llm=llm, max_iter=3, verbose=False,
    )
    author = Agent(
        role="Principal AI Engineer and Textbook Author",
        goal="Write rigorous, approachable, detailed chapters for Staff and Principal interviews",
        backstory="You teach mathematical foundations and practical architecture without pretending unverifiable facts are proven.",
        llm=llm, max_iter=4, verbose=False,
    )
    engineer = Agent(
        role="Code and Architecture Reviewer",
        goal="Improve executable code examples, equations, Mermaid diagrams and design trade-offs",
        backstory="You inspect code for correctness but do not claim to have executed it.",
        llm=llm, max_iter=3, verbose=False,
    )
    editor = Agent(
        role="Technical Editor and Interview Examiner",
        goal="Produce polished Markdown with consistent headings, sound reasoning and senior-level interview practice",
        backstory="You flag gaps and retain citations; you never invent papers or claim a tool was run.",
        llm=llm, max_iter=3, verbose=False,
    )
    refs = relevant_refs(chapter)
    allowed = "\n".join(f"[@{r['id']}] {r['citation']} {r['url']}" for r in refs)
    evidence_text = ""
    if evidence_bundle:
        evidence_text = "\nRETRIEVED METADATA (not full-text proof):\n" + json.dumps(
            evidence_bundle, ensure_ascii=False, indent=2)[:22000]
    spec = f"Chapter {chapter['number']}: {chapter['title']}\nPart: {chapter['part_title']}\nAudience: 12+ years, Staff/Principal/Lead AI, Data Science, CV, ML Engineering and Architecture roles."
    evidence = Task(
        description=(
            f"Build a detailed evidence/teaching outline for {spec}.\n"
            "Use ONLY the source IDs below as citations. You have NOT retrieved the source contents, "
            "so do not pretend to have checked any text, results or API versions. "
            "Mark facts requiring independent source verification and suggest what to verify. "
            "Use source references only for clearly relevant claims.\n"
            f"Seed references:\n{allowed}" + evidence_text
        ),
        expected_output="Teaching outline, essential math, algorithms, risks, and source mapping with [@id] citations.",
        agent=researcher,
    )
    writing = Task(
        description=(
            f"Write a substantive Markdown textbook chapter: {spec}.\n"
            "Required exact H2 headings: Learning Objectives; Foundations; Mathematical Derivation; "
            "Worked Example; Implementation; Architecture and Flowcharts; Production Trade-offs; "
            "Interview Questions; Exercises; References. "
            "Use H1 '# Chapter N: Title'. Include precise LaTeX using $$...$$, at least one Mermaid flowchart, "
            "a complete Python example with explicit dependencies and synthetic/sample data, complexity analysis, "
            "failure cases, evaluation methods, 8 interview questions (senior, staff, principal), "
            "3 worked exercises, and a concise recap. For leadership chapters, mathematical content may be "
            "a quantitative decision framework. Cite ONLY supplied IDs as [@id], never fabricate sources. "
            "Explain when an example is illustrative, not benchmarked. Output Markdown only."
        ),
        expected_output="Detailed self-contained Markdown chapter with equations, code, Mermaid, examples and citations.",
        agent=author, context=[evidence], markdown=True,
    )
    review = Task(
        description=(
            "Review and REWRITE the previous Markdown chapter. Check equations symbol by symbol; "
            "improve code syntax and imports; include at least one Mermaid flowchart; analyze runtime, memory, "
            "operational risks, alternatives and scaling. Do not say code has been executed. "
            "Preserve all required headings and supported citations. Output the complete revised Markdown."
        ),
        expected_output="Complete corrected Markdown chapter, not review notes.",
        agent=engineer, context=[writing], markdown=True,
    )
    polish = Task(
        description=(
            "Finalize the entire Markdown chapter for a 12+ year professional audience. "
            "Keep the exact H2 headings, math, code fences, Mermaid, and [@id] citations. "
            "Do not invent measurements or sources. Return ONLY the full revised Markdown chapter, "
            "no commentary, no enclosing markdown fence."
        ),
        expected_output="Publication-quality full Markdown chapter ready for automated checks and human review.",
        agent=editor, context=[review], markdown=True,
    )
    result = Crew(
        agents=[researcher, author, engineer, editor],
        tasks=[evidence, writing, review, polish],
        process=Process.sequential,
        verbose=False,
    ).kickoff()
    return str(result.raw if hasattr(result, "raw") else result)
