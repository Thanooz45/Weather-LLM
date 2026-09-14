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
    /* Main container background & typography */
    .stApp {
        background: radial-gradient(circle at top left, #121826, #0b0f17);
        color: #e2e8f0;
    }

    /* Custom Header card */
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

    /* Weather stat badge */
    .weather-card {
        padding: 1rem 1.25rem;
        background: rgba(30, 41, 59, 0.6);
        border-radius: 12px;
        border: 1px solid rgba(56, 189, 248, 0.25);
        margin: 0.75rem 0;
    }

    /* Chat bubble polish */
    .stChatMessage {
        border-radius: 12px;
        margin-bottom: 0.8rem;
    }

    /* Sidebar customization */
    section[data-testid="stSidebar"] {
        background-color: #0d131f;
        border-right: 1px solid rgba(255, 255, 255, 0.05);
    }
    </style>
""", unsafe_allow_html=True)

# --- Retrieve Keys ---
groq_api_key = st.secrets.get("GROQ_API_KEY")
weather_api_key = st.secrets.get("WEATHER_API_KEY")

if not groq_api_key or not weather_api_key:
    st.error("Missing credentials: Make sure `GROQ_API_KEY` and `WEATHER_API_KEY` are defined in Streamlit secrets.")
    st.stop()

client = Groq(api_key=groq_api_key)

# --- Weather API Helper ---
def get_weather(location: str):
    url = f"http://api.openweathermap.org/data/2.5/weather?q={location}&units=metric&appid={weather_api_key}"
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
            return json.dumps({"error": f"City '{location}' not found. Check the spelling."})
    except Exception as e:
        return json.dumps({"error": f"Network error: {str(e)}"})

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
                        "description": "The city or locality name (e.g., Tokyo, London, Bengaluru)"
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
            st.session_state.preset_prompt = suggestion

    st.markdown("---")
    if st.button("🗑️ Clear Conversation", use_container_width=True):
        st.session_state.messages = []
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
    if msg["role"] == "user":
        with st.chat_message("user", avatar="👤"):
            st.markdown(msg["content"])
    elif msg["role"] == "assistant" and msg.get("content"):
        with st.chat_message("assistant", avatar="🌤️"):
            st.markdown(msg["content"])

# --- Handle Incoming Queries ---
active_input = st.chat_input("Ask about weather anywhere (e.g., 'Do I need an umbrella in Paris today?')")

# Check if a preset button was clicked
if "preset_prompt" in st.session_state and st.session_state.preset_prompt:
    active_input = st.session_state.preset_prompt
    st.session_state.preset_prompt = None

if active_input:
    # 1. Record and display user prompt
    st.session_state.messages.append({"role": "user", "content": active_input})
    with st.chat_message("user", avatar="👤"):
        st.markdown(active_input)

    # 2. Query LLM
    with st.chat_message("assistant", avatar="🌤️"):
        with st.spinner("Analyzing weather inquiry..."):
            response = client.chat.completions.create(
                messages=st.session_state.messages,
                model=selected_model,
                tools=tools,
                tool_choice="auto"
            )
            response_message = response.choices[0].message

            # 3. Tool execution branch
            if response_message.tool_calls:
                st.session_state.messages.append(response_message)

                for tool_call in response_message.tool_calls:
                    if tool_call.function.name == "get_weather":
                        args = json.loads(tool_call.function.arguments)
                        target_location = args.get("location")

                        weather_raw = get_weather(target_location)
                        weather_data = json.loads(weather_raw)

                        # Display visual metric badges if the data fetch was successful
                        if "error" not in weather_data:
                            cols = st.columns(4)
                            cols[0].metric("📍 Location", weather_data["location"])
                            cols[1].metric("🌡️ Temp", f"{weather_data['temperature']} °C", f"Feels like {weather_data['feels_like']}°C")
                            cols[2].metric("💧 Humidity", f"{weather_data['humidity']}%")
                            cols[3].metric("💨 Wind", f"{weather_data['wind_speed']} m/s")

                        # Pass raw json response directly back to the tool role
                        st.session_state.messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": weather_raw
                        })

                # Follow-up generation for natural language response
                second_response = client.chat.completions.create(
                    messages=st.session_state.messages,
                    model=selected_model,
                    tools=tools,
                    tool_choice="auto"
                )
                final_answer = second_response.choices[0].message.content
                st.markdown(final_answer)
                st.session_state.messages.append({"role": "assistant", "content": final_answer})

            else:
                st.markdown(response_message.content)
                st.session_state.messages.append({"role": "assistant", "content": response_message.content})
