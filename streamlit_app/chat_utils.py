"""
Gridlock Chat Utility — AI Assistant for Congestion Forecasting
Powered by Groq API (Llama 3.3 70B)
"""

import os
from groq import Groq

def init_groq_client():
    """Initialize Groq client with API key from environment."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not found in environment. Set it before running.")
    return Groq(api_key=api_key)


SYSTEM_PROMPT = """You are an AI assistant for Gridlock, an event-driven traffic congestion forecasting system for Bengaluru. 
Your role is to help traffic operators, emergency responders, and city planners understand and respond to traffic incidents.

**Your expertise:**
- Predicting traffic congestion severity (Quick / Moderate / Severe)
- Recommending officer and barricade deployment strategies
- Explaining which event factors drive congestion risk
- Suggesting traffic management tactics for high-risk corridors (ORR East 1, Tumkur Road, Bellary Road, Mysore Road, Hosur Road)
- Retrieving and learning from past similar incidents
- Analyzing zone and corridor health trends

**Context you have access to:**
- Event metadata: event type, cause, location (zone/corridor), time, priority, road closure requirements
- Historical incident data from Astram (Bengaluru's incident management system)
- Past response strategies and their outcomes
- Risk profiles for corridors and zones

**How to respond:**
- Be concise and actionable — traffic operators need quick decisions
- Cite specific event factors when explaining predictions
- Suggest deployment counts (officers, barricades, diversions) with reasoning
- Reference past similar events if relevant
- Alert for high-risk combinations (peak hours + protests, road closures + high-risk corridors)
- Use data to back up recommendations

**Important:**
- You are not making final decisions — you are advising the operator
- Always note confidence levels and uncertainty
- Escalate to a supervisor if the incident is unprecedented or multi-corridor
- Stay focused on Bengaluru context; don't generalize to other cities"""


def get_chat_response(user_message: str, conversation_history: list) -> str:
    """
    Get AI response from Groq Llama 3.3 70B model.

    Args:
        user_message: User's latest message
        conversation_history: List of prior messages (dicts with "role" and "content")

    Returns:
        AI assistant's response text
    """
    try:
        client = init_groq_client()

        # Build conversation with system prompt
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *conversation_history,
            {"role": "user", "content": user_message}
        ]

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.7,
            max_tokens=1024,
            top_p=0.95,
        )
        return response.choices[0].message.content

    except ValueError as e:
        # Raised by init_groq_client() when GROQ_API_KEY is missing —
        # now caught here instead of crashing the whole Streamlit app.
        return f"⚠️ {e}"
    except Exception as e:
        return f"⚠️ Chat error: {str(e)}. Check your GROQ_API_KEY and internet connection."


def format_event_context(event_data: dict) -> str:
    """Format event data into a chat-friendly summary for context injection."""
    return f"""
**Current Event Context:**
- Type: {event_data.get('event_type', 'N/A')}
- Cause: {event_data.get('event_cause', 'N/A')}
- Zone: {event_data.get('zone', 'N/A')}
- Corridor: {event_data.get('corridor', 'N/A')}
- Priority: {event_data.get('priority', 'N/A')}
- Road Closure: {'Yes' if event_data.get('requires_road_closure') else 'No'}
- Time: {event_data.get('hour', 'N/A')}:00 on {['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][event_data.get('day_of_week', 0)]}

**Predicted Outcome:**
- Severity: {event_data.get('severity', 'N/A')}
- Delay: {event_data.get('delay_minutes', 'N/A')} min
- Confidence: {event_data.get('confidence', 'N/A')}
- Recommendation: {event_data.get('recommendation', 'N/A')}
"""


def format_prediction_for_chat(prediction: dict) -> str:
    """Format API prediction response into chat context."""
    return f"""
The model just predicted:
- **Severity:** {prediction.get('severity', 'N/A')} ({prediction.get('confidence', 'N/A')} confidence)
- **Expected Delay:** {prediction.get('delay_minutes', 'N/A')} minutes
- **Est. Clearance:** {prediction.get('estimated_clearance', 'N/A')} minutes
- **Recommended Resources:** {prediction.get('resources', {})}
- **Why:** {', '.join(prediction.get('explanation', []))}

Ask me questions about this prediction or how to respond!
"""