import unittest

from jobapply.generation import _answer, clean_html, render_resume
from jobapply.models import Job


class GenerationTests(unittest.TestCase):
    def test_answers_use_resume_evidence(self):
        job = Job("ashby", "1", "AI Engineer", "Acme")
        source = "linkedin.com/in/example +55 (12) 99613-0832"
        self.assertIn("linkedin.com/in/example", _answer("Linkedin URL", job, source))
        self.assertIn("99613", _answer("Phone / Whatsapp", job, source))

    def test_html_is_cleaned(self):
        self.assertEqual(clean_html("<strong>Python</strong> &amp; RAG"), "Python &amp; RAG")

    def test_render_resume_uses_template_structure(self):
        template = """\n% JOBAPPLY:SUMMARY:START\nold summary\n% JOBAPPLY:SUMMARY:END\n% JOBAPPLY:SKILLS:START\nold skills\n% JOBAPPLY:SKILLS:END\n% JOBAPPLY:EXPERIENCE:START\nold experience\n% JOBAPPLY:EXPERIENCE:END\n"""
        job = Job("ashby", "42", "Python AI Engineer", "Acme", description="Python RAG AWS LangGraph")
        profile = {
            "summary": "Experienced engineer",
            "experience": [{"company": "Example Company", "dates": "2020 -- Present", "role": "Engineer", "bullets": ["Built Python RAG systems"], "technologies": "Python, RAG"}],
            "skills": [["AI", "RAG, LangChain"]],
        }
        rendered = render_resume(template, job, profile)
        self.assertIn("Targeted for Python AI Engineer roles", rendered)
        self.assertIn("RAG, LangChain", rendered)
        self.assertIn("Example Company", rendered)
        self.assertNotIn("old summary", rendered)
        self.assertNotIn("old experience", rendered)

    def test_experience_is_newest_first(self):
        template = "% JOBAPPLY:SUMMARY:START\nold\n% JOBAPPLY:SUMMARY:END\n% JOBAPPLY:SKILLS:START\nold\n% JOBAPPLY:SKILLS:END\n% JOBAPPLY:EXPERIENCE:START\nold\n% JOBAPPLY:EXPERIENCE:END"
        profile = {
            "summary": "Engineer",
            "experience": [
                {"company": "Older", "dates": "January 2020 -- December 2021", "role": "Engineer", "bullets": ["Older work"], "technologies": "Python"},
                {"company": "Newest", "dates": "August 2024 -- Present", "role": "Engineer", "bullets": ["Newest work"], "technologies": "Python"},
            ],
            "skills": [["Programming", "Python"]],
        }
        rendered = render_resume(template, type("Job", (), {"title": "Engineer", "description": "Python"})(), profile)
        self.assertLess(rendered.index("Newest"), rendered.index("Older"))
