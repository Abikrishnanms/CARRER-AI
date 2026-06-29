# CARRER AI 🚀
> **An AI Multi-Agent Job Intelligence Platform**

CarrerAI is an industry-level AI-Powered Platform designed to automate job collection, processing, classification, and personalized recommendation using multiple intelligent software agents.

The project combines Artificial Intelligence, Distributed Systems, Machine Learning, Web Scraping, PostgreSQL, RabbitMQ, Redis, Docker, and Streamlit to create a scalable job intelligence ecosystem.

---

## Project Vision

CarrerAI aims to simplfy the job search process by automatically collecting job postings from multiple platforms, understanding both job requirements and user skills, and recommending the most relevant opportunities through intelligent AI agents.

---

## Objectives
- Collect jobs from multiple platforms
- Process and clean job data
- Extract skills automatically
- Classify jobs using AI
- Recommend jobs based on user profile
- Provide analytics and insights
- Build a scalable multi-agent architecture

---
## 🏗 System Architecture

```
                     Users
                        │
                        ▼
              Streamlit Dashboard
                        │
                        ▼
              Orchestrator Agent
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
 Search Agent    Scraper Agent   Recommendation Agent
                        │
                        ▼
                   RabbitMQ
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
 Cleaning Agent  Skill Agent  Classification Agent
                        │
                        ▼
                  PostgreSQL
```

---

## 🛠 Technology Stack

| Category | Technology |
|----------|------------|
| Language | Python |
| Frontend | Streamlit |
| Database | PostgreSQL |
| ORM | SQLAlchemy |
| Queue | RabbitMQ |
| Cache | Redis |
| Web Scraping | Selenium, BeautifulSoup |
| ML | Scikit-learn |
| Containers | Docker |
| Version Control | Git |

---

## 📂 Project Structure

```
job-segmentation/

├── agents/
├── app/
├── config/
├── database/
├── data/
├── docker/
├── docs/
├── logs/
├── models/
├── scripts/
├── services/
├── tests/

├── README.md
├── requirements.txt
├── .gitignore
└── docker-compose.yml
```

---

## 🚧 Current Status

**Version:** v0.1.0

Current Sprint:

- ✅ Project Planning
- ✅ System Architecture
- ✅ Repository Structure
- 🚧 Environment Setup
- ⏳ Infrastructure Setup
- ⏳ Agent Development

---

## 📅 Development Roadmap

- Project Foundation
- Infrastructure Setup
- Multi-Agent Development
- Database Integration
- Recommendation Engine
- Dashboard Development
- Deployment

---

## 👨‍💻 Author

**Abikrishnan M S**

MSc Computer Science (Data Analytics)

Digital University Kerala

---

## 📄 License

This project is developed for educational and research purposes.