import streamlit as st
from groq import Groq
import requests
import json

st.set_page_config(
    page_title="SkyCast AI | Smart Weather Assistant",
    page_icon="🌤️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Dark UI
st.markdown("""
    <style>
    .stApp {
        background: radial-gradient(circle at top left, #121826, #0b0f17);
        color: #e2e8f0;
    }
    .hero-container {
        padding: 1.5rem;
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.7), rgba(15, 23, 42, 0.7));
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        backdrop-filter: blur(12px);
        margin-bottom: 1.5rem;
    }
    .hero-title {
        font-size: 2rem;
        font-weight: 700;
        margin: 0;
        background: linear-gradient(90deg, #38bdf8, #818cf8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .hero-subtitle {
        color: #94a3b8;
        font-size: 0.95rem;
        margin-top: 0.3rem;
    }
    .stChatMessage {
        border-radius: 12px;
        margin-bottom: 0.8rem;
    }
    section[data-testid="stSidebar"] {
        background-color: #0d131f;
        border-right: 1px solid rgba(255, 255, 255, 0.05);
    }
    </style>
""", unsafe_allow_html=True)

# Retrieve API Keys
groq_api_key = str(st.secrets.get("GROQ_API_KEY", "")).strip()
weather_api_key = str(st.secrets.get("WEATHER_API_KEY", "")).strip()

if not groq_api_key or not weather_api_key:
    st.error("Missing keys: Please configure GROQ_API_KEY and WEATHER_API_KEY in Streamlit Secrets.")
    st.stop()

client = Groq(api_key=groq_api_key)
MODEL_ID = "openai/gpt-oss-120b"

# Weather Tool Function
def get_weather(location: str):
    url = f"https://api.openweathermap.org/data/2.5/weather?q={location}&units=metric&appid={weather_api_key}"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        if data.get("cod") == 200:
            return json.dumps({
                "location": data.get("name", location),
                "temperature": round(data["main"]["temp"], 1),
                "feels_like": round(data["main"]["feels_like"], 1),
                "humidity": data["main"]["humidity"],
                "wind_speed": data["wind"]["speed"],
                "description": data["weather"][0]["description"].title()
            })
        else:
            return json.dumps({"error": f"City '{location}' not found."})
    except Exception as e:
        return json.dumps({"error": f"Connection failed: {str(e)}"})

# Function Calling Definition
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Fetch real-time weather metrics for a specified city or location.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The city name (e.g., Hyderabad, London, Tokyo)"
                    }
                },
                "required": ["location"]
            }
        }
    }
]

# Sidebar
with st.sidebar:
    st.markdown("### ⚙️ Engine")
    st.code(MODEL_ID, language="text")

    st.markdown("---")
    st.markdown("### ⚡ Quick Prompts")
    quick_queries = [
        "What's the weather in Tokyo right now?",
        "Is it raining in London?",
        "Compare weather between Paris and Mumbai",
        "Current temperature in Bengaluru"
    ]

    for q in quick_queries:
        if st.button(q, use_container_width=True):
            st.session_state.pending_prompt = q
            st.rerun()

    st.markdown("---")
    if st.button("🗑️ Clear Conversation", use_container_width=True):
        st.session_state.chat_history = []
        st.session_state.pending_prompt = None
        st.rerun()

# Header
st.markdown(f"""
    <div class="hero-container">
        <div class="hero-title">🌤️ SkyCast AI</div>
        <div class="hero-subtitle">Powered by {MODEL_ID} and OpenWeatherMap</div>
    </div>
""", unsafe_allow_html=True)

# State initialization
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Display conversation
for msg in st.session_state.chat_history:
    role = msg.get("role")
    content = msg.get("content")
    if role == "user" and content:
        with st.chat_message("user", avatar="👤"):
            st.markdown(content)
    elif role == "assistant" and content:
        with st.chat_message("assistant", avatar="🌤️"):
            st.markdown(content)

# Prompt check
chat_input = st.chat_input("Ask about weather anywhere...")
user_query = None

if chat_input:
    user_query = chat_input
elif "pending_prompt" in st.session_state and st.session_state.pending_prompt:
    user_query = st.session_state.pending_prompt
    st.session_state.pending_prompt = None

if user_query:
    st.session_state.chat_history.append({"role": "user", "content": user_query})
    with st.chat_message("user", avatar="👤"):
        st.markdown(user_query)

    with st.chat_message("assistant", avatar="🌤️"):
        with st.spinner(f"Querying {MODEL_ID}..."):
            try:
                # 1. First model call
                response = client.chat.completions.create(
                    messages=st.session_state.chat_history,
                    model=MODEL_ID,
                    tools=tools,
                    tool_choice="auto"
                )
                assistant_msg = response.choices[0].message

                # 2. Check for tool execution
                if assistant_msg.tool_calls:
                    # Append assistant message with its tool calls
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": assistant_msg.content or "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments
                                }
                            }
                            for tc in assistant_msg.tool_calls
                        ]
                    })

                    # Execute each tool
                    for tc in assistant_msg.tool_calls:
                        if tc.function.name == "get_weather":
                            args = json.loads(tc.function.arguments)
                            loc = args.get("location", "")
                            weather_json_str = get_weather(loc)
                            weather_obj = json.loads(weather_json_str)

                            if "error" not in weather_obj:
                                cols = st.columns(4)
                                cols[0].metric("📍 Location", str(weather_obj.get("location", loc)))
                                cols[1].metric("🌡️ Temp", f"{weather_obj.get('temperature')} °C", f"Feels like {weather_obj.get('feels_like')}°C")
                                cols[2].metric("💧 Humidity", f"{weather_obj.get('humidity')}%")
                                cols[3].metric("💨 Wind", f"{weather_obj.get('wind_speed')} m/s")

                            # Add tool output directly to messages
                            st.session_state.chat_history.append({
                                "role": "tool",
                                "tool_call_id": tc.id,
                                "name": "get_weather",
                                "content": weather_json_str
                            })

                    # 3. Second call to get final natural answer
                    second_response = client.chat.completions.create(
                        messages=st.session_state.chat_history,
                        model=MODEL_ID,
                        tools=tools,
                        tool_choice="auto"
                    )
                    final_text = second_response.choices[0].message.content or ""
                    st.markdown(final_text)
                    st.session_state.chat_history.append({"role": "assistant", "content": final_text})

                else:
                    final_text = assistant_msg.content or ""
                    st.markdown(final_text)
                    st.session_state.chat_history.append({"role": "assistant", "content": final_text})

            except Exception as err:
                st.error(f"Groq API error: {err}")
