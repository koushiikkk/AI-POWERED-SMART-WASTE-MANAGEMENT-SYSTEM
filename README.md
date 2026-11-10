# AI-Powered Smart Waste Management System

An intelligent waste management platform that uses AI-powered image analysis, automatic truck assignment, and dynamic route planning to improve waste collection efficiency.

## Overview

The **AI-Powered Smart Waste Management System** is a cloud-based application designed to modernize traditional waste collection processes.

The system allows users to upload images of public dustbins. Using a Vision AI model, it analyzes the uploaded images to estimate waste levels and identify bins that require collection.

Based on the detected waste level, location, truck availability, and workload, the system automatically assigns collection tasks to suitable garbage trucks. It also dynamically updates active collection routes whenever new complaints are received.

The platform provides separate dashboards for administrators and collection staff, enabling centralized monitoring and efficient waste collection management.

## Key Features

### 1. AI-Powered Dustbin Detection
- Upload dustbin images in supported formats.
- Analyze images using NVIDIA NIM Vision AI.
- Estimate the waste level inside dustbins.
- Identify bins that require immediate attention.
- Generate detection results for waste management decisions.

### 2. Automatic Truck Assignment
- Automatically assign eligible complaints to available garbage trucks.
- Consider truck availability, staff assignment, workload, and location.
- Prioritize bins based on their waste levels.
- Reduce manual intervention in collection scheduling.

### 3. Dynamic Route Planning
- Automatically generate collection routes for assigned trucks.
- Calculate geographical distances using the Haversine formula.
- Insert newly received complaints into active routes.
- Preserve already completed collection stops.
- Update staff dashboards with newly assigned stops.

### 4. Interactive Map Integration
- Visualize dustbin locations and collection routes.
- Display assigned collection stops on an interactive map.
- Provide navigation through Google Maps Directions.
- Help collection staff follow their assigned routes.

### 5. Role-Based Dashboards

**Administrator Dashboard**
- Monitor dustbin detection activities.
- View complaints and their priorities.
- Manage trucks and staff.
- Monitor automatic truck assignments.
- Track collection progress and route information.

**Staff Dashboard**
- View assigned trucks and collection tasks.
- Access assigned collection routes.
- View dustbin locations on the map.
- Mark collection stops as completed.
- Receive updates when new stops are added to active routes.

### 6. Cloud-Based Data Management
- Supabase Authentication for user authentication.
- Supabase PostgreSQL for application data.
- Supabase Storage for uploaded dustbin images.
- Backend APIs for communication between application components.

## System Architecture

The application follows a modular frontend-backend architecture.

```text
                 USER / ADMIN / STAFF
                          |
                          v
                 React Frontend
                          |
                          v
                  FastAPI Backend
                          |
          +---------------+---------------+
          |               |               |
          v               v               v
      NVIDIA NIM       Supabase       Route Planning
      Vision AI        Services        Algorithm
          |               |               |
          v               v               v
      Image Analysis   PostgreSQL      Truck Assignment
      & Waste Level    & Storage       & Route Updates
          |               |               |
          +---------------+---------------+
                          |
                          v
                 Interactive Map
                 & Staff Dashboard
```

## Technology Stack

| Component | Technology |
|---|---|
| Frontend | React.js, JavaScript |
| UI Styling | Tailwind CSS |
| Build Tool | Vite |
| Backend | Python, FastAPI |
| API Server | Uvicorn |
| AI / Image Analysis | NVIDIA NIM API |
| Vision Model | Llama 3.2 90B Vision Instruct |
| Database | Supabase PostgreSQL |
| Authentication | Supabase Auth |
| Image Storage | Supabase Storage |
| Maps | React Leaflet, Leaflet |
| Navigation | Google Maps Directions |
| Route Calculation | Haversine Distance & Priority-Based Insertion Algorithm |
| Version Control | Git & GitHub |

## How the System Works

1. **Image Upload:** A user uploads an image of a dustbin through the application.
2. **AI Analysis:** The backend sends the image for analysis using the NVIDIA NIM Vision AI model.
3. **Waste Assessment:** The AI analyzes the image and estimates the waste level.
4. **Complaint Creation:** The system records the detection result and associated location.
5. **Priority Evaluation:** The system determines the collection priority based on the detected waste level.
6. **Automatic Assignment:** An eligible garbage truck and its assigned staff member are selected.
7. **Route Generation:** The backend calculates distances and generates a collection route.
8. **Dynamic Updates:** When new complaints arrive, pending stops can be inserted into active routes.
9. **Collection Completion:** Staff members mark stops as completed through their dashboard, and the updated status is stored in the database.

## Dynamic Route Planning

One of the major features of this project is dynamic route updating.

Unlike a static route-generation approach, the system supports adding newly received complaints to an already active truck route.

The route planning mechanism:
- Uses geographical coordinates to calculate distances.
- Applies a priority-based insertion algorithm.
- Finds suitable insertion positions for newly assigned collection stops.
- Preserves completed stops while updating pending stops.
- Updates the staff dashboard with the latest route information.

This helps the collection process adapt to incoming complaints without unnecessarily rebuilding the entire route.

**Note:** The current implementation uses geographical distance calculations and priority-based route insertion. Google Maps is used for navigation. It does not currently provide continuous live GPS tracking or traffic-aware route optimization.

## Project Structure

```text
AI-POWERED-SMART-WASTE-MANAGEMENT-SYSTEM/
│
├── backend/
│
├── smart-waste-dashboard/
│   ├── backend/
│   │   ├── app/
│   │   ├── requirements.txt
│   │   └── .env.example
│   │
│   ├── frontend/
│   │   ├── src/
│   │   ├── public/
│   │   ├── package.json
│   │   └── .env.example
│   │
│   └── README.md
│
├── PROMPTS.md
├── implementation_plan.md
├── .gitignore
└── README.md
```

## Installation and Setup

### Prerequisites

Make sure the following are installed:

- Python 3.11
- Node.js and npm
- Git
- A Supabase project
- An NVIDIA NIM API key

### 1. Clone the Repository

```bash
git clone https://github.com/koushiikkk/AI-POWERED-SMART-WASTE-MANAGEMENT-SYSTEM.git
```

```bash
cd AI-POWERED-SMART-WASTE-MANAGEMENT-SYSTEM
```

### 2. Backend Setup

```bash
cd smart-waste-dashboard/backend
```

Create and activate a Python virtual environment:

**Windows PowerShell:**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the required dependencies:

```bash
pip install -r requirements.txt
```

Configure the backend environment variables using the provided `.env.example` file. Add the required Supabase and NVIDIA NIM credentials.

Start the backend:

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Backend URL:

```text
http://127.0.0.1:8000
```

### 3. Frontend Setup

Open another terminal:

```bash
cd smart-waste-dashboard/frontend
```

Install dependencies:

```bash
npm install
```

Configure the frontend environment variables using the provided `.env.example` file.

Start the development server:

```bash
npm run dev
```

Frontend URL:

```text
http://localhost:5173
```

**Note:** Configure the environment variables and Supabase project schema according to the application setup before running the system.

## Cloud Integration

The application is designed around cloud-based services.

Current cloud components:

- **Supabase Authentication:** Handles user authentication.
- **Supabase PostgreSQL:** Stores application records and operational data.
- **Supabase Storage:** Stores uploaded dustbin images.
- **NVIDIA NIM:** Provides AI-powered image analysis through its API.

AWS integration code is also maintained in the project for potential future use. AWS services are currently disabled in the running application.

## Security Considerations

- Environment variables are used to manage application credentials.
- Sensitive API keys must not be committed to version control.
- Backend-only credentials must remain on the server.
- Authentication and role-based access help restrict dashboard functionality.
- `.gitignore` excludes local environment files and other sensitive or temporary files.

**Important:** Never upload actual `.env` files, API keys, service-role keys, or cloud credentials to GitHub.

## Future Enhancements

Potential improvements include:

- Integration with IoT-enabled smart dustbins for real-time fill-level monitoring.
- GPS-based live truck tracking.
- Traffic-aware route optimization.
- Predictive waste collection using historical data.
- Advanced analytics and waste generation forecasting.
- Integration with additional cloud services for scalability.

## Project Information

**Project Name:** AI-Powered Smart Waste Management System

**Domain:** Artificial Intelligence, Cloud Computing, Smart Cities

**Primary Objective:** Improve waste collection efficiency through AI-powered dustbin analysis, automatic truck assignment, and dynamic route planning.

**Repository:** [GitHub - AI-Powered Smart Waste Management System](https://github.com/koushiikkk/AI-POWERED-SMART-WASTE-MANAGEMENT-SYSTEM)

---

*Developed as an academic project focused on intelligent and efficient urban waste management.*
