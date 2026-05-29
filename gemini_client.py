import json
import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pydantic Schemas for Structured JSON Outputs
class SubTopicList(BaseModel):
    topics: List[str] = Field(
        description="A list of 5 to 10 distinct, sequential, high-yield sub-topics/sections extracted from the chapter text for study progression."
    )

class MCQOptions(BaseModel):
    A: str = Field(description="Option A")
    B: str = Field(description="Option B")
    C: str = Field(description="Option C")
    D: str = Field(description="Option D")
    E: str = Field(description="Option E")

class MCQItem(BaseModel):
    question: str = Field(
        description="The exact verbatim, word-for-word question parsed from the PDF text."
    )
    options: MCQOptions = Field(
        description="The exact answer options A, B, C, D, and E as parsed verbatim from the PDF text. If the PDF only has 4 options, map them to A-D and set E to 'N/A'."
    )
    correct_answer: str = Field(
        description="The single correct answer character parsed or derived from the text (must be uppercase A, B, C, D, or E)."
    )
    explanation: str = Field(
        description="The exact verbatim explanation parsed from the text if present, or a concise, fact-grounded explanation explaining the correct choice based strictly on textbook facts."
    )

class MCQList(BaseModel):
    questions: List[MCQItem] = Field(
        description="A collection of verbatim multiple choice questions parsed from the text."
    )

class GeminiStudyClient:
    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash"):
        """
        Initialize the Gemini Client with API Key and default model name.
        """
        self.api_key = api_key
        self.model_name = model_name
        self.client = genai.Client(api_key=api_key)

    def extract_subtopics(self, pdf_text: str) -> List[str]:
        """
        Extracts high-yield subtopics from the PDF content in a sequential study flow.
        """
        prompt = (
            "You are an expert pediatric residency program director and board prep coach. "
            "Analyze the following textbook chapter text extracted from a pediatric medical textbook PDF. "
            "Your task is to identify and extract a sequential list of 5 to 10 distinct sub-topics "
            "that represent the core logical divisions of this chapter, in chronological/logical order of study. "
            "These sub-topics will define a sequential study pathway. "
            "Make sure they are descriptive (e.g., 'Neonatal Hyperbilirubinemia', 'Biliary Atresia', 'Breastfeeding Jaundice').\n\n"
            f"--- TEXTBOOK TEXT ---\n{pdf_text}\n--- END OF TEXT ---"
        )
        
        try:
            logger.info("Calling Gemini API for subtopic extraction...")
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=SubTopicList,
                    temperature=0.1
                )
            )
            
            data = json.loads(response.text)
            topics = data.get("topics", [])
            logger.info(f"Successfully extracted {len(topics)} subtopics.")
            return topics
            
        except Exception as e:
            logger.error(f"Error in extract_subtopics: {str(e)}")
            raise e

    def extract_verbatim_mcqs(self, subtopic: str, chapter_context: str, num_questions: int, existing_questions: List[str] = None) -> List[Dict[str, Any]]:
        """
        Extracts verbatim (word-for-word) MCQs from the chapter text belonging to the selected subtopic.
        Uses the Gemini API strictly as a parser, detector, and categorizer.
        """
        exclude_str = ""
        if existing_questions:
            exclude_str = "\nCRITICAL: DO NOT extract any of the following questions as they have already been loaded:\n" + "\n".join([f"- {q}" for q in existing_questions])

        prompt = (
            "You are an expert pediatric board exam text-parsing agent. Your task is to analyze the textbook chapter text provided "
            "and STRICTLY extract existing multiple-choice questions (MCQs) word-for-word (verbatim) from the text that belong to "
            f"the sub-topic: '{subtopic}'.\n\n"
            "CRITICAL INSTRUCTIONS:\n"
            "1. DO NOT write, generate, synthesize, or invent any new questions. You must parse and extract the EXACT wording (verbatim) from the textbook text.\n"
            "2. Detect the exact options provided in the text. Ensure options are mapped to letters A, B, C, D, and E. If a question in the text only has 4 options, map them to A-D and set E to 'N/A'.\n"
            "3. Identify the correct answer (A, B, C, D, or E) from the textbook text, or logically derive it strictly based on the text.\n"
            "4. Extract the explanation verbatim from the text if it is provided. If no explanation is written in the text, write a brief, high-yield clinical explanation explaining why the correct answer is correct based strictly on facts in the chapter text.\n"
            f"5. Extract exactly {num_questions} questions.{exclude_str}\n\n"
            "If the textbook text does not contain explicit multiple-choice questions for this sub-topic, look for review statements, fact-checks, or key clinical summaries within this sub-topic and reformat them into verbatim-styled recall questions using the EXACT word-for-word text from the book, to keep the study session active. But prioritize extracting actual pre-existing MCQs first.\n\n"
            f"--- TEXTBOOK CHAPTER TEXT ---\n{chapter_context}\n--- END OF TEXT ---"
        )

        try:
            logger.info(f"Calling Gemini API to extract {num_questions} verbatim MCQs for subtopic: '{subtopic}'...")
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=MCQList,
                    temperature=0.1
                )
            )
            
            data = json.loads(response.text)
            questions = data.get("questions", [])
            
            # Convert structured schema items to plain python dicts for easier app consumption
            formatted_questions = []
            for q in questions:
                formatted_questions.append({
                    "question": q["question"],
                    "options": {
                        "A": q["options"]["A"],
                        "B": q["options"]["B"],
                        "C": q["options"]["C"],
                        "D": q["options"]["D"],
                        "E": q["options"]["E"],
                    },
                    "correct_answer": q["correct_answer"].strip().upper(),
                    "explanation": q["explanation"]
                })
                
            logger.info(f"Successfully extracted {len(formatted_questions)} questions verbatim.")
            return formatted_questions
            
        except Exception as e:
            logger.error(f"Error in extract_verbatim_mcqs: {str(e)}")
            raise e
