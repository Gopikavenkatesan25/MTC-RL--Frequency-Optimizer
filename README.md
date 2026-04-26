🚌 MTC Chennai RL Bus Frequency Optimizer

## 🌐 Live Demo  
[Click Here to Open App](https://mtc-rl-optimizer.streamlit.app/)

🚀 Overview
This project is a Reinforcement Learning-based bus frequency optimization system for Chennai MTC routes. It simulates real-world public transport behavior and compares a traditional static scheduling system with an intelligent RL-based adaptive system that reduces passenger waiting time and improves fleet efficiency.
The system uses a FastAPI backend for simulation logic and a Streamlit frontend for interactive visualization and analysis.

✨ Key Features
RL-based vs Static scheduling comparison
Real-time simulation in 15-minute intervals
Passenger demand-based optimization
Route disruption simulation and recovery behavior
Auto-step live animation mode
24-hour performance comparison visualization
Interactive Streamlit dashboard

🧠 Problem Statement
Urban bus systems often suffer from:
Fixed schedules that do not adapt to demand
High passenger waiting time during peak hours
Poor response to route disruptions or breakdowns
Inefficient fleet utilization

💡 Proposed Solution
We introduce an RL-based simulation system that:
Dynamically adjusts bus frequency based on demand
Minimizes passenger waiting time
Reacts intelligently to disruptions
Improves overall transport efficiency compared to static scheduling

🏗️ Project Structure
mtc_rl/
├── backend.py        → FastAPI RL simulation engine
├── frontend.py       → Streamlit dashboard
├── requirements.txt  → Dependencies
└── README.md

⚙️ Setup & Installation
1️⃣ Install dependencies
pip install -r requirements.txt
2️⃣ Start FastAPI Backend

(Open Terminal 1)
uvicorn backend:app --reload --port 8000
3️⃣ Start Streamlit Frontend

(Open Terminal 2)
streamlit run frontend.py

4️⃣ Open in browser
🎛️ Streamlit UI → http://localhost:8501
📡 FastAPI Docs → http://localhost:8000/docs

🎮 How to Use / Demo Flow
## 🌐 Live Demo  
[Click Here to Open App](https://mtc-rl-optimizer.streamlit.app/)

Follow this sequence during demonstration:

Start in Static Mode
Click “Step +15 min” multiple times
Observe high waiting times
Switch to RL Agent Mode
Continue stepping forward
Observe improved optimization
Click Compare Modes
View 24-hour performance comparison graph
Simulate Route Disruption
Break a route using disruption feature
Observe RL agent adapting dynamically
Enable Auto-Step Mode
Watch live simulation animation

📡 API Endpoints
Method	Endpoint	Description
GET	/routes	Get all MTC routes
GET	/state	Current simulation state
POST	/step	Advance simulation by 15 min
POST	/set_mode/{mode}	Switch static or RL mode
POST	/disrupt/{route_id}	Simulate breakdown
POST	/restore/{route_id}	Restore route
POST	/reset	Reset simulation
GET	/compare	24-hour static vs RL comparison

📊 Evaluation Mapping

📌 Data-Centric (35%)
Synthetic MTC demand modeling
Passenger flow simulation
AVL-like behavior simulation

📌 Performance (30%)
Reduced passenger waiting time
Improved fleet utilization
Adaptive frequency optimization

📌 Technical (20%)
FastAPI backend architecture
Streamlit interactive frontend
Reinforcement Learning-inspired logic

📌 Documentation (15%)
Structured README
Clear demo flow instructions
API documentation included

📈 Impact
Reduces passenger waiting time significantly
Improves bus frequency planning
Handles real-time disruptions effectively
Helps urban transport decision-making

🚀 Future Improvements
Real-time GPS integration
Live traffic API connection
Advanced Deep RL (PPO / DQN) implementation
Mobile application version
Cloud deployment with live tracking

👨‍💻 Developer Info
Developed as part of an AI + Urban Transport optimization hackathon project.
