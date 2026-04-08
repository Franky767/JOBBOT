"""
Módulo LLM para AI Job Applier
Proporciona funciones para análisis de trabajos y personalización de materiales
Con detección automática de idioma mejorada (usa título + descripción)
"""

import json
import sys
import os
import asyncio
import re
from datetime import datetime 
from pathlib import Path
from typing import Dict, List, Optional
from playwright.async_api import async_playwright

# Asegurar que podemos importar deepseek_client
sys.path.append(os.path.dirname(__file__))
from deepseek_client import DeepSeekClient

# Inicializar cliente global
_client = None

def get_client():
    """Obtiene o crea una instancia del cliente"""
    global _client
    if _client is None:
        _client = DeepSeekClient()
    return _client

async def init_llm():
    """
    Inicializa el LLM (llamado por main.py al startup)
    """
    print("\n🔄 INICIALIZANDO LLM...")
    client = get_client()
    
    # Probar conexión
    test_response = client.generate(
        "Responde exactamente con una palabra: OK", 
        temperature=0.1
    )
    
    if test_response:
        print(f"\n✅ LLM INICIALIZADO CORRECTAMENTE")
        print(f"   Proveedor activo: {client.current_provider.upper()}")
        print(f"   Respuesta prueba: {test_response}")
    else:
        print("\n⚠️  LLM inicializado pero sin respuesta de prueba")
    
    return True

async def extract_hiring_manager_from_url(job_url: str) -> str:
    """
    Extract hiring manager name from LinkedIn job page
    Looks for the "Posted by" or "Hiring manager" section
    """
    try:
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()
        
        await page.goto(job_url, wait_until="domcontentloaded", timeout=10000)
        await page.wait_for_timeout(2000)
        
        # Try multiple selectors where hiring manager names appear
        selectors = [
            "a[href*='/in/'] span",
            ".hirer-card__hirer-name",
            ".job-details-hirer-trigger",
            "[data-test-id='hirer-name']",
            ".hirer-name",
            ".job-poster-info",
            ".poster-name",
            "div:has-text('Posted by') a",
            "div:has-text('Hiring manager') a",
            ".hirer-card__name",
            ".hirer-details__name"
        ]
        
        for selector in selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    text = await element.inner_text()
                    text = text.strip()
                    
                    # FILTER OUT LOCATIONS AND COUNTRIES
                    if text and len(text) > 3:
                        # List of locations to ignore
                        ignore_list = [
                            'united states', 'usa', 'u.s.a.', 'america', 'american samoa',
                            'alabama', 'alaska', 'arizona', 'arkansas', 'california',
                            'colorado', 'connecticut', 'delaware', 'florida', 'georgia',
                            'hawaii', 'idaho', 'illinois', 'indiana', 'iowa', 'kansas',
                            'kentucky', 'louisiana', 'maine', 'maryland', 'massachusetts',
                            'michigan', 'minnesota', 'mississippi', 'missouri', 'montana',
                            'nebraska', 'nevada', 'new hampshire', 'new jersey', 'new mexico',
                            'new york', 'north carolina', 'north dakota', 'ohio', 'oklahoma',
                            'oregon', 'pennsylvania', 'rhode island', 'south carolina',
                            'south dakota', 'tennessee', 'texas', 'utah', 'vermont',
                            'virginia', 'washington', 'west virginia', 'wisconsin', 'wyoming',
                            'remote', 'global', 'worldwide', 'anywhere'
                        ]
                        
                        text_lower = text.lower()
                        if text_lower in ignore_list or any(state in text_lower for state in ['alaska', 'alabama', 'arizona']):
                            print(f"   ⚠️ Ignoring location: {text}")
                            continue
                        
                        # Also check if it looks like a location (single word, capitalized)
                        if len(text.split()) == 1 and text[0].isupper() and text[1:].islower():
                            if text.lower() in ignore_list:
                                continue
                        
                        await browser.close()
                        await playwright.stop()
                        return text
            except:
                continue
        
        # If no element found, try to parse the page content
        content = await page.content()
        
        # Look for common patterns
        patterns = [
            r'Posted by ([A-Z][a-z]+ [A-Z][a-z]+)',
            r'Hiring manager:?\s*([A-Z][a-z]+ [A-Z][a-z]+)',
            r'Contact:?\s*([A-Z][a-z]+ [A-Z][a-z]+)',
            r'<span[^>]*>([A-Z][a-z]+ [A-Z][a-z]+)</span>'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                name = match.group(1).strip()
                # Filter again
                name_lower = name.lower()
                if name_lower not in ['united states', 'usa', 'remote'] and not any(state in name_lower for state in ['alaska', 'alabama']):
                    await browser.close()
                    await playwright.stop()
                    return name
        
        await browser.close()
        await playwright.stop()
        return None
        
    except Exception as e:
        print(f"⚠️ Could not extract hiring manager: {e}")
        return None

# ========== IMPROVED LANGUAGE DETECTION ==========

def detect_language(text: str, title: str = "") -> str:
    """
    Detect if text is in English or Spanish using BOTH description and title
    
    Args:
        text: Job description text
        title: Job title (optional, helps with accuracy)
    
    Returns:
        "english" or "spanish"
    """
    if not text or len(text) < 100:
        return "english"
    
    text_lower = text.lower()
    title_lower = title.lower() if title else ""
    
    print(f"\n🌐 LANGUAGE DETECTION:")
    print(f"   Title: '{title}'")
    
    # ===== STRONG SPANISH INDICATORS IN TITLE =====
    spanish_title_patterns = [
        # Spanish prepositions/articles with job titles
        ' de ', ' del ', ' de la ', ' en ', ' para ',
        # Common Spanish job title structures
        'director de', 'gerente de', 'jefe de', 'coordinador de',
        'especialista en', 'responsable de', 'técnico en',
        # Spanish job title words
        'marketing', 'ventas', 'comercial', 'publicidad', 'comunicación',
        'recursos humanos', 'financiero', 'administrativo'
    ]
    
    # If title contains strong Spanish patterns, it's likely Spanish
    if title_lower:
        for pattern in spanish_title_patterns:
            if pattern in title_lower:
                # Double-check with location if available
                if any(city in title_lower for city in ['madrid', 'barcelona', 'valencia', 'sevilla']):
                    print(f"   📍 Spanish city detected in title")
                    return "spanish"
                
                # If it's a Spanish pattern but location is US, still might be Spanish job
                # (many US companies post Spanish-language jobs)
                print(f"   📌 Spanish title pattern detected: '{pattern}'")
                
                # But if the description is overwhelmingly English, trust the description
                english_count, spanish_count = _count_language_indicators(text_lower)
                if english_count > spanish_count * 2:  # English is dominant
                    print(f"   ⚠️ Title suggests Spanish but description is mostly English")
                    return "english"
                return "spanish"
    
    # ===== COUNT LANGUAGE INDICATORS IN DESCRIPTION =====
    english_count, spanish_count = _count_language_indicators(text_lower)
    
    # Check for Spanish special characters
    spanish_special = sum(1 for char in text if char in 'áéíóúñü¿¡')
    spanish_count += spanish_special * 2  # Give extra weight to special chars
    
    total = english_count + spanish_count
    if total == 0:
        return "english"
    
    spanish_ratio = spanish_count / total
    
    print(f"   English indicators: {english_count}")
    print(f"   Spanish indicators: {spanish_count}")
    print(f"   Spanish special chars: {spanish_special}")
    print(f"   Spanish ratio: {spanish_ratio:.2f}")
    
    # ===== DECISION LOGIC =====
    # Only return Spanish if strong majority (60%+) AND enough indicators
    if spanish_ratio > 0.6 and spanish_count > 8:
        print(f"   ✅ Detected: SPANISH")
        return "spanish"
    else:
        print(f"   ✅ Detected: ENGLISH")
        return "english"

def _count_language_indicators(text_lower: str) -> tuple:
    """
    Count English and Spanish language indicators in text
    Returns (english_count, spanish_count)
    """
    # Strong Spanish indicators (words that are rarely in English)
    spanish_indicators = [
        ' el ', ' la ', ' los ', ' las ', ' y ', ' en ', ' de ', ' que ', ' por ', ' para ',
        ' con ', ' una ', ' un ', ' trabajo', ' empresa', ' requisitos', ' experiencia',
        ' habilidades', ' puesto', ' ofrecemos', ' buscamos', ' funciones',
        ' responsabilidades', ' salario', ' beneficios', ' jornada', ' remoto',
        ' presencial', ' contrato', ' indefinido', ' temporal', ' prácticas',
        ' nuestro', ' nuestra', ' equipo', ' candidato', ' estar', ' será', ' hemos',
        ' este', ' esta', ' estos', ' estas', ' mismo', ' misma', ' todos', ' todas',
        ' durante', ' mediante', ' través', ' según', ' entre', ' hacia', ' desde'
    ]
    
    # Strong English indicators
    english_indicators = [
        ' the ', ' and ', ' for ', ' with ', ' this ', ' that ', ' from ', ' your ',
        ' job', ' work', ' company', ' requirements', ' experience', ' skills',
        ' position', ' we offer', ' looking for', ' responsibilities',
        ' salary', ' benefits', ' full-time', ' part-time', ' remote',
        ' onsite', ' contract', ' permanent', ' temporary', ' internship',
        ' our ', ' team ', ' candidate', ' qualified', ' will ', ' have ',
        ' this ', ' these ', ' those ', ' during ', ' through ', ' within ',
        ' between ', ' among ', ' about ', ' above ', ' below ', ' under '
    ]
    
    spanish_count = sum(1 for word in spanish_indicators if word in text_lower)
    english_count = sum(1 for word in english_indicators if word in text_lower)
    
    return english_count, spanish_count

# ========== KEYWORD EXTRACTION ==========

def extract_keywords_from_title(title: str) -> List[str]:
    """
    Extract important keywords from job title
    """
    if not title:
        return []
    
    # Common words to filter out
    stop_words = ['the', 'of', 'in', 'for', 'at', 'and', 'or', 'a', 'an', 
                  'de', 'del', 'la', 'el', 'los', 'las', 'y', 'en', 'para']
    
    words = re.findall(r'\b[a-zA-Z]+\b', title.lower())
    keywords = [w for w in words if w not in stop_words and len(w) > 2]
    
    return keywords

# ========== JOB ANALYSIS FUNCTIONS ==========

def extract_requirements(job_description: str, job_title: str = "") -> dict:
    """
    Extrae requisitos de una descripción de trabajo
    Ahora usa el título para mejor detección de idioma
    """
    print("\n🔍 EXTRACTING JOB REQUIREMENTS...")
    client = get_client()
    
    # Detect language using BOTH title and description
    job_language = detect_language(job_description, job_title)
    print(f"   📝 Descripción en: {job_language.upper()}")
    
    # Extract keywords from title
    title_keywords = extract_keywords_from_title(job_title)
    if title_keywords:
        print(f"   🏷️ Title keywords: {', '.join(title_keywords)}")
    
    # Translate to English for consistent analysis if needed
    description_for_analysis = job_description
    if job_language == "spanish":
        print("   🔄 Traduciendo descripción al inglés para análisis...")
        description_for_analysis = translate_text(job_description, "english")
    
    prompt = f"""Analyze this job description and extract requirements in JSON format.

Job Title: {job_title}

Description:
{description_for_analysis}

Respond ONLY with this JSON (no additional text):
{{
    "title": "Job title (in English)",
    "skills": ["skill1", "skill2"],
    "experience": "years of experience required",
    "education": "education required",
    "keywords": ["keyword1", "keyword2"]
}}"""
    
    response = client.generate(prompt, temperature=0.1)
    
    if response:
        try:
            start = response.find('{')
            end = response.rfind('}') + 1
            if start >= 0 and end > start:
                result = json.loads(response[start:end])
                # Add title keywords if not already present
                if title_keywords:
                    existing_keywords = set(result.get('keywords', []))
                    result['keywords'] = list(existing_keywords.union(set(title_keywords)))
                result['_original_language'] = job_language
                return result
        except json.JSONDecodeError as e:
            print(f"❌ Error parsing JSON: {e}")
    
    # Default if fails
    return {
        "title": job_title or "Unknown position",
        "skills": [],
        "experience": "",
        "education": "",
        "keywords": title_keywords,
        "_original_language": job_language
    }

# ========== TRANSLATION FUNCTIONS ==========

def translate_text(text: str, to_language: str) -> str:
    """
    Traduce texto entre inglés y español
    """
    client = get_client()
    
    prompt = f"""Translate this text to {to_language}. 
Return ONLY the translation, no explanations.

Original text:
{text}

Translation to {to_language}:"""
    
    response = client.generate(prompt, temperature=0.1)
    return response if response else text

def translate_job_title(title: str, to_language: str) -> str:
    """Traduce títulos de trabajo específicos"""
    translations = {
        "marketing manager": "gerente de marketing",
        "digital marketing manager": "gerente de marketing digital",
        "content marketing manager": "gerente de marketing de contenidos",
        "product marketing manager": "gerente de marketing de producto",
        "social media manager": "gestor de redes sociales",
        "marketing director": "director de marketing",
        "head of marketing": "director de marketing",
        "marketing specialist": "especialista en marketing",
        "seo specialist": "especialista en seo",
        "content manager": "content manager",
        "community manager": "community manager",
        "marketing analyst": "analista de marketing",
        "growth marketing": "growth marketing",
    }
    
    if to_language == "spanish":
        title_lower = title.lower()
        for eng, spa in translations.items():
            if eng in title_lower:
                pattern = re.compile(re.escape(eng), re.IGNORECASE)
                return pattern.sub(spa, title)
        return translate_text(title, "spanish")
    else:
        reverse = {v: k for k, v in translations.items()}
        title_lower = title.lower()
        for spa, eng in reverse.items():
            if spa in title_lower:
                pattern = re.compile(re.escape(spa), re.IGNORECASE)
                return pattern.sub(eng, title)
        return translate_text(title, "english")

def calculate_match_score(resume_text: str, requirements: dict) -> int:
    """
    Calculates intelligent match score between resume and job requirements
    Uses HUMAN-LIKE evaluation: achievements matter most, skills in context
    """
    print("\n📊 CALCULATING INTELLIGENT MATCH SCORE...")
    
    # Extract job requirements
    required_skills = set(s.lower() for s in requirements.get('skills', []))
    job_keywords = set(k.lower() for k in requirements.get('keywords', []))
    job_title = requirements.get('title', '').lower()
    
    # Combine all job terms
    all_job_terms = required_skills.union(job_keywords)
    
    # Add job title words
    title_words = set(re.findall(r'\b[a-z0-9]+\b', job_title))
    all_job_terms.update(title_words)
    
    # Load profile to get achievements
    from pathlib import Path
    import yaml
    
    profile_path = Path.home() / "Desktop/JOBBOT/AIHawk/my_profile.yaml"
    with open(profile_path, 'r') as f:
        profile = yaml.safe_load(f)
    
    achievements = profile.get('key_achievements', [])
    
    # ===== 1. ACHIEVEMENT RELEVANCE (50% of total) - HUMAN LOGIC =====
    achievement_score = 0
    relevant_achievements = []
    
    # Job-specific outcome keywords (what this job cares about)
    outcome_keywords = {
        'brand': ['brand', 'awareness', 'recognition', 'identity', 'positioning', 'visibility'],
        'global': ['global', 'international', 'worldwide', 'multi-country', 'cross-border'],
        'campaign': ['campaign', 'launch', 'initiative', 'program', 'project', 'event'],
        'revenue': ['revenue', 'growth', 'increase', 'roi', 'profit', 'sales', 'budget'],
        'team': ['team', 'cross-functional', 'collaboration', 'stakeholder', 'leadership', 'partnership'],
        'strategy': ['strategy', 'planning', 'execution', 'implementation', 'development', 'roadmap'],
        'content': ['content', 'marketing', 'social', 'digital', 'media', 'copy'],
        'analytics': ['analytics', 'data', 'metrics', 'kpi', 'performance', 'tracking', 'analysis'],
        'management': ['management', 'oversight', 'direction', 'coordination', 'organization']
    }
    
    # Score each achievement
    for achievement in achievements:
        achievement_lower = achievement.lower()
        relevance = 0
        matched_categories = set()
        
        # Check each category
        for category, keywords in outcome_keywords.items():
            if any(k in achievement_lower for k in keywords):
                relevance += 2  # Each category match is worth 2 points
                matched_categories.add(category)
        
        # Check for specific skill mentions (extra points)
        for skill in all_job_terms:
            if skill in achievement_lower and len(skill) > 3:
                relevance += 1
                matched_categories.add(skill)
        
        # Check for metrics (always good)
        if any(m in achievement_lower for m in ['%', 'percent', 'million', 'k', '$', 'increased', 'decreased', 'improved', 'reduced']):
            relevance += 2
            matched_categories.add('metrics')
        
        relevant_achievements.append({
            'text': achievement,
            'score': relevance,
            'matches': list(matched_categories)
        })
    
    # Sort by relevance score
    relevant_achievements.sort(key=lambda x: x['score'], reverse=True)
    
    # HUMAN LOGIC: ANY achievement that hits 2+ categories is relevant
    # Score of 4+ (2 categories * 2 points) means it's hitting multiple job aspects
    good_achievements = sum(1 for a in relevant_achievements if a['score'] >= 4)
    
    # Show top achievements
    print(f"\n   🏆 TOP ACHIEVEMENTS FOR THIS JOB:")
    for i, ach in enumerate(relevant_achievements[:5], 1):
        print(f"      {i}. Score {ach['score']}: {ach['matches']}")
        print(f"         {ach['text'][:100]}...")
    
    # Calculate achievement match - based on PERCENTAGE of achievements that are relevant
    excellent_achievements = 0
    if achievements:
        # Simple percentage of achievements that are relevant (score >=4)
        achievement_match = int((good_achievements / len(achievements)) * 100)
        
        # Bonus for having MULTIPLE highly relevant achievements (score >=8)
        excellent_achievements = sum(1 for a in relevant_achievements if a['score'] >= 8)
        if excellent_achievements >= 5:
            achievement_match = min(100, achievement_match + 15)
        elif excellent_achievements >= 3:
            achievement_match = min(100, achievement_match + 10)
        elif excellent_achievements >= 1:
            achievement_match = min(100, achievement_match + 5)
        
    else:
        achievement_match = 0
    
    print(f"\n   📍 Achievements relevant to this job (score ≥4): {good_achievements}/{len(achievements)}")
    print(f"   📍 Excellent achievements (score ≥8): {excellent_achievements}")
    print(f"   📍 Achievement match: {achievement_match}%")
    
    # ===== 2. SKILL MATCH (30% of total) - IMPROVED VERSION =====
    # Not just counting words, but understanding related terms and context
    resume_lower = resume_text.lower()
    
    # Expanded skill clusters with healthcare-specific terms
    skill_clusters = {
        'healthcare': ['healthcare', 'health', 'medical', 'hospital', 'clinic', 'patient', 'clinical', 'fda', 'regulatory', 'compliance'],
        'marketing': ['marketing', 'campaign', 'promotion', 'advertising', 'communications', 'brand', 'outreach'],
        'relationship': ['relationship', 'stakeholder', 'partnership', 'collaboration', 'community', 'client', 'customer'],
        'sales': ['sales', 'revenue', 'growth', 'acquisition', 'retention', 'lead generation', 'pipeline'],
        'strategy': ['strategy', 'planning', 'strategic', 'initiative', 'development', 'execution'],
        'admissions': ['admissions', 'enrollment', 'intake', 'evaluation', 'assessment', 'screening', 'verification'],
        'insurance': ['insurance', 'managed care', 'verification', 'coverage', 'provider', 'payer'],
        'communication': ['communication', 'presentation', 'public speaking', 'training', 'multilingual'],
        'management': ['management', 'leadership', 'oversight', 'direction', 'coordination', 'supervision']
    }
    
    # Map job skills to clusters
    skill_match_score = 0
    matched_clusters = set()
    cluster_matches = {}
    
    # Initialize cluster match counts
    for cluster in skill_clusters:
        cluster_matches[cluster] = 0
    
    # Check each job term against clusters
    for job_term in all_job_terms:
        term_matched = False
        
        # Direct match in resume
        if job_term in resume_lower:
            skill_match_score += 3  # Direct matches worth 3 points
            matched_clusters.add(job_term)
            term_matched = True
            print(f"      ✓ Direct match: {job_term}")
        
        # Check clusters
        for cluster, terms in skill_clusters.items():
            # If job term is related to this cluster
            if job_term in terms or any(t in job_term for t in terms):
                # Check if ANY term from this cluster appears in resume
                cluster_hits = 0
                for cluster_term in terms:
                    if cluster_term in resume_lower:
                        cluster_hits += 1
                        if cluster_term not in matched_clusters:
                            matched_clusters.add(f"{cluster_term}")
                
                if cluster_hits > 0:
                    # Partial match via cluster
                    skill_match_score += cluster_hits  # Points based on how many cluster terms match
                    cluster_matches[cluster] = cluster_hits
                    if not term_matched:
                        print(f"      ✓ Cluster match: {job_term} via {cluster} ({cluster_hits} hits)")
                    term_matched = True
        
        # Bonus for healthcare-specific terms (this job is healthcare)
        healthcare_terms = ['healthcare', 'medical', 'hospital', 'clinical', 'patient', 'fda']
        if any(term in resume_lower for term in healthcare_terms):
            if not any(m in str(matched_clusters) for m in ['healthcare', 'medical']):
                skill_match_score += 5  # Big bonus for healthcare experience
                matched_clusters.add('healthcare_experience')
                print(f"      ✓ BONUS: Healthcare experience detected")
    
    # Normalize skill score
    if all_job_terms:
        # Max possible: each term could get up to 3 points direct, plus cluster bonuses
        max_skill_score = len(all_job_terms) * 5  # Higher max to account for bonuses
        skill_match = min(100, int((skill_match_score / max_skill_score) * 100))
    else:
        skill_match = 50
    
    print(f"   📍 Skill clusters matched: {matched_clusters}")
    print(f"   📍 Skill match score (raw): {skill_match_score}")
    print(f"   📍 Skill match: {skill_match}%")
    
    # ===== 3. INDUSTRY MATCH (10% of total) =====
    profile_industries = set(i.lower() for i in profile.get('professional_skills', {}).get('industries', []))
    
    # This job is in talent/staffing but your industries cover many sectors
    # We'll look for any overlap
    job_industry_indicators = ['talent', 'staffing', 'workforce', 'recruiting', 'agency']
    
    industry_matches = set()
    for indicator in job_industry_indicators:
        if indicator in job_title or indicator in resume_text.lower():
            for prof_industry in profile_industries:
                if any(word in prof_industry for word in ['agency', 'consulting', 'service']):
                    industry_matches.add('agency/consulting')
    
    # Also check if your industries appear in job description
    for prof_industry in profile_industries:
        if prof_industry in resume_text.lower():
            industry_matches.add(prof_industry)
    
    industry_match = min(100, len(industry_matches) * 20)  # 5 matches = 100%
    print(f"   📍 Industry matches: {industry_matches}")
    print(f"   📍 Industry match: {industry_match}%")
    
    # ===== 4. EXPERIENCE LEVEL (10% of total) =====
    required_years = 0
    exp_text = requirements.get('experience', '')
    
    years_match = re.search(r'(\d+)(?:\s*[-+]\s*(\d+))?\s*(?:year|yr)', exp_text.lower())
    if years_match:
        min_years = int(years_match.group(1))
        max_years = int(years_match.group(2)) if years_match.group(2) else min_years + 2
        required_years = (min_years + max_years) / 2
    
    your_years = profile.get('professional_skills', {}).get('experience', {}).get('total_years', 13)
    
    if required_years == 0 or your_years >= required_years:
        experience_match = 100
    else:
        experience_match = int((your_years / required_years) * 100)
    
    print(f"   📍 Required years: ~{required_years}, Your years: {your_years}")
    print(f"   📍 Experience match: {experience_match}%")
    
    # ===== CALCULATE WEIGHTED TOTAL =====
    # NEW WEIGHTS: Achievements matter most!
    total_score = (
        achievement_match * 0.50 +  # What you've DONE (most important)
        skill_match * 0.30 +         # What you KNOW
        industry_match * 0.10 +       # Where you've worked
        experience_match * 0.10        # How long
    )
    
    total_score = round(total_score)
    
    print(f"\n📊 FINAL MATCH SCORE: {total_score}%")
    print(f"   Breakdown:")
    print(f"   • Achievements: {achievement_match}% (50% weight) - WHAT MATTERS MOST")
    print(f"   • Skills: {skill_match}% (30% weight)")
    print(f"   • Industry: {industry_match}% (10% weight)")
    print(f"   • Experience: {experience_match}% (10% weight)")
    
    if total_score >= 65:
        print(f"   ✅ RECOMMENDATION: APPLY - Strong match!")
    elif total_score >= 60:
        print(f"   ⚠️ RECOMMENDATION: Consider applying - Decent match")
    else:
        print(f"   ❌ RECOMMENDATION: Skip - Low match")
    
    return total_score

async def tailor_cover_letter(requirements: dict, profile: Dict, language: str, 
                        company: str = None, job_url: str = None) -> str:
    """Generate a tailored cover letter using LLM with hiring manager name"""
    
    # ===== FILTER OUT LOCATIONS =====
    location_keywords = [
        'american samoa', 'united states', 'usa', 'u.s.a.', 'america',
        'alabama', 'alaska', 'arizona', 'arkansas', 'california',
        'colorado', 'connecticut', 'delaware', 'florida', 'georgia',
        'hawaii', 'idaho', 'illinois', 'indiana', 'iowa', 'kansas',
        'kentucky', 'louisiana', 'maine', 'maryland', 'massachusetts',
        'michigan', 'minnesota', 'mississippi', 'missouri', 'montana',
        'nebraska', 'nevada', 'new hampshire', 'new jersey', 'new mexico',
        'new york', 'north carolina', 'north dakota', 'ohio', 'oklahoma',
        'oregon', 'pennsylvania', 'rhode island', 'south carolina',
        'south dakota', 'tennessee', 'texas', 'utah', 'vermont',
        'virginia', 'washington', 'west virginia', 'wisconsin', 'wyoming',
        'remote', 'global', 'worldwide', 'anywhere'
    ]
    
    # Filter out location if passed as company
    if company and company.lower().strip() in location_keywords:
        print(f"⚠️ Ignoring location as company: {company}")
        company = None
    
    client = get_client()
    
    job_title = requirements.get('title', 'the position')
    if language == "spanish":
        job_title = translate_job_title(job_title, "spanish")
    
    # Get REAL contact info from profile
    personal = profile.get('personal_info', {})
    name = personal.get('name', 'Frank Tavarez')
    email = personal.get('email', 'Tavarez.frank@outlook.com')
    phone = personal.get('phone', '+1 (786) 227-7764')
    location = personal.get('location', 'St Paul, MN, USA')
    linkedin = personal.get('linkedin', 'https://www.linkedin.com/in/frank-tavarez/')
    
    years = profile.get('professional_skills', {}).get('experience', {}).get('total_years', 13)
    
    # Get top skills/keywords
    skills = requirements.get('skills', [])[:5]
    keywords = requirements.get('keywords', [])[:5]
    all_keywords = list(set(skills + keywords))
    keywords_text = ', '.join(all_keywords)
    top_keywords = ', '.join(all_keywords[:5])
    
    # ===== HANDLE UNKNOWN COMPANY =====
    is_company_unknown = not company or company == "Unknown Company" or company == "Unknown"
    
    # Build the greeting based on company/hiring manager
    hiring_manager = None
    if job_url and not is_company_unknown:
        hiring_manager = await extract_hiring_manager_from_url(job_url)
        print(f"🔍 Extracted hiring manager: {hiring_manager}")
        
        # Filter out locations from hiring manager
        if hiring_manager:
            hiring_lower = hiring_manager.lower().strip()
            if hiring_lower in location_keywords or any(loc in hiring_lower for loc in location_keywords):
                print(f"   ⚠️ Ignoring location as hiring manager: {hiring_manager}")
                hiring_manager = None
    
    # Build greeting with fallbacks
    if is_company_unknown:
        greeting = "Dear Hiring Team,"
    elif hiring_manager and company and company != "the company":
        greeting = f"Dear {hiring_manager} and the {company} Team,"
    elif hiring_manager:
        greeting = f"Dear {hiring_manager},"
    elif company and company != "the company":
        greeting = f"Dear {company} Hiring Team,"
    else:
        greeting = "Dear Hiring Team,"
    
    print(f"📝 Using greeting: {greeting}")
    
    # Build company references for the body
    if is_company_unknown:
        # Use generic references
        company_references = {
            'first_mention': "your team",
            'possessive': "your team's",
            'repetitive': "your organization",
            'goal': "your goals",
            'mission': "your mission",
            'company_name_placeholder': "your organization"
        }
    else:
        company_references = {
            'first_mention': company,
            'possessive': f"{company}'s",
            'repetitive': company,
            'goal': f"{company}'s goals",
            'mission': f"{company}'s mission",
            'company_name_placeholder': company
        }
    
    # Build the header with REAL info
    header = f"""{name}
{email} | {phone} | {location}

{datetime.now().strftime('%B %d, %Y')}

{greeting}

"""
    
    if language == "spanish":
        prompt = f"""Write ONLY the body of a bold cover letter (do not include the header, date, greeting, or signature) for:

POSITION: {job_title}
NAME: {name}
YEARS EXPERIENCE: {years}
COMPANY NAME: {company_references['first_mention']}

JOB KEYWORDS: {keywords_text}

IMPORTANT INSTRUCTIONS:
- The company is: {company_references['first_mention']}
- DO NOT use "[Company Name]" or any placeholders
- Use these company references in the body:
  * First mention: "{company_references['first_mention']}"
  * Subsequent mentions: "{company_references['repetitive']}" or "{company_references['possessive']}"
  * When talking about their mission/goals: "{company_references['mission']}" or "{company_references['goal']}"
- DO NOT include a header, date, greeting, or signature - I will add those separately

The cover letter body should:
1. Be professional, bold, and enthusiastic
2. Mention relevant experience
3. Naturally incorporate the keywords
4. Connect with job requirements
5. Reference the company/organization naturally in the body
6. End with a call to action (but not a signature)
7. Incorporate a personal passion as main reason for the application

Cover letter body (ONLY the body paragraphs, no header/greeting/signature):"""
    else:
        prompt = f"""Write ONLY the body of a bold cover letter (do not include the header, date, greeting, or signature) for:

POSITION: {job_title}
NAME: {name}
YEARS EXPERIENCE: {years}
COMPANY NAME: {company_references['first_mention']}

JOB KEYWORDS: {keywords_text}

IMPORTANT INSTRUCTIONS:
- The company is: {company_references['first_mention']}
- DO NOT use "[Company Name]" or any placeholders
- Use these company references in the body:
  * First mention: "{company_references['first_mention']}"
  * Subsequent mentions: "{company_references['repetitive']}" or "{company_references['possessive']}"
  * When talking about their mission/goals: "{company_references['mission']}" or "{company_references['goal']}"
- DO NOT include a header, date, greeting, or signature - I will add those separately

The cover letter body should:
1. Be professional, bold, and enthusiastic
2. Mention relevant experience
3. Naturally incorporate the keywords
4. Connect with job requirements
5. Reference the company/organization naturally in the body
6. End with a call to action (but not a signature)
7. Incorporate a personal passion as main reason for the application

Cover letter body (ONLY the body paragraphs, no header/greeting/signature):"""
    
    body = client.generate(prompt, temperature=0.5)
    
    # Post-process to replace any remaining "Unknown Company" with generic references
    if is_company_unknown:
        body = body.replace("Unknown Company", "your organization")
        body = body.replace("the company", "your team")
        body = body.replace("this company", "this organization")
    
    # Combine header + body + signature
    signature = f"""

Sincerely,

{name}"""
    
    full_letter = header + body + signature
    
    return full_letter

async def process_job_application(job_description: str, profile: Dict, job_title: str = "", 
                            company: str = None, job_url: str = None) -> Dict:
    """
    Procesa una solicitud de trabajo completa con detección automática de idioma
    """
    # Detect language using both title and description
    job_language = detect_language(job_description, job_title)
    print(f"\n🌍 IDIOMA DETECTADO: {job_language.upper()}")
    
    # Extract requirements (pass title for better context)
    requirements = extract_requirements(job_description, job_title)
    
    # Get resume in correct language
    from resume_builder import ResumeBuilder
    builder = ResumeBuilder()
    resume_text = builder.build_resume(language=job_language)
    
    # Calculate match
    match_score = calculate_match_score(resume_text, requirements)
    
    # Generate cover letter with company and URL (now await since it's async)
    cover_letter = await tailor_cover_letter(
        requirements, 
        profile, 
        job_language,
        company=company,
        job_url=job_url
    )
    
    # Don't try to extract hiring manager here again - it's already done in tailor_cover_letter
    return {
        "match_score": match_score,
        "requirements": requirements,
        "tailored_resume": resume_text,
        "tailored_cover_letter": cover_letter,
        "job_language": job_language,
        "materials_language": job_language
    }

# ========== PDF GENERATION ==========

import re
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib import colors

def save_resume_as_pdf(text: str, path: Path, title: str = "Resume", doc_type: str = "resume"):
    """Save text content as a professionally formatted PDF with minimalist style"""
    
    doc = SimpleDocTemplate(
        str(path),
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    
    # Get base styles
    base_styles = getSampleStyleSheet()
    
    # Custom minimalist styles
    styles = {
        'title': ParagraphStyle(
            'MinimalTitle',
            parent=base_styles['Normal'],
            fontSize=16,
            leading=20,
            spaceAfter=6,
            alignment=TA_CENTER,
            textColor=colors.black,
            fontName='Times-Bold'
        ),
        'contact': ParagraphStyle(
            'MinimalContact',
            parent=base_styles['Normal'],
            fontSize=10,
            leading=12,
            spaceAfter=4,
            alignment=TA_CENTER,
            textColor=colors.gray,
            fontName='Times-Roman'
        ),
        'section_header': ParagraphStyle(
            'MinimalSectionHeader',
            parent=base_styles['Normal'],
            fontSize=12,
            leading=14,
            spaceBefore=4,
            spaceAfter=4,
            alignment=TA_LEFT,
            textColor=colors.black,
            fontName='Times-Bold',
        ),
        'company': ParagraphStyle(
            'MinimalCompany',
            parent=base_styles['Normal'],
            fontSize=11,
            leading=13,
            spaceBefore=4,
            spaceAfter=2,
            alignment=TA_LEFT,
            textColor=colors.black,
            fontName='Times-Bold'
        ),
        'position': ParagraphStyle(
            'MinimalPosition',
            parent=base_styles['Normal'],
            fontSize=10,
            leading=12,
            spaceAfter=2,
            alignment=TA_LEFT,
            textColor=colors.black,
            fontName='Times-Italic'
        ),
        'bullet': ParagraphStyle(
            'MinimalBullet',
            parent=base_styles['Normal'],
            fontSize=10,
            leading=12,
            leftIndent=10,
            spaceAfter=2,
            alignment=TA_LEFT,
            textColor=colors.black,
            fontName='Times-Roman'
        ),
        'normal': ParagraphStyle(
            'MinimalNormal',
            parent=base_styles['Normal'],
            fontSize=10,
            leading=12,
            spaceAfter=4,
            alignment=TA_LEFT,
            textColor=colors.black,
            fontName='Times-Roman'
        ),
        'date': ParagraphStyle(
            'MinimalDate',
            parent=base_styles['Normal'],
            fontSize=10,
            leading=12,
            spaceAfter=4,
            alignment=TA_RIGHT,
            textColor=colors.gray,
            fontName='Times-Roman'
        ),
    }
    
    story = []
    lines = text.split('\n')
    i = 0
    
    # Define section headers to look for
    section_headers = [
        "PROFESSIONAL SUMMARY", "PROFESSIONAL EXPERIENCE", "CORE COMPETENCIES",
        "EDUCATION", "CERTIFICATIONS", "ADDITIONAL INFORMATION", "KEY PROJECTS",
        "TECHNICAL SKILLS", "LANGUAGES"
    ]
    
    # Track if we've seen the header already
    header_processed = False
    contact_processed = False
    
    while i < len(lines):
        line = lines[i].rstrip()
        
        # Skip empty lines but add spacing
        if not line:
            story.append(Spacer(1, 0.05 * inch))
            i += 1
            continue
        
        # === FORCE HEADER DETECTION ===
        # First non-empty line should be name
        if not header_processed and line and not any(header in line for header in section_headers):
            story.append(Paragraph(line, styles['title']))
            header_processed = True
            i += 1
            continue
        
        # Second line with contact info
        if header_processed and not contact_processed and ('@' in line or '|' in line or '+' in line):
            story.append(Paragraph(line, styles['contact']))
            story.append(Spacer(1, 0.1 * inch))
            contact_processed = True
            i += 1
            continue
        
        # Check if this is a section header
        is_header = False
        for header in section_headers:
            if line == header or line.startswith(header + ":"):
                is_header = True
                break
        
        if is_header:
            if i > 0:
                story.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
                story.append(Spacer(1, 0.05 * inch))
            story.append(Paragraph(line, styles['section_header']))
            i += 1
            continue
        
        # Check if we're in the KEY PROJECTS section
        if 'KEY PROJECTS' in ''.join(lines[max(0, i-10):i]):
            # Handle bold markers in project text
            if '**' in line:
                processed_line = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', line)
                story.append(Paragraph(processed_line, styles['normal']))
            else:
                story.append(Paragraph(line, styles['normal']))
            i += 1
            continue
        
        # Check if this is a company line (contains | and company keywords)
        company_keywords = ['remote', 'solutions', 'group', 'corp', 'university', 'college', 'hospital', 
                           'agency', 'xiocast', 'balance', 'registrar', 'twitter', 'chanel', 'google', 'hardwood']
        
        if '|' in line and any(word in line.lower() for word in company_keywords):
            parts = line.split('|')
            company_part = parts[0].strip()
            location_part = parts[1].strip() if len(parts) > 1 else ""
            
            story.append(Paragraph(f"<b>{company_part}</b> | {location_part}", styles['company']))
            i += 1
            
            # Next line might be position with date
            if i < len(lines) and '|' in lines[i]:
                pos_parts = lines[i].split('|')
                position = pos_parts[0].strip()
                date_range = pos_parts[1].strip() if len(pos_parts) > 1 else ""
                story.append(Paragraph(f"<i>{position}</i> | {date_range}", styles['position']))
                i += 1
            continue
        
        # Check if this is a position line (contains | and job title keywords)
        position_keywords = ['manager', 'consultant', 'advisor', 'director', 'specialist', 'marketing', 'sales']
        if '|' in line and any(word in line.lower() for word in position_keywords):
            parts = line.split('|')
            position_part = parts[0].strip()
            date_part = parts[1].strip() if len(parts) > 1 else ""
            
            story.append(Paragraph(f"<i>{position_part}</i> | {date_part}", styles['position']))
            i += 1
            continue
        
        # Handle bold markers in text (for all other lines)
        if '**' in line:
            processed_line = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', line)
            story.append(Paragraph(processed_line, styles['normal']))
            i += 1
            continue
        
        # Handle italic markers (single asterisks, but not double)
        if '*' in line and '**' not in line:
            processed_line = re.sub(r'\*(.*?)\*', r'<i>\1</i>', line)
            story.append(Paragraph(processed_line, styles['normal']))
            i += 1
            continue
        
        # Bullet points
        if line.startswith('•') or line.startswith('-') or line.startswith('*'):
            content = line[1:].strip()
            # Handle bold inside bullet points
            if '**' in content:
                content = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', content)
            story.append(Paragraph(f"• {content}", styles['bullet']))
            i += 1
            continue
        
        # Contact info (only if not already processed)
        if ('@' in line or '+1' in line) and not contact_processed:
            story.append(Paragraph(line, styles['contact']))
            contact_processed = True
            i += 1
            continue
        
        # Everything else - regular text
        story.append(Paragraph(line, styles['normal']))
        i += 1
    
    doc.build(story)
    print(f"   ✅ PDF saved: {path}")
