import streamlit as st
from groq import Groq
import requests
import json

# --- Page Configuration ---
st.set_page_config(
    page_title="SkyCast AI | Smart Weather Assistant",
    page_icon="🌤️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom Styling (CSS) ---
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

# --- Retrieve Keys Safely ---
groq_api_key = str(st.secrets.get("GROQ_API_KEY", "")).strip()
weather_api_key = str(st.secrets.get("WEATHER_API_KEY", "")).strip()

if not groq_api_key or not weather_api_key:
    st.error("Missing credentials: Make sure `GROQ_API_KEY` and `WEATHER_API_KEY` are defined under Streamlit Settings > Secrets.")
    st.stop()

# Initialize Groq Client
client = Groq(api_key=groq_api_key)

# --- Weather API Helper ---
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
        return json.dumps({"error": f"Connection error: {str(e)}"})

# --- Function Calling Tool Schema ---
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
                        "description": "The city name (e.g. Hyderabad, London, Tokyo)"
                    }
                },
                "required": ["location"]
            }
        }
    }
]

# --- Sidebar Controls ---
with st.sidebar:
    st.markdown("### ⚙️ Engine Settings")
    selected_model = st.selectbox(
        "Groq Model",
        ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
        index=0
    )

    st.markdown("---")
    st.markdown("### ⚡ Quick Prompts")
    prompt_suggestions = [
        "What's the weather in Tokyo right now?",
        "Is it raining in London?",
        "Compare weather between Paris and Mumbai",
        "Current temperature in Bengaluru"
    ]

    for suggestion in prompt_suggestions:
        if st.button(suggestion, use_container_width=True):
            st.session_state.pending_prompt = suggestion
            st.rerun()

    st.markdown("---")
    if st.button("🗑️ Clear Conversation", use_container_width=True):
        st.session_state.messages = []
        st.session_state.pending_prompt = None
        st.rerun()

# --- Main Page Header ---
st.markdown("""
    <div class="hero-container">
        <div class="hero-title">🌤️ SkyCast AI</div>
        <div class="hero-subtitle">Real-time weather insights powered by OpenWeatherMap and Groq Function Calling</div>
    </div>
""", unsafe_allow_html=True)

# --- Session State Setup ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- Render Chat History ---
for msg in st.session_state.messages:
    role = msg.get("role")
    content = msg.get("content")
    if role == "user" and content:
        with st.chat_message("user", avatar="👤"):
            st.markdown(content)
    elif role == "assistant" and content:
        with st.chat_message("assistant", avatar="🌤️"):
            st.markdown(content)

# --- Input Handling ---
chat_input = st.chat_input("Ask about weather anywhere...")
prompt_to_process = None

if chat_input:
    prompt_to_process = chat_input
elif "pending_prompt" in st.session_state and st.session_state.pending_prompt:
    prompt_to_process = st.session_state.pending_prompt
    st.session_state.pending_prompt = None

if prompt_to_process:
    st.session_state.messages.append({"role": "user", "content": prompt_to_process})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt_to_process)

    with st.chat_message("assistant", avatar="🌤️"):
        with st.spinner("Analyzing weather query..."):
            try:
                # First Completion Call
                response = client.chat.completions.create(
                    messages=st.session_state.messages,
                    model=selected_model,
                    tools=tools,
                    tool_choice="auto"
                )
                response_message = response.choices[0].message

                # Handle Tool Execution
                if response_message.tool_calls:
                    tool_calls_dict = [tc.model_dump() for tc in response_message.tool_calls]
                    
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": response_message.content or "",
                        "tool_calls": tool_calls_dict
                    })

                    for tool_call in response_message.tool_calls:
                        if tool_call.function.name == "get_weather":
                            args = json.loads(tool_call.function.arguments)
                            loc = args.get("location", "")
                            weather_raw = get_weather(loc)
                            weather_data = json.loads(weather_raw)

                            if "error" not in weather_data:
                                cols = st.columns(4)
                                cols[0].metric("📍 Location", str(weather_data.get("location", loc)))
                                cols[1].metric("🌡️ Temp", f"{weather_data.get('temperature')} °C", f"Feels like {weather_data.get('feels_like')}°C")
                                cols[2].metric("💧 Humidity", f"{weather_data.get('humidity')}%")
                                cols[3].metric("💨 Wind", f"{weather_data.get('wind_speed')} m/s")

                            st.session_state.messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": weather_raw
                            })

                    # Second Completion Call with tool response included
                    second_response = client.chat.completions.create(
                        messages=st.session_state.messages,
                        model=selected_model,
                        tools=tools,
                        tool_choice="auto"
                    )
                    final_text = second_response.choices[0].message.content or ""
                    st.markdown(final_text)
                    st.session_state.messages.append({"role": "assistant", "content": final_text})

                else:
                    final_text = response_message.content or ""
                    st.markdown(final_text)
                    st.session_state.messages.append({"role": "assistant", "content": final_text})

            except Exception as err:
                st.error(f"Error communicating with Groq: {err}")
