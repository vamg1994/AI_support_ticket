from langchain_community.chat_models import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
import os
import logging

logger = logging.getLogger(__name__)

class ITSupportAgent:
    def __init__(self):
        self.llm = ChatOpenAI(
            temperature=0,
            model_name="gpt-3.5-turbo",
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )

        self.system_prompt = """
        You are an experienced IT support professional. Your role is to:
        1. Analyze IT support tickets thoroughly
        2. Ask relevant follow-up questions when needed
        3. Provide detailed troubleshooting steps
        4. Track issue resolution progress

        Important Guidelines:
        - Always acknowledge the user's problem first
        - Ask follow-up questions when:
          * The issue description is vague
          * More technical details are needed
          * Previous steps didn't resolve the issue
        - For each solution:
          * Start with simple steps
          * Progress to more complex solutions
          * Include expected outcomes
          * Mention potential risks or warnings

        When responding, follow this format:
        CATEGORY: <network|hardware|software|access|other>
        CONFIDENCE: <score between 0 and 1>
        RESPONSE:
        Understanding: <brief summary of the issue>
        Diagnosis: <likely cause based on symptoms>
        Initial Questions: <if more information is needed>
        Steps to Resolve:
        1. <first step with expected outcome>
        2. <second step with expected outcome>
        3. <additional steps as needed>
        Additional Notes: <warnings, alternative solutions, or escalation criteria>
        Next Steps: <what to do if these steps don't resolve the issue>
        """

    def analyze_ticket(self, description, conversation_history=None):
        try:
            # Include conversation history in the prompt if available
            prompt = description
            if conversation_history:
                prompt = f"""
                Previous Conversation:
                {conversation_history}

                Current Message:
                {description}

                Provide a response that takes into account the previous conversation and any steps already attempted.
                """

            messages = [
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=prompt)
            ]

            response = self.llm.invoke(messages)

            # Parse the response
            lines = response.content.split('\n')
            category = None
            confidence = 0.0
            response_text = []

            current_section = None
            for line in lines:
                line = line.strip()
                if line.startswith('CATEGORY:'):
                    category = line.replace('CATEGORY:', '').strip().lower()
                elif line.startswith('CONFIDENCE:'):
                    confidence = float(line.replace('CONFIDENCE:', '').strip())
                elif line.startswith('RESPONSE:'):
                    current_section = 'response'
                elif current_section == 'response' and line:
                    response_text.append(line)

            # Adjust confidence based on response completeness
            if len(response_text) < 5:  # If response is too short
                confidence = min(confidence, 0.5)

            # Reduce confidence if key sections are missing
            required_sections = ['Understanding:', 'Diagnosis:', 'Steps to Resolve:']
            for section in required_sections:
                if not any(section in line for line in response_text):
                    confidence = min(confidence, 0.6)

            final_response = '\n'.join(response_text)
            return final_response, confidence, category

        except Exception as e:
            logger.error(f"Error in AI analysis: {str(e)}")
            return "I apologize, but I'm having trouble analyzing this ticket.", 0.0, "error"

    def needs_followup(self, description):
        """
        Analyze if the issue description needs follow-up questions
        """
        try:
            messages = [
                SystemMessage(content="You are an IT support analyst. Determine if this issue description needs follow-up questions. Respond with only 'true' or 'false'."),
                HumanMessage(content=f"Does this IT support issue need follow-up questions? Issue: {description}")
            ]

            response = self.llm.invoke(messages)
            return 'true' in response.content.lower()
        except Exception as e:
            logger.error(f"Error checking follow-up need: {str(e)}")
            return True  # Default to needing follow-up if there's an error