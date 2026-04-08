"""
Resume Builder - Uses your profile data with NATURAL keyword tailoring via LLM
Intelligently selects best-matching skills based on job keywords
"""

import yaml
import os
from pathlib import Path
from typing import Dict, List, Optional
from dotenv import load_dotenv
from llm import get_client

load_dotenv()


class ResumeBuilder:
    """
    Builds resumes using your profile data with NATURAL keyword tailoring
    """
    
    def __init__(self):
        # Load profile - use environment variable or relative path
        self.project_root = Path(__file__).parent.parent
        self.aihawk_dir = os.getenv("AIHAWK_DIR", str(self.project_root / "AIHawk"))
        
        profile_path = Path(self.aihawk_dir) / "my_profile.yaml"
        if not profile_path.exists():
            # Fallback to original path if needed (for existing setup)
            profile_path = Path.home() / "Desktop/JOBBOT/AIHawk/my_profile.yaml"
        
        with open(profile_path, 'r') as f:
            self.profile = yaml.safe_load(f)
        
        # Load detailed experience
        detailed_path = Path(self.aihawk_dir) / "data_folder" / "plain_text_resume.yaml"
        if not detailed_path.exists():
            detailed_path = Path.home() / "Desktop/JOBBOT/AIHawk/data_folder/plain_text_resume.yaml"
        
        if detailed_path.exists():
            with open(detailed_path, 'r') as f:
                self.detailed = yaml.safe_load(f)
        else:
            self.detailed = {}
        
        self.llm = get_client()
    
    def _parse_achievements(self, achievements_list: list) -> list:
        """
        Parse achievements - ONLY looks for [HIGH] markers
        Everything else is normal
        """
        parsed = []
        
        for achievement in achievements_list:
            text = achievement.strip()
            is_high = False
            
            # Check for HIGH marker
            if text.startswith('[HIGH]') or text.startswith('• [HIGH]'):
                is_high = True
                text = text.replace('[HIGH]', '').replace('• [HIGH]', '').strip()
            
            parsed.append({
                'text': text,
                'always_include': is_high
            })
        
        return parsed
    
    def _select_achievements(self, achievements: list, keywords: list, max_bullets: int = 3) -> list:
        """
        Select achievements - ALWAYS include [HIGH] ones first
        """
        parsed = self._parse_achievements(achievements)
        
        # Separate must-have from others
        must_include = [a for a in parsed if a['always_include']]
        others = [a for a in parsed if not a['always_include']]
        
        # Start with ALL must-include achievements
        selected = must_include.copy()
        
        # Fill remaining slots with best matching others
        remaining_slots = max_bullets - len(selected)
        if remaining_slots > 0 and others:
            # Score others by keyword relevance
            scored = []
            for achievement in others:
                score = 0
                for keyword in keywords:
                    if keyword.lower() in achievement['text'].lower():
                        score += 1
                scored.append((score, achievement))
            
            # Sort by score only (avoid comparing dicts on tie)
            scored.sort(key=lambda x: x[0], reverse=True)
            selected.extend([a for score, a in scored[:remaining_slots]])
        
        return selected
    
    def _select_best_skills(self, all_skills: list, keywords: list, max_skills: int = 10) -> list:
        """
        Select the most relevant skills based on job keywords
        """
        if not keywords or not all_skills:
            return all_skills[:max_skills]
        
        # Score each skill by how many keywords it matches
        scored = []
        for skill in all_skills:
            score = 0
            skill_lower = skill.lower()
            for keyword in keywords:
                if keyword.lower() in skill_lower:
                    score += 2
                elif any(related in skill_lower for related in [keyword.lower(), keyword.lower().replace(' ', '')]):
                    score += 1
            scored.append((score, skill))
        
        # Sort by score ONLY
        scored.sort(key=lambda x: x[0], reverse=True)
        
        # Return top max_skills (NOT max_bullets)
        return [skill for score, skill in scored[:max_skills]]
    
    def build_resume(self, language: str = "english", keywords: List[str] = None) -> str:
        """Build base resume using profile data"""
        
        personal = self.profile.get('personal_info', {})
        skills = self.profile.get('professional_skills', {})
        achievements = self.profile.get('key_achievements', [])
        certifications = self.profile.get('certifications', [])
        education = self.profile.get('education', [])
        
        # Get all skills from YAML - use empty defaults if not found
        all_tools = skills.get('tools_technologies', [])
        all_concepts = skills.get('skills_concepts', [])
        
        # Select best-matching skills based on job keywords
        if keywords and len(keywords) > 0:
            selected_tools = self._select_best_skills(all_tools, keywords, max_skills=10)
            selected_concepts = self._select_best_skills(all_concepts, keywords, max_skills=10)
        else:
            selected_tools = all_tools[:10]
            selected_concepts = all_concepts[:10]
        
        resume = []
        
        # ===== HEADER =====
        name = personal.get('name', '')
        email = personal.get('email', '')
        phone = personal.get('phone', '')
        location = personal.get('location', '')
        portfolio = personal.get('portfolio', '')
        
        # Only add header if we have the info (otherwise skip or use placeholders)
        if name:
            resume.append(name)
        if email or phone or location:
            resume.append(f"{email} | {phone} | {location}")
        if portfolio:
            resume.append(portfolio)
        if resume and resume[-1] != "":
            resume.append("")
        
        # ===== PROFESSIONAL SUMMARY =====
        resume.append("PROFESSIONAL SUMMARY")
        years = skills.get('experience', {}).get('total_years', 13)
        
        if keywords and len(keywords) > 0:
            keywords_text = ', '.join(keywords[:6])
            summary = f"Results-driven marketing leader with {years}+ years of experience specializing in {keywords_text}. Proven track record of driving brand growth, optimizing campaigns, and delivering measurable business impact through data-driven strategies and cross-functional leadership."
        else:
            summary = f"Results-driven marketing leader with {years}+ years of experience driving brand growth, optimizing campaigns, and delivering measurable results through data-driven strategies and cross-functional leadership."
        
        resume.append(summary)
        resume.append("")
        
        # ===== PROFESSIONAL EXPERIENCE =====
        resume.append("PROFESSIONAL EXPERIENCE")
        resume.append("")
        
        # Get detailed experience
        exp_details = self.detailed.get('experience_details', [])
        
        if exp_details:
            for exp in exp_details:
                company = exp.get('company', '')
                exp_location = exp.get('location', '')
                if company:
                    resume.append(f"{company} | {exp_location}")
                
                position = exp.get('position', '')
                period = exp.get('employment_period', '')
                if position:
                    resume.append(f"{position} | {period}")
                
                # Use all achievements if no keywords, otherwise select with priority
                achievements_list = exp.get('achievements', [])
                if keywords and len(keywords) > 0:
                    selected = self._select_achievements(achievements_list, keywords, max_bullets=3)
                    for ach in selected:
                        resume.append(f"• {ach['text']}")
                else:
                    for achievement in achievements_list[:3]:
                        achievement = achievement.replace('•', '').strip()
                        if achievement:
                            resume.append(f"• {achievement}")
                resume.append("")
        
        # ===== KEY PROJECTS =====
        projects = self.detailed.get('projects', [])
        if projects:
            resume.append("KEY PROJECTS")
            resume.append("")
            
            # Show top 2-3 projects
            for project in projects[:3]:
                name = project.get('name', '')
                company = project.get('company', '')
                period = project.get('period', '')
                
                if name:
                    resume.append(f"• {name} | {company}")
                    if period:
                        resume.append(f"  {period}")
                    
                    description = project.get('description', '')
                    if description:
                        for line in description.strip().split('\n'):
                            line = line.strip()
                            if not line:
                                continue
                            if line.startswith('Situation:'):
                                resume.append(f"  **Situation:**{line[len('Situation:'):]}")
                            elif line.startswith('Task:'):
                                resume.append(f"  **Task:**{line[len('Task:'):]}")
                            elif line.startswith('Action:'):
                                resume.append(f"  **Action:**{line[len('Action:'):]}")
                            elif line.startswith('Result:'):
                                resume.append(f"  **Result:**{line[len('Result:'):]}")
                            else:
                                resume.append(f"    {line}")
                    resume.append("")
        
        # ===== EDUCATION =====
        if education:
            resume.append("EDUCATION")
            for edu in education:
                degree = edu.get('degree', '')
                institution = edu.get('institution', '')
                year = edu.get('year', '')
                resume.append(f"**{degree}** - {institution}, {year}")
            resume.append("")
        
        # ===== CERTIFICATIONS =====
        if certifications:
            resume.append("CERTIFICATIONS")
            resume.append(", ".join(certifications))
            resume.append("")

        # ===== CORE COMPETENCIES =====
        resume.append("CORE COMPETENCIES")
        
        if selected_tools:
            resume.append(f"**Technical:** {', '.join(selected_tools)}")
        if selected_concepts:
            resume.append(f"**Strategic:** {', '.join(selected_concepts)}")
        
        return "\n".join(resume)
    
    def build_tailored_resume(self, language: str = "english", keywords: List[str] = None, 
                              job_title: str = None, job_description: str = None) -> str:
        """
        Build a resume tailored to job keywords
        Uses intelligent skill selection and priority achievements
        """
        
        if not keywords or not self.llm:
            return self.build_resume(language=language)
        
        # Build the resume with keyword-based selection
        return self.build_resume(language=language, keywords=keywords)
